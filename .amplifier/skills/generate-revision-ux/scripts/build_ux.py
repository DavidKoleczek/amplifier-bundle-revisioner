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

# Inlined into the JSON, so never listed again as a downloadable artifact.
RESERVED_FILES = {"spike-plan.md", "findings.md", "verdict.json", "status.json"}

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_LEDGER = "./.amplifier/revisioner/risky-assumptions.yaml"
DEFAULT_OUT = "./.amplifier/revisioner/ux"
DEFAULT_CLASSIFIER = ".amplifier/skills/vision-check-in/scripts/classify.py"


# --------------------------------------------------------------------------- reading


def read_text_or_none(path: Path) -> str | None:
    """File contents, or None when the file is absent or unreadable. Never a placeholder."""
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def read_json_or_none(path: Path) -> Any:
    """Parsed JSON, or None when the file is absent or malformed."""
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_sections(path: Path) -> dict[str, list]:
    """Return {section_key: [entries]} from the two-section ledger."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        raise SystemExit(
            f"Unexpected ledger structure in {path}: expected a top-level YAML list."
        )
    out: dict[str, list] = {CURRENT_KEY: [], PAST_KEY: []}
    for item in data:
        if isinstance(item, dict):
            for key, value in item.items():
                if key in out and isinstance(value, list):
                    out[key] = value
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


# -------------------------------------------------------------------------- evidence


def list_artifacts(spike_dir: Path) -> list[dict[str, Any]]:
    """Index every file in data/<id>/ except the four inlined ones.

    Paths are posix and relative to public/, so they resolve as ordinary links once the
    data tree has been copied to <out>/public/data/.
    """
    if not spike_dir.is_dir():
        return []
    artifacts: list[dict[str, Any]] = []
    for file_path in sorted(spike_dir.rglob("*")):
        if not file_path.is_file():
            continue
        relative = file_path.relative_to(spike_dir)
        if relative.as_posix() in RESERVED_FILES:
            continue
        artifacts.append(
            {
                "path": f"data/{spike_dir.name}/{relative.as_posix()}",
                "bytes": file_path.stat().st_size,
            }
        )
    artifacts.sort(key=lambda a: a["path"])
    return artifacts


def build_evidence(entries: list, data_dir: Path) -> dict[str, Any]:
    """One drill-down payload per current-vision assumption, keyed by id."""
    evidence: dict[str, Any] = {}
    for entry in entries:
        if not isinstance(entry, dict) or "id" not in entry:
            continue
        entry_id = str(entry["id"])
        spike_dir = data_dir / entry_id
        derisking = entry.get("derisking")
        evidence[entry_id] = {
            "spike_plan": read_text_or_none(spike_dir / "spike-plan.md"),
            "findings": read_text_or_none(spike_dir / "findings.md"),
            "verdict": read_json_or_none(spike_dir / "verdict.json"),
            "status": read_json_or_none(spike_dir / "status.json"),
            "derisking": derisking if isinstance(derisking, list) else [],
            "artifacts": list_artifacts(spike_dir),
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

    classification = run_classifier(classifier, ledger)
    sections = load_sections(ledger)
    evidence = build_evidence(sections[CURRENT_KEY], data_dir)

    try:
        vision_rel = vision_path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        vision_rel = vision_path.as_posix()

    state = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo": repo_root.name,
        "vision": {
            "path": vision_rel,
            "markdown": read_text_or_none(vision_path),
        },
        "classification": classification,
        "evidence": evidence,
        "past_assumptions": sections[PAST_KEY],
    }

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
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

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
