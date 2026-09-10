"""Synthetic, offline tests for the dashboard builder and its classifier boundary."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml


SKILL_DIR = Path(__file__).resolve().parent.parent
CLASSIFIER = SKILL_DIR.parent / "vision-check-in" / "scripts" / "classify.py"
spec = importlib.util.spec_from_file_location("build_ux", SKILL_DIR / "scripts" / "build_ux.py")
assert spec and spec.loader
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def entry(entry_id="probe-1", **extra):
    return {"id": entry_id, "assumption": f"Assumption {entry_id}", **extra}


def write_ledger(path, current, past=None):
    document = [{builder.CURRENT_KEY: current}]
    if past is not None:
        document.append({builder.PAST_KEY: past})
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def write_spike(ledger, name, content, entry_id="probe-1"):
    path = ledger.parent / "data" / entry_id / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
    return path


def snapshot(root):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*") if path.is_file()
    }


@pytest.fixture
def workspace(tmp_path):
    source = tmp_path / "project" / ".amplifier" / "revisioner"
    source.mkdir(parents=True)
    ledger = source / "risky-assumptions.yaml"
    write_ledger(ledger, [entry()])
    out = tmp_path / "dashboard"
    (out / "public" / "data").mkdir(parents=True)
    (out / "index.html").write_text("existing template")
    (out / "public" / "data" / "old.txt").write_text("existing artifact")
    (out / "public" / "revision-state.json").write_text('{"existing": true}')
    return ledger, out


def invoke(monkeypatch, ledger, out, *, data_only=True):
    argv = [
        "build_ux.py", "--file", str(ledger), "--out", str(out),
        "--classifier", str(CLASSIFIER),
    ]
    if data_only:
        argv.append("--data-only")
    monkeypatch.setattr(sys, "argv", argv)
    assert builder.main() == 0
    return json.loads((out / "public" / "revision-state.json").read_text())


def assert_rejected(monkeypatch, ledger, out, match):
    before = snapshot(out)
    with pytest.raises(SystemExit, match=match):
        invoke(monkeypatch, ledger, out, data_only=False)
    assert snapshot(out) == before


def test_ledger_only_uses_classifier_defaults_and_preserves_source(workspace, monkeypatch):
    ledger, out = workspace
    before = snapshot(ledger.parent)
    expected = builder.run_classifier(CLASSIFIER, ledger)
    state = invoke(monkeypatch, ledger, out)
    assert state["classification"] == expected
    assert state["classification"]["rows"][0]["risk"] == 0
    assert state["classification"]["rows"][0]["confidence"] == 0
    assert state["vision"]["markdown"] is None
    assert state["evidence"]["probe-1"] == {
        "spike_plan": None, "findings": None, "verdict": None, "status": None,
        "derisking": [], "artifacts": [],
    }
    assert state["past_assumptions"] == []
    assert "warnings" not in state
    assert snapshot(ledger.parent) == before
    assert (out / "index.html").read_text() == "existing template"
    assert not (out / "public" / "data").exists()


def test_missing_and_empty_text_are_distinct(workspace, monkeypatch):
    ledger, out = workspace
    write_spike(ledger, "findings.md", "")
    (ledger.parent / "vision.md").write_text("")
    state = invoke(monkeypatch, ledger, out)
    assert state["vision"]["markdown"] == ""
    assert state["evidence"]["probe-1"]["findings"] == ""
    assert state["evidence"]["probe-1"]["spike_plan"] is None
    assert "warnings" not in state


def test_approaches_nested_artifacts_past_entries_and_template(workspace, monkeypatch):
    ledger, out = workspace
    approaches = [
        {"approach": "Run a probe", "blocked": True, "needs": "A sample", "extra": 1},
        {"approach": "Inspect a source", "blocked": False},
    ]
    past = [entry("past_v1.2", confidence=None, archived_note="Replaced premise", extra={"n": 2})]
    write_ledger(ledger, [
        entry(risk=0.8, confidence=-0.8, derisking=approaches, additive="accepted"),
        entry("other", risk=None, confidence=None, derisking=None),
    ], past)
    write_spike(ledger, "status.json", '{"state":"running","updated":"test-clock"}')
    write_spike(ledger, "findings.md", "# Evidence\nA synthetic observation.")
    write_spike(ledger, "verdict.json", '{"confidence":-0.8}')
    nested = write_spike(ledger, "output/nested/raw.bin", b"\x00\xff")
    write_spike(ledger, "output/findings.md", "Nested artifact")
    before = snapshot(ledger.parent)
    expected = builder.run_classifier(CLASSIFIER, ledger)
    state = invoke(monkeypatch, ledger, out, data_only=False)
    assert state["classification"] == expected
    assert state["classification"]["rows"][0]["category"] == "in_flight"
    assert state["evidence"]["probe-1"]["derisking"] == approaches
    assert state["evidence"]["other"]["derisking"] == []
    assert state["past_assumptions"] == past
    assert state["evidence"]["probe-1"]["artifacts"] == [
        {"path": "data/probe-1/output/findings.md", "bytes": len("Nested artifact")},
        {"path": "data/probe-1/output/nested/raw.bin", "bytes": 2},
    ]
    assert (out / "public" / "data" / nested.relative_to(ledger.parent / "data")).read_bytes() == b"\x00\xff"
    assert (out / "package.json").is_file()
    assert snapshot(ledger.parent) == before


@pytest.mark.parametrize("verdict", [
    {"id": "probe-1", "confidence": 0.7},
    {"id": "probe-1", "derisking": [{"blocked": True, "needs": "A sample"}]},
    {"summary": {"nested": ["An observation", 1]}, "extra": None},
])
def test_valid_verdict_shapes_remain_verbatim(workspace, monkeypatch, verdict):
    ledger, out = workspace
    write_spike(ledger, "verdict.json", json.dumps(verdict))
    state = invoke(monkeypatch, ledger, out)
    assert state["evidence"]["probe-1"]["verdict"] == verdict
    assert state["evidence"]["probe-1"]["artifacts"] == []
    assert "warnings" not in state


@pytest.mark.parametrize("raw", [
    b"{", b"", b"null", b"[]", b'"text"', b"\xff",
    b'{"confidence": NaN}', b'{"confidence": 1e999}',
])
def test_malformed_verdict_warns_and_retains_raw_access(workspace, monkeypatch, raw):
    ledger, out = workspace
    write_spike(ledger, "verdict.json", raw)
    before = snapshot(ledger.parent)
    state = invoke(monkeypatch, ledger, out)
    assert state["evidence"]["probe-1"]["verdict"] is None
    assert state["evidence"]["probe-1"]["artifacts"] == [
        {"path": "data/probe-1/verdict.json", "bytes": len(raw)}
    ]
    assert state["warnings"][0]["path"] == "data/probe-1/verdict.json"
    assert "Cannot inline verdict" in state["warnings"][0]["message"]
    assert (out / "public" / "data" / "probe-1" / "verdict.json").read_bytes() == raw
    assert snapshot(ledger.parent) == before


@pytest.mark.parametrize("raw", [
    b"{", b"", b"null", b"[]", b"{}", b"\xff",
    b'{"state":"open"}', b'{"state":true}', b'{"state":null}',
    b'{"state":"running","updated":2}', b'{"state":"done","extra":NaN}',
])
def test_malformed_status_fails_before_output(workspace, monkeypatch, raw):
    ledger, out = workspace
    write_spike(ledger, "status.json", raw)
    assert_rejected(monkeypatch, ledger, out, r"status.json: invalid status")


@pytest.mark.parametrize("state_name", ["running", "done", "blocked"])
def test_valid_status_is_preserved(workspace, monkeypatch, state_name):
    ledger, out = workspace
    status = {"state": state_name, "extra": {"source": "synthetic"}}
    write_spike(ledger, "status.json", json.dumps(status))
    expected = builder.run_classifier(CLASSIFIER, ledger)
    state = invoke(monkeypatch, ledger, out)
    assert state["classification"] == expected
    assert state["evidence"]["probe-1"]["status"] == status


@pytest.mark.parametrize("filename", ["vision.md", "findings.md", "spike-plan.md"])
def test_invalid_utf8_text_warns(workspace, monkeypatch, filename):
    ledger, out = workspace
    if filename == "vision.md":
        (ledger.parent / filename).write_bytes(b"\xff")
    else:
        write_spike(ledger, filename, b"\xff")
    state = invoke(monkeypatch, ledger, out)
    assert len(state["warnings"]) == 1
    assert "Cannot read text" in state["warnings"][0]["message"]
    if filename == "vision.md":
        assert state["vision"]["markdown"] is None
        assert state["warnings"][0]["path"] == "vision.md"
    else:
        field = "findings" if filename == "findings.md" else "spike_plan"
        assert state["evidence"]["probe-1"][field] is None
        assert state["evidence"]["probe-1"]["artifacts"][0]["path"].endswith(filename)


@pytest.mark.parametrize("filename", [
    "risky-assumptions.yaml", "vision.md", "status.json", "verdict.json", "findings.md",
])
def test_permission_errors_propagate_without_output(workspace, monkeypatch, filename):
    ledger, out = workspace
    read_text = Path.read_text

    def denied(path, *args, **kwargs):
        if path.name == filename:
            raise PermissionError(f"denied: {filename}")
        return read_text(path, *args, **kwargs)

    before = snapshot(out)
    monkeypatch.setattr(Path, "read_text", denied)
    with pytest.raises(PermissionError, match="denied"):
        invoke(monkeypatch, ledger, out, data_only=False)
    assert snapshot(out) == before


@pytest.mark.parametrize("entry_id", ["", "..", "../escape", "/absolute", "a/b", "a\\b", "a?b", "a#b", "a b", 7, None])
def test_invalid_ids_fail(workspace, monkeypatch, entry_id):
    ledger, out = workspace
    write_ledger(ledger, [entry(entry_id)])
    assert_rejected(monkeypatch, ledger, out, "id must be")


@pytest.mark.parametrize("in_past", [False, True])
def test_duplicate_ids_fail_across_sections(workspace, monkeypatch, in_past):
    ledger, out = workspace
    write_ledger(ledger, [entry()] if in_past else [entry(), entry()], [entry()] if in_past else [])
    assert_rejected(monkeypatch, ledger, out, "duplicate id")


@pytest.mark.parametrize("axis,value", [
    ("risk", -0.1), ("risk", 1.1), ("confidence", -1.1), ("confidence", 1.1),
    ("risk", True), ("confidence", False), ("risk", "0.8"), ("confidence", []),
    ("risk", float("nan")), ("confidence", float("inf")), ("risk", float("-inf")),
])
def test_invalid_axes_fail(workspace, monkeypatch, axis, value):
    ledger, out = workspace
    write_ledger(ledger, [entry(**{axis: value})])
    assert_rejected(monkeypatch, ledger, out, f"{axis} must be a finite number")


@pytest.mark.parametrize("value", ["", "  ", 1, None])
def test_nonempty_assumption_text_required(workspace, monkeypatch, value):
    ledger, out = workspace
    write_ledger(ledger, [entry(assumption=value)])
    assert_rejected(monkeypatch, ledger, out, "assumption must be nonempty text")


@pytest.mark.parametrize("derisking", [
    {}, "", False, ["approach"], [{"blocked": "false"}], [{"blocked": 1}],
    [{"blocked": None}], [{"needs": []}], [{"needs": None}], [{"approach": 3}],
])
def test_malformed_approaches_fail(workspace, monkeypatch, derisking):
    ledger, out = workspace
    write_ledger(ledger, [entry(derisking=derisking)])
    assert_rejected(monkeypatch, ledger, out, "derisking")


def test_all_blocked_approaches_without_status_use_classifier(workspace, monkeypatch):
    ledger, out = workspace
    write_ledger(ledger, [entry(risk=1, derisking=[{"blocked": True, "needs": "A sample"}])])
    expected = builder.run_classifier(CLASSIFIER, ledger)
    state = invoke(monkeypatch, ledger, out)
    assert state["classification"] == expected
    assert state["classification"]["rows"][0]["category"] == "blocked"


@pytest.mark.parametrize("document", [
    {}, [], None, ["section"], [{"unknown": []}],
    [{builder.CURRENT_KEY: {}}], [{builder.PAST_KEY: None}],
    [{builder.CURRENT_KEY: [1]}],
    [{builder.CURRENT_KEY: []}, {builder.CURRENT_KEY: []}],
])
def test_invalid_section_structures_fail(workspace, monkeypatch, document):
    ledger, out = workspace
    ledger.write_text(yaml.safe_dump(document))
    assert_rejected(monkeypatch, ledger, out, "risky-assumptions.yaml")


def test_past_only_and_additive_sections_are_accepted(workspace, monkeypatch):
    ledger, out = workspace
    past = [entry("history-1", risk=0, confidence=-1, archived_note="Old premise")]
    ledger.write_text(yaml.safe_dump([{"metadata": {"extension": True}}, {builder.PAST_KEY: past}]))
    state = invoke(monkeypatch, ledger, out)
    assert state["past_assumptions"] == past
    assert state["classification"]["rows"] == []
    assert state["evidence"] == {}


def test_classifier_object_including_additive_fields_is_preserved(workspace, monkeypatch):
    ledger, out = workspace
    result = builder.run_classifier(CLASSIFIER, ledger)
    result["extension"] = {"keep": [1, True, None]}
    result["rows"][0]["extra"] = "verbatim"
    result["buckets"]["open"][0]["extra"] = "verbatim"
    original = copy.deepcopy(result)
    monkeypatch.setattr(builder, "run_classifier", lambda *_: result)
    state = invoke(monkeypatch, ledger, out)
    assert state["classification"] == original
    assert result == original


@pytest.mark.parametrize("field,value", [
    ("rows", {}), ("rows", []), ("counts", []), ("buckets", {}),
    ("recommended_mode", "invented"), ("vision_drift", []),
    ("high_risk_total", "1"),
])
def test_incompatible_classifier_structure_fails(workspace, monkeypatch, field, value):
    ledger, out = workspace
    result = builder.run_classifier(CLASSIFIER, ledger)
    result[field] = value
    monkeypatch.setattr(builder, "run_classifier", lambda *_: result)
    assert_rejected(monkeypatch, ledger, out, "incompatible classifier output")


def test_classifier_mismatched_bucket_id_fails(workspace, monkeypatch):
    ledger, out = workspace
    result = builder.run_classifier(CLASSIFIER, ledger)
    result["buckets"]["open"][0]["id"] = "different-id"
    monkeypatch.setattr(builder, "run_classifier", lambda *_: result)
    assert_rejected(monkeypatch, ledger, out, "bucket rows must match")


def test_nonfinite_additive_output_fails_before_writing(workspace, monkeypatch):
    ledger, out = workspace
    write_ledger(ledger, [entry()], [entry("past-1", extra=float("nan"))])
    assert_rejected(monkeypatch, ledger, out, "state is not JSON-compatible")


def test_malformed_yaml_fails_before_writing(workspace, monkeypatch):
    ledger, out = workspace
    ledger.write_text("[unterminated")
    assert_rejected(monkeypatch, ledger, out, "invalid YAML ledger")


def test_invalid_input_does_not_create_output(workspace, tmp_path, monkeypatch):
    ledger, _ = workspace
    out = tmp_path / "uncreated"
    write_ledger(ledger, [entry(risk=2)])
    with pytest.raises(SystemExit, match="risk must be"):
        invoke(monkeypatch, ledger, out, data_only=False)
    assert not out.exists()


@pytest.mark.parametrize("field,value", [
    ("id", "different-id"), ("confidence", float("nan")), ("needs", {}),
])
def test_incompatible_classifier_rows_fail(workspace, monkeypatch, field, value):
    ledger, out = workspace
    result = builder.run_classifier(CLASSIFIER, ledger)
    result["rows"][0][field] = value
    monkeypatch.setattr(builder, "run_classifier", lambda *_: result)
    assert_rejected(monkeypatch, ledger, out, "incompatible classifier output")


@pytest.mark.parametrize("path_name", ["data", "data/probe-1"])
def test_files_cannot_replace_spike_directories(workspace, monkeypatch, path_name):
    ledger, out = workspace
    path = ledger.parent / path_name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not a directory")
    assert_rejected(monkeypatch, ledger, out, "expected a spike")


def test_denied_artifact_directory_stops_before_output(workspace, monkeypatch):
    ledger, out = workspace
    write_spike(ledger, "nested/raw.txt", "Synthetic artifact")
    denied_dir = ledger.parent / "data" / "probe-1" / "nested"
    scandir = builder.os.scandir

    def denied(path):
        if Path(path) == denied_dir:
            raise PermissionError("denied artifact directory")
        return scandir(path)

    before = snapshot(out)
    monkeypatch.setattr(builder.os, "scandir", denied)
    with pytest.raises(PermissionError, match="denied artifact directory"):
        invoke(monkeypatch, ledger, out, data_only=False)
    assert snapshot(out) == before