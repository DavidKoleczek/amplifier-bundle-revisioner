#!/usr/bin/env python3
"""Fixture tests for the vision-check-in scripts.

These are pure-Python, offline, deterministic tests -- no LLM, no network. They pin the
*mechanical* contract the three scripts must honor so the skill's judgment can rest on
them: how classify.py buckets assumptions and picks a mode, how the vision-drift check
fires, and that archive_assumptions.py moves entries verbatim.

The scripts are loaded by path (they live in ../scripts and are not an importable
package), and their section-key constants are read off the modules rather than retyped,
so the tests never hard-code the ledger's literal section names.

Run:  pytest .amplifier/skills/vision-check-in/tests/ -q
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

yaml = pytest.importorskip("yaml")

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


classify_mod = _load("classify")
stamp_mod = _load("stamp_vision")
archive_mod = _load("archive_assumptions")

CURRENT_KEY = classify_mod.CURRENT_KEY
PAST_KEY = archive_mod.PAST_KEY


# --------------------------------------------------------------------------- helpers


def write_status(data_dir: Path, entry_id: str, state: str) -> None:
    d = data_dir / entry_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "status.json").write_text(json.dumps({"state": state}))


def entry(entry_id: str, risk: float, confidence: float, **extra) -> dict:
    e = {
        "id": entry_id,
        "assumption": f"assumption {entry_id}",
        "risk": risk,
        "confidence": confidence,
    }
    e.update(extra)
    return e


def run_classify(entries: list[dict], data_dir: Path, drift=None) -> dict:
    return classify_mod.classify(
        {CURRENT_KEY: entries},
        data_dir,
        hold=0.7,
        fail=0.7,
        high_risk=0.7,
        drift=drift,
    )


def write_ledger(
    path: Path, current: list[dict], past: list[dict] | None = None
) -> None:
    doc: list = [{CURRENT_KEY: current}]
    if past is not None:
        doc.append({PAST_KEY: past})
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))


# ----------------------------------------------------------------------- classify modes


def test_all_clear_when_high_risk_holds(tmp_path):
    write_status(tmp_path, "RA-hold", "done")
    result = run_classify([entry("RA-hold", risk=0.9, confidence=0.85)], tmp_path)
    assert result["recommended_mode"] == "all_clear"
    assert result["counts"]["holds"] == 1


def test_pivot_when_high_risk_fails(tmp_path):
    write_status(tmp_path, "RA-fail", "done")
    result = run_classify([entry("RA-fail", risk=0.9, confidence=-0.8)], tmp_path)
    assert result["recommended_mode"] == "pivot"
    assert result["counts"]["fails"] == 1


def test_unblock_when_high_risk_blocked(tmp_path):
    write_status(tmp_path, "RA-block", "blocked")
    result = run_classify([entry("RA-block", risk=0.9, confidence=0.0)], tmp_path)
    assert result["recommended_mode"] == "unblock"
    assert result["counts"]["blocked"] == 1


def test_in_progress_when_spike_running(tmp_path):
    write_status(tmp_path, "RA-run", "running")
    result = run_classify([entry("RA-run", risk=0.9, confidence=0.0)], tmp_path)
    assert result["recommended_mode"] == "in_progress"
    assert result["counts"]["in_flight"] == 1


def test_running_spike_not_misreported_as_fail(tmp_path):
    # A running spike whose confidence is momentarily negative must stay in_flight,
    # never be surfaced as a realized risk.
    write_status(tmp_path, "RA-run", "running")
    result = run_classify([entry("RA-run", risk=0.9, confidence=-0.9)], tmp_path)
    assert result["counts"]["in_flight"] == 1
    assert result["counts"]["fails"] == 0


def test_pivot_outranks_unblock(tmp_path):
    write_status(tmp_path, "RA-fail", "done")
    write_status(tmp_path, "RA-block", "blocked")
    result = run_classify(
        [entry("RA-fail", 0.9, -0.8), entry("RA-block", 0.9, 0.0)], tmp_path
    )
    assert result["recommended_mode"] == "pivot"


def test_blocked_via_derisking_all_blocked_without_status(tmp_path):
    # No status.json, but every derisking approach is blocked -> blocked bucket.
    e = entry("RA-db", 0.9, 0.0, derisking=[{"needs": "repo access", "blocked": True}])
    result = run_classify([e], tmp_path)
    assert result["counts"]["blocked"] == 1
    assert result["buckets"]["blocked"][0]["needs"] == ["repo access"]


def test_low_risk_fail_does_not_trigger_pivot(tmp_path):
    write_status(tmp_path, "RA-lowfail", "done")
    result = run_classify([entry("RA-lowfail", risk=0.3, confidence=-0.9)], tmp_path)
    # It's a fail, but not load-bearing -> no pivot.
    assert result["recommended_mode"] != "pivot"
    assert result["counts"]["fails"] == 1


# ------------------------------------------------------------------------- drift / stale


def test_stale_outranks_everything(tmp_path):
    write_status(tmp_path, "RA-fail", "done")
    drift = {"checked": True, "stale": True, "stored": "aaa", "current": "bbb"}
    result = run_classify([entry("RA-fail", 0.9, -0.8)], tmp_path, drift=drift)
    assert result["recommended_mode"] == "stale"
    assert result["vision_drift"]["stale"] is True


def test_check_drift_unstamped_is_not_stale(tmp_path):
    ledger = tmp_path / "led.yaml"
    vision = tmp_path / "vision.md"
    write_ledger(ledger, [entry("RA-x", 0.9, 0.0)])
    vision.write_text("vision text")
    drift = classify_mod.check_drift(ledger, vision)
    assert drift["checked"] is False
    assert drift["stale"] is False


def test_check_drift_missing_vision_is_not_stale(tmp_path):
    ledger = tmp_path / "led.yaml"
    write_ledger(ledger, [entry("RA-x", 0.9, 0.0)])
    drift = classify_mod.check_drift(ledger, tmp_path / "nope.md")
    assert drift["checked"] is False
    assert drift["stale"] is False


def test_stamp_then_match_then_mismatch(tmp_path):
    ledger = tmp_path / "led.yaml"
    vision = tmp_path / "vision.md"
    write_ledger(ledger, [entry("RA-x", 0.9, 0.0)])
    vision.write_text("original vision")

    # Stamp, then the ledger matches the current vision.
    doc = stamp_mod.load_doc(ledger)
    assert stamp_mod.stored_hash(doc) is None
    # Drive the stamp through its CLI entry so we test the real write path.
    import sys

    argv = sys.argv
    sys.argv = ["stamp_vision.py", "--file", str(ledger), "--vision", str(vision)]
    try:
        assert stamp_mod.main() == 0
    finally:
        sys.argv = argv

    drift = classify_mod.check_drift(ledger, vision)
    assert drift["checked"] is True
    assert drift["stale"] is False

    # Change the vision -> stale fires.
    vision.write_text("original vision -- with an edit")
    drift = classify_mod.check_drift(ledger, vision)
    assert drift["checked"] is True
    assert drift["stale"] is True


def test_stamp_preserves_existing_meta_keys(tmp_path):
    ledger = tmp_path / "led.yaml"
    vision = tmp_path / "vision.md"
    doc = [
        {stamp_mod.META_KEY: {"owner": "team-x"}},
        {CURRENT_KEY: [entry("RA-x", 0.9, 0.0)]},
    ]
    ledger.write_text(yaml.safe_dump(doc, sort_keys=False))
    vision.write_text("v")

    import sys

    argv = sys.argv
    sys.argv = ["stamp_vision.py", "--file", str(ledger), "--vision", str(vision)]
    try:
        assert stamp_mod.main() == 0
    finally:
        sys.argv = argv

    meta = stamp_mod.find_meta(stamp_mod.load_doc(ledger))
    assert meta["owner"] == "team-x"  # untouched
    assert meta["vision_sha256"] == stamp_mod.vision_sha256(vision)


def test_stamped_ledger_still_classifies_normally(tmp_path):
    # A revisioner_meta section must not pollute the assumption buckets.
    ledger = tmp_path / "led.yaml"
    doc = [
        {stamp_mod.META_KEY: {"vision_sha256": "abc"}},
        {CURRENT_KEY: [entry("RA-x", 0.9, 0.85)]},
    ]
    ledger.write_text(yaml.safe_dump(doc, sort_keys=False))
    sections = classify_mod.load_sections(ledger)
    assert len(sections[CURRENT_KEY]) == 1


# ------------------------------------------------------------------------------ archive


def _run_archive(ledger: Path, ids: str, note: str | None = None) -> int:
    import sys

    argv = sys.argv
    sys.argv = ["archive_assumptions.py", "--file", str(ledger), "--ids", ids]
    if note:
        sys.argv += ["--note", note]
    try:
        return archive_mod.main()
    finally:
        sys.argv = argv


def test_archive_moves_entry_verbatim(tmp_path):
    ledger = tmp_path / "led.yaml"
    moved = entry("RA-move", 0.9, -0.8, derisking=[{"needs": "x", "blocked": False}])
    kept = entry("RA-keep", 0.5, 0.2)
    write_ledger(ledger, [moved, kept], past=[])

    assert _run_archive(ledger, "RA-move", note="pivot: pull model") == 0

    sections = classify_mod.load_sections(ledger)
    current_ids = [e["id"] for e in sections[CURRENT_KEY]]
    past = sections[PAST_KEY]
    assert current_ids == ["RA-keep"]
    assert len(past) == 1
    m = past[0]
    # Verbatim: risk, confidence, derisking all preserved; only archived_note added.
    assert m["id"] == "RA-move"
    assert m["risk"] == 0.9
    assert m["confidence"] == -0.8
    assert m["derisking"] == [{"needs": "x", "blocked": False}]
    assert m["archived_note"] == "pivot: pull model"


def test_archive_leaves_untouched_entries_alone(tmp_path):
    ledger = tmp_path / "led.yaml"
    a = entry("RA-a", 0.9, -0.8)
    b = entry("RA-b", 0.4, 0.1)
    write_ledger(ledger, [a, b], past=[])
    _run_archive(ledger, "RA-a")
    sections = classify_mod.load_sections(ledger)
    kept = sections[CURRENT_KEY][0]
    assert kept == {
        "id": "RA-b",
        "assumption": "assumption RA-b",
        "risk": 0.4,
        "confidence": 0.1,
    }


def test_archive_unknown_id_raises(tmp_path):
    ledger = tmp_path / "led.yaml"
    write_ledger(ledger, [entry("RA-a", 0.9, -0.8)], past=[])
    with pytest.raises(SystemExit):
        _run_archive(ledger, "RA-nonexistent")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
