#!/usr/bin/env python3
"""Stamp a risky-assumptions ledger with the fingerprint of the vision it was built from.

The ledger's assumptions are bets a *specific* version of the vision makes. If the
vision text later changes -- through an approved pivot, or edited out-of-band -- those
bets may no longer describe the current vision, and a check-in run against them would
be silently stale. To make that detectable, whoever generates or regenerates the ledger
records a hash of the vision here; `classify.py` compares it on every check-in.

The fingerprint lives in its own top-level list item so it never collides with the
assumption sections and older readers ignore it:

    - revisioner_meta:
        vision_sha256: <hex>
        vision_path: .amplifier/revisioner/vision.md
        stamped_at: <iso8601>

Called by `find-risky-assumptions` right after it writes the ledger, and by
`vision-check-in` after an approved pivot regenerates the ledger.

Usage:
    python3 stamp_vision.py --file <ledger> [--vision <vision.md>]
    python3 stamp_vision.py --file <ledger> --print   # show stored vs current, write nothing
"""

from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml  # PyYAML
except ImportError:  # pragma: no cover
    import sys

    sys.stderr.write("PyYAML is required (pip install pyyaml).\n")
    sys.exit(2)

META_KEY = "revisioner_meta"


def vision_sha256(vision_path: Path) -> str:
    """Hash the vision bytes. Whitespace and all -- byte-exact is the honest signal."""
    return hashlib.sha256(vision_path.read_bytes()).hexdigest()


def load_doc(path: Path) -> list:
    if not path.exists() or path.stat().st_size == 0:
        raise SystemExit(f"Ledger not found or empty: {path}")
    data = yaml.safe_load(path.read_text()) or []
    if not isinstance(data, list):
        raise SystemExit(
            f"Unexpected ledger structure in {path}: expected a top-level list."
        )
    return data


def find_meta(doc: list) -> dict | None:
    for item in doc:
        if isinstance(item, dict) and META_KEY in item:
            block = item[META_KEY]
            return block if isinstance(block, dict) else None
    return None


def stored_hash(doc: list) -> str | None:
    meta = find_meta(doc)
    return (
        str(meta.get("vision_sha256")) if meta and meta.get("vision_sha256") else None
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--file", required=True, help="Path to risky-assumptions.yaml")
    parser.add_argument(
        "--vision",
        default=None,
        help="Path to vision.md (default: <ledger dir>/vision.md)",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        dest="print_only",
        help="Show stored vs current fingerprint and exit without writing.",
    )
    args = parser.parse_args()

    path = Path(args.file)
    vision = Path(args.vision) if args.vision else path.parent / "vision.md"
    doc = load_doc(path)

    if not vision.exists():
        raise SystemExit(f"Vision file not found: {vision}")
    current = vision_sha256(vision)

    if args.print_only:
        prev = stored_hash(doc)
        state = "match" if prev == current else ("MISMATCH" if prev else "unstamped")
        print(f"stored : {prev or '(none)'}")
        print(f"current: {current}")
        print(f"vision : {vision}")
        print(f"state  : {state}")
        return 0

    # Upsert the meta block, preserving any other keys already there.
    meta = find_meta(doc)
    if meta is None:
        meta = {}
        doc.insert(0, {META_KEY: meta})
    meta["vision_sha256"] = current
    try:
        meta["vision_path"] = str(vision.relative_to(Path.cwd()))
    except ValueError:
        meta["vision_path"] = str(vision)
    meta["stamped_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    path.write_text(
        yaml.safe_dump(
            doc,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
            width=1000,
        )
    )
    print(f"Stamped {path} with vision fingerprint {current[:12]}... ({vision})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
