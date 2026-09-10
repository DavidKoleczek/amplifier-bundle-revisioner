#!/usr/bin/env python3
"""Build the ReVisioner UX: emit revision-state.json and instantiate the app template.

Read-only with respect to .amplifier/revisioner/: this script renders state, it never
authors it. It does not set risk or confidence, does not write to the ledger, and does
not touch vision.md.

What it does:
  1. Shells out to vision-check-in/scripts/classify.py --json and embeds the result
     VERBATIM under "classification". Buckets, categories and recommended mode are never
     recomputed here -- the check-in conversation and the UI must not disagree.
  2. Builds "evidence" for every current-vision assumption: the inlined spike-plan.md,
     findings.md, verdict.json and status.json, the ledger's own derisking block, and an
     index of every remaining file in data/<id>/.
  3. Copies assets/template/ into the output directory and data/ into <out>/public/data/,
     then writes <out>/public/revision-state.json.

Absence is data: a missing findings.md emits null, never "" and never a placeholder.

Usage:
    python3 build_ux.py
    python3 build_ux.py --out ./somewhere/ux
    python3 build_ux.py --data-only          # refresh state, keep the installed template
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml  # PyYAML
except ImportError:  # pragma: no cover
    sys.stderr.write("PyYAML is required (pip install pyyaml).\n")
    sys.exit(2)

CURRENT_KEY = "assumptions_related_to_current_vision"
PAST_KEY = "assumptions_related_to_past_visions"

# Inlined into the JSON unless a warning requires access to the raw file.
RESERVED_FILES = {"spike-plan.md", "findings.md", "verdict.json", "status.json"}

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_LEDGER = "./.amplifier/revisioner/risky-assumptions.yaml"
DEFAULT_OUT = "./.amplifier/revisioner/ux"
DEFAULT_CLASSIFIER = ".amplifier/skills/vision-check-in/scripts/classify.py"


# --------------------------------------------------------------------------- reading


def read_text_or_none(path: Path, warnings: list[dict[str, str]]) -> str | None:
    """Preserve empty text; warn on unreadable text and stop on denied access."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except PermissionError:
        raise
    except (OSError, UnicodeDecodeError) as exc:
        warnings.append({"path": path.as_posix(), "message": f"Cannot read text: {exc}"})
        return None


def read_json_or_none(
    path: Path, warnings: list[dict[str, str]], *, strict_status: bool = False
) -> dict[str, Any] | None:
    """Optional JSON objects; malformed run-state must not become an open assumption."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("expected a JSON object")
        json.dumps(value, allow_nan=False)
        if strict_status:
            if value.get("state") not in ("running", "done", "blocked"):
                raise ValueError("expected state to be running, done, or blocked")
            if "updated" in value and not isinstance(value["updated"], str):
                raise ValueError("updated must be a string when present")
        return value
    except FileNotFoundError:
        return None
    except PermissionError:
        raise
    except (OSError, ValueError) as exc:
        if strict_status:
            raise SystemExit(f"{path}: invalid status; {exc}. Fix this file before building.") from exc
        warnings.append({"path": path.as_posix(), "message": f"Cannot inline verdict: {exc}"})
        return None


def validate_entry(entry: Any, location: str) -> None:
    """Check only fields the classifier and dashboard consume; never coerce them."""
    if not isinstance(entry, dict):
        raise SystemExit(f"{location}: expected an assumption mapping.")
    entry_id = entry.get("id")
    if not isinstance(entry_id, str) or not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9._-]*", entry_id):
        raise SystemExit(f"{location}: id must be a safe nonempty string using letters, digits, _, -, or .")
    if not isinstance(entry.get("assumption"), str) or not entry["assumption"].strip():
        raise SystemExit(f"{location}: assumption must be nonempty text.")
    for axis, lower in (("risk", 0), ("confidence", -1)):
        value = entry.get(axis)
        # Missing or null axes retain classify.py's existing zero default.
        if value is None:
            continue
        if (
            type(value) not in (int, float)
            or not lower <= value <= 1
            or (isinstance(value, float) and not math.isfinite(value))
        ):
            raise SystemExit(f"{location}: {axis} must be a finite number in [{lower}, 1], or null.")
    approaches = entry.get("derisking")
    if approaches is None:
        return
    if not isinstance(approaches, list):
        raise SystemExit(f"{location}: derisking must be a list of mappings, or null.")
    for index, approach in enumerate(approaches):
        where = f"{location}.derisking[{index}]"
        if not isinstance(approach, dict):
            raise SystemExit(f"{where}: expected an approach mapping.")
        for field, expected in (("approach", str), ("needs", str), ("blocked", bool)):
            if field in approach and not isinstance(approach[field], expected):
                raise SystemExit(f"{where}: {field} must be {expected.__name__} when present.")


def load_sections(path: Path) -> dict[str, list]:
    """Return {section_key: [entries]} from the two-section ledger."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise SystemExit(f"{path}: invalid YAML ledger; {exc}") from exc
    if not isinstance(data, list):
        raise SystemExit(
            f"Unexpected ledger structure in {path}: expected a top-level YAML list."
        )
    out: dict[str, list] = {CURRENT_KEY: [], PAST_KEY: []}
    seen_sections: set[str] = set()
    seen_ids: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            raise SystemExit(f"{path}: expected section mappings in the top-level list.")
        for key, value in item.items():
            if key not in out:
                continue
            if key in seen_sections or not isinstance(value, list):
                raise SystemExit(f"{path}: {key} must occur once as a list of assumption mappings.")
            seen_sections.add(key)
            for index, entry in enumerate(value):
                location = f"{path}: {key}[{index}]"
                validate_entry(entry, location)
                if entry["id"] in seen_ids:
                    raise SystemExit(f"{location}: duplicate id {entry['id']!r} across ledger sections.")
                seen_ids.add(entry["id"])
            out[key] = value
    if not seen_sections:
        raise SystemExit(f"{path}: no recognized assumption sections; consult references/state-contract.md.")
    return out


def repo_root_for(ledger: Path) -> Path:
    """Walk up from the ledger to the directory holding .amplifier/; else use cwd."""
    for parent in ledger.resolve().parents:
        if parent.name == ".amplifier":
            return parent.parent
    return Path.cwd().resolve()


# ---------------------------------------------------------------------- classification


def run_classifier(classifier: Path, ledger: Path) -> dict[str, Any]:
    """Invoke classify.py --json and return its output unchanged.

    Thresholds and bucketing live in exactly one place. If the classifier cannot run,
    fail loudly rather than guessing at buckets.
    """
    proc = subprocess.run(
        [sys.executable, str(classifier), "--file", str(ledger), "--json"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"Classifier failed (exit {proc.returncode}): {classifier}\n"
            f"{proc.stderr.strip()}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Classifier did not emit valid JSON: {classifier}\n{exc}\n"
            f"stdout was:\n{proc.stdout[:2000]}"
        ) from exc


def validate_classification(result: Any, entries: list, classifier: Path) -> None:
    """Check the join and renderable structure, not the classifier's decisions."""
    prefix = f"{classifier}: incompatible classifier output"
    categories = ("holds", "fails", "blocked", "in_flight", "open")
    if not isinstance(result, dict):
        raise SystemExit(f"{prefix}; expected an object.")
    if result.get("recommended_mode") not in ("stale", "pivot", "unblock", "in_progress", "all_clear"):
        raise SystemExit(f"{prefix}; unknown recommended_mode.")
    if not isinstance(result.get("rows"), list):
        raise SystemExit(f"{prefix}; rows must be a list.")
    row_ids = []
    for row in result["rows"]:
        validate_entry(row, prefix)
        row_ids.append(row["id"])
        if any(type(row.get(axis)) not in (int, float) for axis in ("risk", "confidence")):
            raise SystemExit(f"{prefix}; rows must include numeric risk and confidence.")
        if row.get("category") not in categories or not isinstance(row.get("status"), str):
            raise SystemExit(f"{prefix}; invalid row category or status.")
        if row.get("lean") not in ("positive", "neutral", "negative"):
            raise SystemExit(f"{prefix}; invalid row lean.")
        if any(type(row.get(field)) is not bool for field in ("high_risk", "has_blocked_residual")):
            raise SystemExit(f"{prefix}; row flags must be booleans.")
        if not isinstance(row.get("needs"), list) or any(not isinstance(n, str) for n in row["needs"]):
            raise SystemExit(f"{prefix}; row needs must be a list of strings.")
    if len(row_ids) != len(set(row_ids)) or set(row_ids) != {e["id"] for e in entries}:
        raise SystemExit(f"{prefix}; row IDs must match current-vision ledger IDs exactly.")
    counts, buckets = result.get("counts"), result.get("buckets")
    if not isinstance(counts, dict) or not isinstance(buckets, dict):
        raise SystemExit(f"{prefix}; counts and buckets must be mappings.")
    for category in categories:
        if type(counts.get(category)) is not int or counts[category] < 0:
            raise SystemExit(f"{prefix}; {category} count must be a nonnegative integer.")
        if not isinstance(buckets.get(category), list):
            raise SystemExit(f"{prefix}; {category} bucket must be a list.")
    bucket_rows = [row for category in categories for row in buckets[category]]
    rows_by_id = {row["id"]: row for row in result["rows"]}
    if (
        len(bucket_rows) != len(row_ids)
        or any(not isinstance(row, dict) or not isinstance(row.get("id"), str)
               or row != rows_by_id.get(row["id"]) for row in bucket_rows)
        or len({row["id"] for row in bucket_rows}) != len(row_ids)
    ):
        raise SystemExit(f"{prefix}; bucket rows must match rows exactly.")
    for field in ("high_risk_total", "high_risk_holding"):
        if type(result.get(field)) is not int or result[field] < 0:
            raise SystemExit(f"{prefix}; {field} must be a nonnegative integer.")
    drift = result.get("vision_drift")
    if drift is not None and (
        not isinstance(drift, dict)
        or any(type(drift.get(field)) is not bool for field in ("checked", "stale"))
    ):
        raise SystemExit(f"{prefix}; vision_drift must contain boolean checked and stale flags.")


# -------------------------------------------------------------------------- evidence


def list_artifacts(spike_dir: Path, raw_files: set[str] | None = None) -> list[dict[str, Any]]:
    """Index raw files, including optional documents that could not be inlined.

    Paths are posix and relative to public/, so they resolve as ordinary links once the
    data tree has been copied to <out>/public/data/.
    """
    if not spike_dir.is_dir():
        return []
    artifacts: list[dict[str, Any]] = []

    def onerror(exc: OSError) -> None:
        raise exc

    for directory, _, files in os.walk(spike_dir, onerror=onerror):
        for name in files:
            file_path = Path(directory) / name
            relative = file_path.relative_to(spike_dir).as_posix()
            if relative in RESERVED_FILES and relative not in (raw_files or set()):
                continue
            artifacts.append(
                {"path": f"data/{spike_dir.name}/{relative}", "bytes": file_path.stat().st_size}
            )
    artifacts.sort(key=lambda a: a["path"])
    return artifacts


def build_evidence(entries: list, data_dir: Path, warnings: list[dict[str, str]]) -> dict[str, Any]:
    """One drill-down payload per current-vision assumption, keyed by id."""
    evidence: dict[str, Any] = {}
    if data_dir.exists() and not data_dir.is_dir():
        raise SystemExit(f"{data_dir}: expected a spike data directory.")
    for entry in entries:
        entry_id = entry["id"]
        spike_dir = data_dir / entry_id
        if spike_dir.exists() and not spike_dir.is_dir():
            raise SystemExit(f"{spike_dir}: expected a spike directory.")
        derisking = entry.get("derisking")
        warning_start = len(warnings)
        evidence[entry_id] = {
            "spike_plan": read_text_or_none(spike_dir / "spike-plan.md", warnings),
            "findings": read_text_or_none(spike_dir / "findings.md", warnings),
            "verdict": read_json_or_none(spike_dir / "verdict.json", warnings),
            "status": read_json_or_none(spike_dir / "status.json", warnings, strict_status=True),
            "derisking": derisking if isinstance(derisking, list) else [],
            "artifacts": list_artifacts(
                spike_dir, {Path(w["path"]).name for w in warnings[warning_start:]}
            ),
        }
    return evidence


# ----------------------------------------------------------------------------- output


def install_template(template_dir: Path, out_dir: Path) -> None:
    """Copy the bundled template over the output directory.

    Template-owned files are overwritten; anything else already there (notably an
    installed node_modules/ or a built dist/) is left alone.
    """
    if not template_dir.is_dir():
        raise SystemExit(
            f"Bundled template not found: {template_dir}\n"
            "The skill install looks incomplete."
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(template_dir, out_dir, dirs_exist_ok=True)


def install_data(data_dir: Path, public_dir: Path) -> int:
    """Mirror data/ into public/data/, replacing any previous copy. Returns file count."""
    target = public_dir / "data"
    if target.exists():
        shutil.rmtree(target)
    if not data_dir.is_dir():
        return 0
    shutil.copytree(data_dir, target)
    return sum(1 for p in target.rglob("*") if p.is_file())


def next_command(out_dir: Path) -> str:
    manager = "pnpm" if shutil.which("pnpm") else "npm"
    run = "pnpm dev" if manager == "pnpm" else "npm run dev"
    return f"cd {out_dir} && {manager} install && {run}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--file",
        default=DEFAULT_LEDGER,
        help=f"Path to risky-assumptions.yaml (default: {DEFAULT_LEDGER})",
    )
    parser.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help=f"Directory to generate the app into (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--data-only",
        action="store_true",
        help="Refresh revision-state.json and public/data/ without re-copying the template.",
    )
    parser.add_argument(
        "--classifier",
        default=DEFAULT_CLASSIFIER,
        help=f"Path to vision-check-in's classify.py (default: {DEFAULT_CLASSIFIER})",
    )
    args = parser.parse_args()

    ledger = Path(args.file)
    if not ledger.is_file() or ledger.stat().st_size == 0:
        raise SystemExit(
            f"Ledger not found or empty: {ledger}\n"
            "There is no state worth rendering yet -- run the find-risky-assumptions "
            "skill first to populate .amplifier/revisioner/risky-assumptions.yaml."
        )

    classifier = Path(args.classifier)
    if not classifier.is_file():
        raise SystemExit(
            f"Classifier not found: {classifier}\n"
            "build_ux.py delegates all bucketing to vision-check-in/scripts/classify.py "
            "and will not guess at categories. Point --classifier at that script."
        )

    source_dir = ledger.parent
    data_dir = source_dir / "data"
    vision_path = source_dir / "vision.md"
    repo_root = repo_root_for(ledger)

    sections = load_sections(ledger)
    warnings: list[dict[str, str]] = []
    evidence = build_evidence(sections[CURRENT_KEY], data_dir, warnings)
    vision_markdown = read_text_or_none(vision_path, warnings)
    classification = run_classifier(classifier, ledger)
    validate_classification(classification, sections[CURRENT_KEY], classifier)

    try:
        vision_rel = vision_path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        vision_rel = vision_path.as_posix()

    state = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo": repo_root.name,
        "vision": {
            "path": vision_rel,
            "markdown": vision_markdown,
        },
        "classification": classification,
        "evidence": evidence,
        "past_assumptions": sections[PAST_KEY],
    }
    if warnings:
        state["warnings"] = [
            {"path": Path(w["path"]).relative_to(source_dir).as_posix(), "message": w["message"]}
            for w in warnings
        ]
        for warning in state["warnings"]:
            print(f"warning: {warning['path']}: {warning['message']}", file=sys.stderr)
    try:
        serialized = json.dumps(state, indent=2, allow_nan=False) + "\n"
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"{ledger}: state is not JSON-compatible; {exc}. Output was not changed.") from exc

    out_dir = Path(args.out)
    if args.data_only:
        if not (out_dir / "package.json").is_file():
            print(
                f"warning: no template found at {out_dir} -- writing data only. "
                "Re-run without --data-only to install the app.",
                file=sys.stderr,
            )
    else:
        install_template(SKILL_DIR / "assets" / "template", out_dir)

    public_dir = out_dir / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    artifact_files = install_data(data_dir, public_dir)

    state_path = public_dir / "revision-state.json"
    state_path.write_text(serialized, encoding="utf-8")

    counts = classification.get("counts", {})
    spiked = sum(1 for e in evidence.values() if e["findings"] is not None)
    indexed = sum(len(e["artifacts"]) for e in evidence.values())
    print(f"Wrote {state_path}")
    print(
        f"  {len(evidence)} current-vision assumptions "
        f"({spiked} with recorded findings, {indexed} artifacts indexed, "
        f"{artifact_files} files copied to public/data/)"
    )
    print(
        "  counts: "
        + (", ".join(f"{k}={v}" for k, v in counts.items() if v) or "(nothing yet)")
    )
    print(f"  recommended mode: {classification.get('recommended_mode', '?').upper()}")
    if (classification.get("vision_drift") or {}).get("stale"):
        print("  !! vision drift: the ledger predates the current vision.md")
    if not args.data_only:
        print(f"  template installed to {out_dir}")
    print()
    print("Next:")
    print(f"  {next_command(out_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
