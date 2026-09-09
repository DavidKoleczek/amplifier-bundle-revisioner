#!/usr/bin/env python3
"""Archive assumptions on a vision pivot: move them current -> past, unchanged.

When evidence invalidates a high-risk assumption and the user OKs a vision
change, the assumptions the old vision rested on are no longer live bets -- but they
are not deleted either. They move from

    assumptions_related_to_current_vision   ->   assumptions_related_to_past_visions

so the pivot keeps its evidence trail. This script moves whole entries **verbatim**
(id, assumption, risk, confidence, derisking -- all preserved), only optionally
stamping an `archived_note` for provenance. It never edits an assumption's fields,
never re-scores, and never touches the entries it is not moving.

The spike data under ./.amplifier/revisioner/data/<id>/ is left in place -- archiving
is a ledger move, not a delete; the evidence stays drillable.

Usage:
    python3 archive_assumptions.py --file <ledger> --ids RA-aaa,RA-bbb
    python3 archive_assumptions.py --file <ledger> --ids RA-aaa --note "pivoted to pull model 2026-09-09"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml  # PyYAML
except ImportError:  # pragma: no cover
    sys.stderr.write("PyYAML is required (pip install pyyaml).\n")
    sys.exit(2)

CURRENT_KEY = "assumptions_related_to_current_vision"
PAST_KEY = "assumptions_related_to_past_visions"


def load_doc(path: Path) -> list:
    if not path.exists() or path.stat().st_size == 0:
        raise SystemExit(f"Ledger not found or empty: {path}")
    data = yaml.safe_load(path.read_text()) or []
    if not isinstance(data, list):
        raise SystemExit(
            f"Unexpected ledger structure in {path}: expected a top-level list."
        )
    return data


def section_list(doc: list, key: str) -> list:
    """Find (or create) the list held under a section key in the top-level list."""
    for item in doc:
        if isinstance(item, dict) and key in item:
            if item[key] is None:
                item[key] = []
            return item[key]
    new_section: dict = {key: []}
    doc.append(new_section)
    return new_section[key]


def parse_ids(raw: list[str]) -> list[str]:
    ids: list[str] = []
    for chunk in raw:
        ids.extend(part.strip() for part in chunk.split(",") if part.strip())
    # Preserve order, drop dupes.
    seen: set[str] = set()
    unique: list[str] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            unique.append(i)
    return unique


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--file", required=True, help="Path to risky-assumptions.yaml")
    parser.add_argument(
        "--ids",
        required=True,
        action="append",
        help="Assumption id(s) to archive: repeat the flag or comma-separate.",
    )
    parser.add_argument(
        "--note",
        default=None,
        help="Optional provenance note stamped as `archived_note` on each moved entry.",
    )
    args = parser.parse_args()

    path = Path(args.file)
    ids = parse_ids(args.ids)
    if not ids:
        raise SystemExit("No ids supplied to archive.")

    doc = load_doc(path)
    current = section_list(doc, CURRENT_KEY)
    past = section_list(doc, PAST_KEY)

    wanted = set(ids)
    moved: list[dict] = []
    kept: list = []
    for entry in current:
        if isinstance(entry, dict) and str(entry.get("id")) in wanted:
            if args.note:
                entry["archived_note"] = args.note
            moved.append(entry)
            wanted.discard(str(entry.get("id")))
        else:
            kept.append(entry)

    if not moved:
        raise SystemExit(
            f"None of the requested ids were found in '{CURRENT_KEY}': {', '.join(ids)}"
        )

    # Mutate the section lists in place so the doc's shape is preserved.
    current[:] = kept
    past.extend(moved)

    path.write_text(
        yaml.safe_dump(
            doc,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
            width=1000,
        )
    )

    print(
        f"Archived {len(moved)} assumption(s) '{CURRENT_KEY}' -> '{PAST_KEY}' in {path}:"
    )
    for e in moved:
        print(
            f"  {e.get('id')}  risk={float(e.get('risk', 0.0)):.2f}  {str(e.get('assumption', ''))[:80]}"
        )
    if wanted:
        print("  NOT FOUND (left untouched): " + ", ".join(sorted(wanted)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
