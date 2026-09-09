#!/usr/bin/env python3
"""Update the ``confidence`` of risky assumptions after de-risking spikes.

This is the write step of the de-risking skill. It consumes the verdicts produced
by spikes and records them into the revisioner risky-assumptions.yaml file.

Rules it enforces so the caller cannot corrupt the ledger:
- Match entries by ``id`` across BOTH sections (current + past visions).
- Only ever touch ``confidence`` and (optionally) the ``derisking`` block.
- NEVER modify ``risk``, ``assumption``, ``id``, ordering, or section shape.
  Risk is stakes-only and is owned by the find skill; de-risking does not move it.
- ``confidence`` is a SIGNED belief that the assumption holds, -1.00..+1.00:
      +1  strong evidence it HOLDS      -> the risk is not being taken (de-risked)
       0  no/inconclusive evidence      -> still an open risk
      -1  strong evidence it does NOT hold -> the risk has been realized
  Magnitude = strength of evidence, sign = direction.

Conditional unknowability: when a spike cannot resolve an assumption right now,
leave confidence near 0 and attach a ``derisking`` list describing what was tried
and what would unblock it. Each approach is:
      {"approach": "<what to do>", "needs": "<info/tool/access required>", "blocked": true}
An assumption is "conditionally unknowable" when every listed approach is blocked;
the ``needs`` fields name exactly what would make it knowable.

Input is a JSON array of verdicts, each:
    {"id": "RA-xxxxxx",
     "confidence": <float -1.00..1.00>,
     "derisking": [ {"approach": "...", "needs": "...", "blocked": true}, ... ]  # optional
    }

Usage:
    python3 update_confidence.py --file <path> --input <verdicts.json>
    python3 update_confidence.py --file <path> --json '[{"id": "RA-ab12Cd", "confidence": 0.8}]'
    cat verdicts.json | python3 update_confidence.py --file <path> --input -
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml  # PyYAML
except ImportError:  # pragma: no cover
    sys.stderr.write(
        "PyYAML is required (pip install pyyaml), or edit the YAML by hand.\n"
    )
    sys.exit(2)


def load_doc(path: Path) -> list:
    """Load the top-level list of sections; refuse to invent one if it is missing."""
    if not path.exists() or path.stat().st_size == 0:
        raise SystemExit(
            f"{path} is missing or empty. Run the find-risky-assumptions skill first; "
            "de-risking updates existing entries, it does not create the ledger."
        )
    data = yaml.safe_load(path.read_text()) or []
    if not isinstance(data, list):
        raise TypeError(
            f"Unexpected structure in {path}: expected a top-level YAML list of sections."
        )
    return data


def index_entries(doc: list) -> dict[str, dict]:
    """Map id -> the mutable entry dict, scanning every section's list."""
    by_id: dict[str, dict] = {}
    for item in doc:
        if not isinstance(item, dict):
            continue
        for value in item.values():
            if isinstance(value, list):
                for entry in value:
                    if isinstance(entry, dict) and "id" in entry:
                        by_id[str(entry["id"])] = entry
    return by_id


def normalize_confidence(raw) -> float:
    try:
        conf = float(raw)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"confidence must be a number, got {raw!r}") from exc
    if not (-1.0 <= conf <= 1.0):
        raise SystemExit(f"confidence must be between -1.00 and 1.00, got {conf}")
    return round(conf, 2)


def normalize_derisking(raw) -> list[dict]:
    """Validate the optional derisking block: a list of approach objects."""
    if not isinstance(raw, list):
        raise SystemExit("'derisking' must be a list of approach objects.")
    approaches: list[dict] = []
    for item in raw:
        if not isinstance(item, dict) or "approach" not in item:
            raise SystemExit(
                "Each 'derisking' item needs at least an 'approach' field."
            )
        approach: dict = {"approach": str(item["approach"]).strip()}
        if item.get("needs") is not None:
            approach["needs"] = str(item["needs"]).strip()
        if "blocked" in item:
            approach["blocked"] = bool(item["blocked"])
        approaches.append(approach)
    return approaches


def read_input(args) -> list:
    if args.json is not None:
        text = args.json
    elif args.input is not None:
        text = sys.stdin.read() if args.input == "-" else Path(args.input).read_text()
    else:
        raise SystemExit("Provide verdicts via --input <file|-> or --json '<...>'.")
    items = json.loads(text)
    if not isinstance(items, list):
        raise SystemExit("Input must be a JSON array of {id, confidence} verdicts.")
    return items


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--file", required=True, help="Path to risky-assumptions.yaml")
    parser.add_argument("--input", help="Path to JSON array file, or '-' for stdin")
    parser.add_argument("--json", help="Inline JSON array string")
    args = parser.parse_args()

    path = Path(args.file)
    items = read_input(args)
    if not items:
        print("No verdicts supplied; nothing to update.")
        return 0

    doc = load_doc(path)
    by_id = index_entries(doc)

    updated = []
    unknown_ids = []
    for raw in items:
        if not isinstance(raw, dict) or "id" not in raw or "confidence" not in raw:
            raise SystemExit(
                "Each verdict needs at least 'id' and 'confidence' fields."
            )
        rid = str(raw["id"])
        entry = by_id.get(rid)
        if entry is None:
            unknown_ids.append(rid)
            continue
        entry["confidence"] = normalize_confidence(raw["confidence"])
        if raw.get("derisking") is not None:
            entry["derisking"] = normalize_derisking(raw["derisking"])
        updated.append((rid, entry["confidence"]))

    if unknown_ids:
        raise SystemExit(
            "These ids were not found in the ledger (nothing was written): "
            + ", ".join(unknown_ids)
        )

    path.write_text(
        yaml.safe_dump(
            doc,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
            width=1000,
        )
    )

    print(f"Updated confidence on {len(updated)} assumption(s) in {path}:")
    for rid, conf in updated:
        state = "holds" if conf > 0 else "does NOT hold" if conf < 0 else "still open"
        print(f"  {rid}  confidence={conf:+.2f}  ({state})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
