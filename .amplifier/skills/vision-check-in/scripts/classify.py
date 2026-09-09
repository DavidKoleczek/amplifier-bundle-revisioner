#!/usr/bin/env python3
"""Classify the current state of a revisioner risky-assumptions ledger.

Read-only. Joins the ledger (risk + signed confidence + any derisking block) with
each assumption's live run-state from ./.amplifier/revisioner/data/<id>/status.json,
buckets every assumption in the CURRENT-vision section, and recommends which of the
three check-in conversations to have.

The two axes (set elsewhere, never by this script):
    risk        0.00..1.00   stakes only -- how much the vision depends on this bet.
    confidence -1.00..+1.00  signed belief it holds (+ holds, - does not, |.| = strength).

Run-state (written by the derisk skill, one file per spike):
    data/<id>/status.json  ->  {"state": "running|done|blocked", ...}
    Absent  ->  inferred from the ledger (all-blocked derisking, or untested at 0.0).

Categories (first match wins):
    in_flight  status == running                          -> a spike is working now
    holds      confidence >= +hold-threshold              -> de-risked, bet looks true
    fails      confidence <= -fail-threshold              -> risk REALIZED, bet looks false
    blocked    status == blocked, or every derisking       -> needs something from the user
               approach is blocked and it is not resolved
    open       otherwise (untested, or thin/inconclusive) -> still spike-able as-is

Recommended mode (priority order):
    pivot      >=1 high-risk assumption FAILS              -> propose a vision update
    unblock    >=1 high-risk assumption BLOCKED            -> ask user to supply `needs`
    in_progress spikes running or open work remains        -> let it run / keep de-risking
    all_clear  every high-risk assumption HOLDS            -> report success

"High-risk" means risk >= --high-risk-threshold. Usage:

    python3 classify.py --file ./.amplifier/revisioner/risky-assumptions.yaml
    python3 classify.py --file <path> --json      # machine-readable
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # PyYAML
except ImportError:  # pragma: no cover
    sys.stderr.write("PyYAML is required (pip install pyyaml).\n")
    sys.exit(2)

CURRENT_KEY = "assumptions_related_to_current_vision"
PAST_KEY = "assumptions_related_to_past_visions"

CAT_ORDER = ["fails", "blocked", "in_flight", "open", "holds"]

META_KEY = "revisioner_meta"


def stored_vision_hash(path: Path) -> str | None:
    """Read the vision fingerprint stamped into the ledger, or None if unstamped."""
    try:
        data = yaml.safe_load(path.read_text()) or []
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(data, list):
        return None
    for item in data:
        if isinstance(item, dict) and META_KEY in item:
            block = item[META_KEY]
            if isinstance(block, dict) and block.get("vision_sha256"):
                return str(block["vision_sha256"])
    return None


def current_vision_hash(vision_path: Path) -> str | None:
    """Byte-exact sha256 of the current vision file, or None if it is absent."""
    if not vision_path.exists():
        return None
    import hashlib

    return hashlib.sha256(vision_path.read_bytes()).hexdigest()


def check_drift(ledger: Path, vision_path: Path) -> dict[str, Any]:
    """Compare the vision the ledger was built from against the vision on disk now.

    Only a positive mismatch (both hashes known and different) is 'stale'. An unstamped
    ledger or a missing vision file yields checked=False -- no false alarm, no signal.
    """
    stored = stored_vision_hash(ledger)
    current = current_vision_hash(vision_path)
    checked = stored is not None and current is not None
    return {
        "checked": checked,
        "stale": checked and stored != current,
        "stored": stored,
        "current": current,
        "vision_path": str(vision_path),
    }


def load_sections(path: Path) -> dict[str, list]:
    """Return {section_key: [entries]} for the top-level list-of-sections ledger."""
    if not path.exists() or path.stat().st_size == 0:
        raise SystemExit(
            f"Ledger not found or empty: {path} (run find-risky-assumptions first)."
        )
    data = yaml.safe_load(path.read_text()) or []
    if not isinstance(data, list):
        raise SystemExit(
            f"Unexpected ledger structure in {path}: expected a top-level list."
        )
    out: dict[str, list] = {CURRENT_KEY: [], PAST_KEY: []}
    for item in data:
        if isinstance(item, dict):
            for key, value in item.items():
                if key in out and isinstance(value, list):
                    out[key] = value
    return out


def read_status(data_dir: Path, entry_id: str) -> str | None:
    """Return the run-state string from data/<id>/status.json, or None if absent/unreadable."""
    status_path = data_dir / entry_id / "status.json"
    if not status_path.exists():
        return None
    try:
        state = json.loads(status_path.read_text()).get("state")
    except (json.JSONDecodeError, OSError):
        return None
    return str(state) if state is not None else None


def derisking_all_blocked(entry: dict) -> bool:
    """True when the entry carries a derisking block and every approach is blocked."""
    block = entry.get("derisking")
    if not isinstance(block, list) or not block:
        return False
    return all(isinstance(a, dict) and a.get("blocked", False) for a in block)


def categorize(entry: dict, status: str | None, hold: float, fail: float) -> str:
    confidence = float(entry.get("confidence", 0.0) or 0.0)
    if status == "running":
        return "in_flight"
    if confidence >= hold:
        return "holds"
    if confidence <= -fail:
        return "fails"
    if status == "blocked":
        return "blocked"
    if status is None and derisking_all_blocked(entry):
        return "blocked"
    return "open"


def lean(confidence: float) -> str:
    if confidence > 0.05:
        return "positive"
    if confidence < -0.05:
        return "negative"
    return "neutral"


def classify(
    sections: dict[str, list],
    data_dir: Path,
    hold: float,
    fail: float,
    high_risk: float,
    drift: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for entry in sections.get(CURRENT_KEY, []):
        if not isinstance(entry, dict) or "id" not in entry:
            continue
        entry_id = str(entry["id"])
        status = read_status(data_dir, entry_id)
        confidence = float(entry.get("confidence", 0.0) or 0.0)
        risk = float(entry.get("risk", 0.0) or 0.0)
        category = categorize(entry, status, hold, fail)
        rows.append(
            {
                "id": entry_id,
                "assumption": str(entry.get("assumption", "")),
                "risk": round(risk, 2),
                "confidence": round(confidence, 2),
                "high_risk": risk >= high_risk,
                "status": status or "unset",
                "category": category,
                "lean": lean(confidence),
                "has_blocked_residual": derisking_all_blocked(entry),
                "needs": [
                    a.get("needs", "")
                    for a in (entry.get("derisking") or [])
                    if isinstance(a, dict) and a.get("blocked", False)
                ],
            }
        )

    # Sort within the whole set: category priority, then risk desc, then id.
    rows.sort(key=lambda r: (CAT_ORDER.index(r["category"]), -r["risk"], r["id"]))

    def bucket(cat: str) -> list[dict[str, Any]]:
        return [r for r in rows if r["category"] == cat]

    high = [r for r in rows if r["high_risk"]]
    high_fail = [r for r in high if r["category"] == "fails"]
    high_blocked = [r for r in high if r["category"] == "blocked"]
    high_hold = [r for r in high if r["category"] == "holds"]
    running_or_open = [r for r in rows if r["category"] in ("in_flight", "open")]

    drift = drift or {"checked": False, "stale": False}
    if drift.get("stale"):
        # The vision changed since this ledger was built: every bet below is suspect,
        # so drift outranks even a realized risk. Don't reason about stale assumptions.
        mode = "stale"
    elif high_fail:
        mode = "pivot"
    elif high_blocked:
        mode = "unblock"
    elif high and len(high_hold) == len(high) and not running_or_open:
        mode = "all_clear"
    else:
        mode = "in_progress"

    return {
        "recommended_mode": mode,
        "counts": {cat: len(bucket(cat)) for cat in CAT_ORDER},
        "high_risk_total": len(high),
        "high_risk_holding": len(high_hold),
        "vision_drift": drift,
        "buckets": {cat: bucket(cat) for cat in CAT_ORDER},
        "rows": rows,
    }


def render_human(result: dict[str, Any]) -> str:
    lines: list[str] = []
    mode = result["recommended_mode"]
    c = result["counts"]
    lines.append(f"Recommended check-in mode: {mode.upper()}")
    drift = result.get("vision_drift") or {}
    if drift.get("stale"):
        lines.append(
            "  !! VISION DRIFT: vision.md changed since this ledger was built "
            "-- assumptions below are STALE."
        )
        lines.append(
            f"     stored={str(drift.get('stored'))[:12]}... current={str(drift.get('current'))[:12]}..."
        )
        lines.append(
            "     Re-run find-risky-assumptions on the current vision before trusting a check-in."
        )
    lines.append(
        f"  high-risk assumptions: {result['high_risk_holding']}/{result['high_risk_total']} holding"
    )
    lines.append(
        "  counts: "
        + ", ".join(f"{cat}={c[cat]}" for cat in CAT_ORDER if c[cat])
        + (" (nothing yet)" if not any(c.values()) else "")
    )
    labels = {
        "fails": "INVALIDATED (risk realized) -- pivot candidates",
        "blocked": "BLOCKED -- need input to proceed",
        "in_flight": "IN FLIGHT -- spike running now",
        "open": "OPEN -- untested or inconclusive, still spike-able",
        "holds": "HOLDS -- de-risked",
    }
    for cat in CAT_ORDER:
        rows = result["buckets"][cat]
        if not rows:
            continue
        lines.append("")
        lines.append(f"[{labels[cat]}]")
        for r in rows:
            flag = "*" if r["high_risk"] else " "
            head = f"  {flag}{r['id']}  risk={r['risk']:.2f} conf={r['confidence']:+.2f}  {r['assumption'][:90]}"
            lines.append(head)
            if cat == "blocked" and r["needs"]:
                for need in r["needs"]:
                    lines.append(f"        needs: {need}")
    lines.append("")
    lines.append("  (* = high-risk)")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--file", required=True, help="Path to risky-assumptions.yaml")
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Spike data dir (default: <ledger dir>/data)",
    )
    parser.add_argument("--hold-threshold", type=float, default=0.7)
    parser.add_argument("--fail-threshold", type=float, default=0.7)
    parser.add_argument("--high-risk-threshold", type=float, default=0.7)
    parser.add_argument(
        "--vision",
        default=None,
        help="Path to vision.md for drift detection (default: <ledger dir>/vision.md)",
    )
    parser.add_argument(
        "--no-drift-check",
        action="store_true",
        help="Skip the vision-drift check entirely.",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )
    args = parser.parse_args()

    path = Path(args.file)
    data_dir = Path(args.data_dir) if args.data_dir else path.parent / "data"
    vision_path = Path(args.vision) if args.vision else path.parent / "vision.md"
    drift = (
        {"checked": False, "stale": False}
        if args.no_drift_check
        else check_drift(path, vision_path)
    )
    sections = load_sections(path)
    result = classify(
        sections,
        data_dir,
        args.hold_threshold,
        args.fail_threshold,
        args.high_risk_threshold,
        drift,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(render_human(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
