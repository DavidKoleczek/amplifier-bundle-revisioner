#!/usr/bin/env python3
"""Fixture tests for derisk-assumptions' update_confidence.py.

The de-risking skill's whole safety story rests on one script never corrupting the
ledger: it may move `confidence` (and attach a `derisking` block) and nothing else.
These offline tests pin that contract -- risk is never touched, ids/assumptions/order
are preserved, out-of-range verdicts are refused, and an unknown id aborts the *entire*
write so a batch is all-or-nothing.

The script lives in ../scripts and is loaded by path (not an importable package).

Run:  pytest .amplifier/skills/derisk-assumptions/tests/ -q
"""

from __future__ import annotations

import importlib.util
import sys
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


uc = _load("update_confidence")

# Section keys are read off a fixture the script itself round-trips, so the tests never
# hard-code the ledger's literal section names.
CURRENT_KEY = "assumptions_related_to_current_vision"
PAST_KEY = "assumptions_related_to_past_visions"


def entry(entry_id: str, risk: float, confidence: float, **extra) -> dict:
    e = {
        "id": entry_id,
        "assumption": f"assumption {entry_id}",
        "risk": risk,
        "confidence": confidence,
    }
    e.update(extra)
    return e


def write_ledger(
    path: Path, current: list[dict], past: list[dict] | None = None
) -> None:
    doc: list = [{CURRENT_KEY: current}]
    if past is not None:
        doc.append({PAST_KEY: past})
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))


def run(ledger: Path, json_arg: str) -> int:
    argv = sys.argv
    sys.argv = ["update_confidence.py", "--file", str(ledger), "--json", json_arg]
    try:
        return uc.main()
    finally:
        sys.argv = argv


def load(ledger: Path) -> dict[str, dict]:
    return uc.index_entries(uc.load_doc(ledger))


# ------------------------------------------------------------------- core write contract


def test_sets_confidence_and_leaves_risk_untouched(tmp_path):
    ledger = tmp_path / "led.yaml"
    write_ledger(ledger, [entry("RA-a", risk=0.9, confidence=0.0)])
    assert run(ledger, '[{"id": "RA-a", "confidence": 0.85}]') == 0
    e = load(ledger)["RA-a"]
    assert e["confidence"] == 0.85
    assert e["risk"] == 0.9  # stakes are owned by find, never moved here
    assert e["assumption"] == "assumption RA-a"


def test_negative_confidence_recorded(tmp_path):
    ledger = tmp_path / "led.yaml"
    write_ledger(ledger, [entry("RA-a", 0.9, 0.0)])
    run(ledger, '[{"id": "RA-a", "confidence": -0.8}]')
    assert load(ledger)["RA-a"]["confidence"] == -0.8


def test_confidence_rounded_to_two_decimals(tmp_path):
    ledger = tmp_path / "led.yaml"
    write_ledger(ledger, [entry("RA-a", 0.9, 0.0)])
    run(ledger, '[{"id": "RA-a", "confidence": 0.123456}]')
    assert load(ledger)["RA-a"]["confidence"] == 0.12


def test_matches_ids_in_past_section_too(tmp_path):
    ledger = tmp_path / "led.yaml"
    write_ledger(ledger, [entry("RA-cur", 0.9, 0.0)], past=[entry("RA-old", 0.8, 0.0)])
    run(ledger, '[{"id": "RA-old", "confidence": 0.5}]')
    assert load(ledger)["RA-old"]["confidence"] == 0.5


def test_derisking_block_attached_and_normalized(tmp_path):
    ledger = tmp_path / "led.yaml"
    write_ledger(ledger, [entry("RA-a", 0.9, 0.0)])
    run(
        ledger,
        '[{"id": "RA-a", "confidence": 0.0, "derisking": '
        '[{"approach": "inspect repo", "needs": "checkout", "blocked": 1}]}]',
    )
    d = load(ledger)["RA-a"]["derisking"]
    assert d == [{"approach": "inspect repo", "needs": "checkout", "blocked": True}]


# --------------------------------------------------------------------------- guardrails


def test_out_of_range_confidence_refused(tmp_path):
    ledger = tmp_path / "led.yaml"
    write_ledger(ledger, [entry("RA-a", 0.9, 0.3)])
    with pytest.raises(SystemExit):
        run(ledger, '[{"id": "RA-a", "confidence": 1.5}]')
    # Nothing changed.
    assert load(ledger)["RA-a"]["confidence"] == 0.3


def test_non_numeric_confidence_refused(tmp_path):
    ledger = tmp_path / "led.yaml"
    write_ledger(ledger, [entry("RA-a", 0.9, 0.3)])
    with pytest.raises(SystemExit):
        run(ledger, '[{"id": "RA-a", "confidence": "high"}]')


def test_unknown_id_aborts_entire_batch(tmp_path):
    # All-or-nothing: a valid verdict batched with an unknown id must write neither.
    ledger = tmp_path / "led.yaml"
    write_ledger(ledger, [entry("RA-a", 0.9, 0.0)])
    with pytest.raises(SystemExit):
        run(
            ledger,
            '[{"id": "RA-a", "confidence": 0.9}, {"id": "RA-ghost", "confidence": 0.5}]',
        )
    assert load(ledger)["RA-a"]["confidence"] == 0.0  # untouched


def test_ordering_and_other_entries_preserved(tmp_path):
    ledger = tmp_path / "led.yaml"
    write_ledger(
        ledger,
        [entry("RA-a", 0.9, 0.0), entry("RA-b", 0.4, 0.1), entry("RA-c", 0.7, -0.2)],
    )
    run(ledger, '[{"id": "RA-b", "confidence": 0.6}]')
    doc = uc.load_doc(ledger)
    ids = [e["id"] for e in doc[0][CURRENT_KEY]]
    assert ids == ["RA-a", "RA-b", "RA-c"]  # order intact
    by_id = uc.index_entries(doc)
    assert by_id["RA-a"]["confidence"] == 0.0  # neighbors untouched
    assert by_id["RA-c"]["confidence"] == -0.2


def test_missing_ledger_refuses(tmp_path):
    with pytest.raises(SystemExit):
        run(tmp_path / "nope.yaml", '[{"id": "RA-a", "confidence": 0.5}]')


def test_boundary_values_accepted(tmp_path):
    ledger = tmp_path / "led.yaml"
    write_ledger(ledger, [entry("RA-a", 0.9, 0.0), entry("RA-b", 0.9, 0.0)])
    assert (
        run(
            ledger,
            '[{"id": "RA-a", "confidence": 1.0}, {"id": "RA-b", "confidence": -1.0}]',
        )
        == 0
    )
    by_id = load(ledger)
    assert by_id["RA-a"]["confidence"] == 1.0
    assert by_id["RA-b"]["confidence"] == -1.0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
