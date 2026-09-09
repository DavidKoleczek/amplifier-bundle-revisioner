#!/usr/bin/env python3
"""Append newly found risky assumptions to a revisioner risky-assumptions.yaml file.

Design goals:
- Generate collision-free ids of the form "RA-" + 6 base62 chars (0-9 a-z A-Z).
- Only ADD entries. Never modify, re-score, or reorder existing ones.
- Preserve the file's two-section shape:
    - assumptions_related_to_current_vision
    - assumptions_related_to_past_visions
- New assumptions are always born untested, with confidence: 0.0.

Two independent axes per assumption:
    - risk       importance/stakes only: how much the vision's success depends on
                 this being true. 0.00-1.00. Set here and does not move.
    - confidence signed belief that the assumption holds, -1.00..+1.00:
                 +1 confident it holds (validated -> de-risked),
                  0 untested / no evidence (where new assumptions start),
                 -1 confident it does not hold (invalidated -> risk realized).
                 Moved later by the separate de-risking skill, not here.

Input is a JSON array of objects, each with:
    {"assumption": "<text>", "risk": <float 0.00-1.00>}

Usage:
    python3 add_assumptions.py --file <path> --input <new_assumptions.json>
    python3 add_assumptions.py --file <path> --json '[{"assumption": "...", "risk": 0.8}]'
    cat new.json | python3 add_assumptions.py --file <path> --input -

Options:
    --section {current,past}   Which section to append to (default: current).
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from pathlib import Path

try:
    import yaml  # PyYAML
except ImportError:  # pragma: no cover
    sys.stderr.write(
        "PyYAML is required (pip install pyyaml), or edit the YAML by hand.\n"
    )
    sys.exit(2)

BASE62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
CURRENT_KEY = "assumptions_related_to_current_vision"
PAST_KEY = "assumptions_related_to_past_visions"


def gen_id(existing: set[str]) -> str:
    """Return a unique 'RA-' + 6 base62 id not already present."""
    for _ in range(10000):
        candidate = "RA-" + "".join(secrets.choice(BASE62) for _ in range(6))
        if candidate not in existing:
            existing.add(candidate)
            return candidate
    raise RuntimeError("Could not generate a unique id (id space exhausted?)")


def load_doc(path: Path) -> list:
    """Load the top-level list, creating an empty skeleton if the file is absent/empty."""
    if not path.exists() or path.stat().st_size == 0:
        return [{CURRENT_KEY: []}, {PAST_KEY: []}]
    data = yaml.safe_load(path.read_text()) or []
    if not isinstance(data, list):
        raise TypeError(
            f"Unexpected structure in {path}: expected a top-level YAML list of sections."
        )
    return data


def section_list(doc: list, key: str) -> list:
    """Find (or create) the list held under a section key in the top-level list."""
    for item in doc:
        if isinstance(item, dict) and key in item:
            if item[key] is None:
                item[key] = []
            return item[key]
    # Section missing entirely — append it.
    new_section: dict = {key: []}
    doc.append(new_section)
    return new_section[key]


def collect_existing_ids(doc: list) -> set[str]:
    ids: set[str] = set()
    for item in doc:
        if not isinstance(item, dict):
            continue
        for value in item.values():
            if isinstance(value, list):
                for entry in value:
                    if isinstance(entry, dict) and "id" in entry:
                        ids.add(str(entry["id"]))
    return ids


def collect_existing_texts(doc: list) -> set[str]:
    """Normalized existing assumption texts, for a duplicate-guard safety net."""
    texts: set[str] = set()
    for item in doc:
        if not isinstance(item, dict):
            continue
        for value in item.values():
            if isinstance(value, list):
                for entry in value:
                    if isinstance(entry, dict) and "assumption" in entry:
                        texts.add(str(entry["assumption"]).strip().lower())
    return texts


def normalize_risk(raw) -> float:
    risk = float(raw)
    if not (0.0 <= risk <= 1.0):
        raise ValueError(f"risk must be between 0.00 and 1.00, got {risk}")
    return round(risk, 2)


def read_input(args) -> list:
    if args.json is not None:
        text = args.json
    elif args.input is not None:
        text = sys.stdin.read() if args.input == "-" else Path(args.input).read_text()
    else:
        raise SystemExit(
            "Provide new assumptions via --input <file|-> or --json '<...>'."
        )
    items = json.loads(text)
    if not isinstance(items, list):
        raise SystemExit("Input must be a JSON array of {assumption, risk} objects.")
    return items


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--file", required=True, help="Path to risky-assumptions.yaml")
    parser.add_argument("--input", help="Path to JSON array file, or '-' for stdin")
    parser.add_argument("--json", help="Inline JSON array string")
    parser.add_argument("--section", choices=["current", "past"], default="current")
    args = parser.parse_args()

    path = Path(args.file)
    items = read_input(args)
    if not items:
        print("No new assumptions supplied; nothing to write.")
        return 0

    doc = load_doc(path)
    existing_ids = collect_existing_ids(doc)
    existing_texts = collect_existing_texts(doc)
    key = CURRENT_KEY if args.section == "current" else PAST_KEY
    target = section_list(doc, key)

    added = []
    skipped = []
    for raw in items:
        if not isinstance(raw, dict) or "assumption" not in raw or "risk" not in raw:
            raise SystemExit("Each item needs 'assumption' and 'risk' fields.")
        assumption = str(raw["assumption"]).strip()
        if not assumption:
            raise SystemExit("Empty 'assumption' text is not allowed.")
        if assumption.lower() in existing_texts:
            # Safety net only — de-duplication is the caller's job. Skip exact repeats.
            skipped.append(assumption)
            continue
        existing_texts.add(assumption.lower())
        entry = {
            "id": gen_id(existing_ids),
            "assumption": assumption,
            "risk": normalize_risk(raw["risk"]),
            "confidence": 0.0,
        }
        target.append(entry)
        added.append(entry)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            doc,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
            width=1000,
        )
    )

    if not added:
        print("No new assumptions written (all supplied items already exist).")
    else:
        print(f"Added {len(added)} assumption(s) to '{key}' in {path}:")
        for e in added:
            print(f"  {e['id']}  risk={e['risk']:.2f}  {e['assumption']}")
    for text in skipped:
        print(f"  SKIPPED (already present): {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
