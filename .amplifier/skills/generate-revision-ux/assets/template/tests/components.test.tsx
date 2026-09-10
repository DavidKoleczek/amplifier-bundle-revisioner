import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup as render } from "react-dom/server";
import Confidence from "../src/components/Confidence";
import Markdown, { artifactHref, resolveLink } from "../src/components/Markdown";
import Attention from "../src/components/Attention";
import Board from "../src/components/Board";
import DrillDown, { Artifacts, Document } from "../src/components/DrillDown";
import { Header, PastAssumptions } from "../src/App";
import { parseRevisionState } from "../src/loadState";
import type { Evidence, RevisionState, Row } from "../src/types";

const row: Row = {
  id: "RA-sample", assumption: "The service can preserve the source data.",
  risk: 0.85, confidence: -0.5, high_risk: true, category: "blocked",
  status: "blocked", lean: "negative", has_blocked_residual: true, needs: ["An independent dataset."],
};
const evidence: Evidence = {
  findings: "# Evidence\n\nMeasured **three** observations.", spike_plan: null, verdict: null,
  status: null, derisking: [], artifacts: [],
};
const fixture = (): RevisionState => ({
  repo: "example-project", generated_at: "2026-01-01T12:00:00Z",
  vision: { path: ".amplifier/revisioner/vision.md", markdown: "# Vision" },
  classification: {
    recommended_mode: "unblock", counts: { holds: 0, fails: 0, blocked: 1, in_flight: 0, open: 0 },
    high_risk_total: 1, high_risk_holding: 0, rows: [{ ...row }],
    buckets: { holds: [], fails: [], blocked: [{ ...row }], in_flight: [], open: [] },
  },
  evidence: { [row.id]: { ...evidence } }, past_assumptions: [],
});
const artifacts = [
  { path: "data/RA-sample/output/report.md", bytes: 50 },
  { path: "data/RA-sample/a b.txt", bytes: 10 },
  { path: "data/RA-sample/report.html", bytes: 20 },
];

for (const value of [-1, -0.5, 0, 0.5, 1]) {
  test(`confidence ${value} has the correct marker and zero-origin fill`, () => {
    const html = render(<Confidence value={value} />);
    const position = (value + 1) * 50;
    assert.match(html, /role="meter"/);
    assert.match(html, /aria-valuemin="-1" aria-valuemax="1"/);
    assert.ok(html.includes(`aria-valuenow="${value}"`));
    assert.ok(html.includes(`class="confidence-fill" style="left:${Math.min(50, position)}%;width:${Math.abs(value) * 50}%"`));
    assert.ok(html.includes(`class="confidence-marker" style="left:${position}%"`));
    assert.match(html, /−1 · Strong evidence against/);
    assert.match(html, /0 · Unknown \/ inconclusive/);
    assert.match(html, /\+1 · Strong evidence supports/);
    assert.match(html, /not probability/);
    assert.doesNotMatch(html, /role="slider"|tabindex/);
    assert.ok(html.includes(`${value >= 0 ? "+" : ""}${value.toFixed(2)}`));
  });
}

test("missing confidence is not zero and invalid confidence is not clamped", () => {
  for (const value of [undefined, null]) {
    const html = render(<Confidence value={value} />);
    assert.match(html, /Not recorded/);
    assert.doesNotMatch(html, /meter|0\.00/);
  }
  for (const value of [NaN, Infinity, -2, 2]) {
    assert.match(render(<Confidence value={value} />), /Invalid recorded confidence/);
  }
});

test("compact confidence keeps the visible numeric range", () => {
  const html = render(<Confidence compact value={0.25} />);
  assert.match(html, /<span>−1 <br\/>Against<\/span><span>0<\/span><span>\+1 <br\/>Supports<\/span>/);
  assert.match(html, /aria-valuetext="\+0.25. Evidence supports/);
});

test("compact confidence exposes semantic endpoint captions without hiding them from assistive technology", () => {
  const html = render(<Confidence compact value={0.05} />);
  assert.match(html, /class="confidence-ticks"><span>−1 <br\/>Against<\/span><span>0<\/span><span>\+1 <br\/>Supports<\/span>/);
  assert.doesNotMatch(html, /aria-hidden|role="slider"|tabindex/);
  assert.match(html, /role="meter"/);
  assert.match(html, /class="confidence-zero"/);
  assert.match(html, /class="confidence-marker" style="left:52.5%"/);
});

test("Markdown renders the full document without executing raw HTML", () => {
  const html = render(<Markdown documentPath="data/RA-sample/findings.md" text={
    "# Findings\n\n**Measured** one observation.\n\n<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>\n\nLast paragraph."
  } />);
  assert.match(html, /<h4>Findings<\/h4>/);
  assert.match(html, /<strong>Measured<\/strong>/);
  assert.match(html, /Last paragraph/);
  assert.doesNotMatch(html, /<script|<img|<iframe/);
});

test("Markdown resolves only known copied files relative to its document", () => {
  assert.deepEqual(resolveLink("../a%20b.txt", "data/RA-sample/output/findings.md", artifacts),
    { href: "/data/RA-sample/a%20b.txt", external: false });
  assert.deepEqual(resolveLink("./output/report.md#evidence", "data/RA-sample/findings.md", artifacts),
    { href: "/data/RA-sample/output/report.md#evidence", external: false });
  assert.equal(resolveLink("../../private.txt", "data/RA-sample/findings.md", artifacts), null);
  assert.equal(resolveLink("javascript:alert(1)", "data/RA-sample/findings.md", artifacts), null);
  assert.equal(resolveLink("data:text/html,bad", "data/RA-sample/findings.md", artifacts), null);
  assert.equal(artifactHref("data/RA-sample/../../private.txt"), null);
  const html = render(<Markdown documentPath="data/RA-sample/findings.md" artifacts={artifacts}
    text="[report](output/report.md) [unavailable](missing.md) [HTML source](report.html)" />);
  assert.match(html, /href="\/data\/RA-sample\/output\/report.md"/);
  assert.match(html, /<span>unavailable<\/span>/);
  assert.match(html, /href="\/data\/RA-sample\/report.html"[^>]*download/);
  assert.doesNotMatch(html, /<iframe/);
});

test("external links are safe and remote images require opt-in", () => {
  const html = render(<Markdown documentPath="data/RA-sample/findings.md"
    text="[source](https://example.org/paper) ![Chart](https://example.org/chart.png)" />);
  assert.match(html, /target="_blank" rel="noopener noreferrer"/);
  assert.match(html, /Open remote image/);
  assert.match(html, /Image: Chart/);
  assert.doesNotMatch(html, /<img|src=/);
});

test("missing, empty, and unreadable documents have distinct messages", () => {
  const props = { title: "Spike plan", path: "data/RA-sample/spike-plan.md", artifacts: [] };
  assert.match(render(<Document {...props} value={null} />), /No spike plan document recorded/);
  assert.match(render(<Document {...props} value={" \n"} />), /present but empty/);
  assert.match(render(<Document {...props} value={null} warning />), /could not be read/);
  assert.doesNotMatch(render(<Document {...props} value={null} />), /never|not been spiked/);
});

test("detail keeps findings first, three blocking states, and raw verdict fields", () => {
  const html = render(<DrillDown row={row} artifacts={[]} evidence={{
    ...evidence, verdict: { confidence: 0.9, extra: { preserved: true } },
    derisking: [{ approach: "One", blocked: true }, { approach: "Two", blocked: false }, { approach: "Three" }],
  }} />);
  assert.ok(html.indexOf("<h3>Findings") < html.indexOf("Ways to gather more evidence"));
  assert.match(html, /Not marked blocked/);
  assert.match(html, /Blocking status not recorded/);
  assert.match(html, />Blocked</);
  assert.match(html, /aria-valuenow="-0.5"/);
  assert.match(html, /&quot;confidence&quot;: 0.9/);
  assert.match(html, /&quot;preserved&quot;: true/);
  assert.match(html, /<details[^>]*><summary>Raw verdict/);
});

test("malformed verdict is identified rather than presented as missing", () => {
  const raw = { path: "data/RA-sample/verdict.json", bytes: 9 };
  const html = render(<DrillDown row={row} artifacts={[raw]} evidence={{ ...evidence, artifacts: [raw] }}
    warnings={[{ path: ".amplifier/revisioner/data/RA-sample/verdict.json", message: "Malformed JSON" }]} />);
  assert.match(html, /could not be parsed/);
  assert.match(html, /href="\/data\/RA-sample\/verdict.json" download/);
  assert.doesNotMatch(html, /No verdict document/);
});

test("artifact groups use actual full parent paths and count bytes", () => {
  const html = render(<Artifacts id="RA-sample" artifacts={[
    ...artifacts,
    { path: "data/RA-sample/output/deep/result.txt", bytes: 5 },
    { path: "data/RA-sample/run/deep/result.txt", bytes: 8 },
  ]} />);
  assert.match(html, /Root files/);
  assert.match(html, /2 files · 30 B/);
  assert.match(html, /output\/deep/);
  assert.match(html, /run\/deep/);
  assert.doesNotMatch(html, /passed|successful|failed/);
});

test("only classifier-designated high-priority failures and blockers get attention", () => {
  const html = render(<Attention fails={[{ ...row, id: "low-fail", category: "fails", high_risk: false }]}
    blocked={[row]} onSelect={() => {}} />);
  assert.match(html, /Review evidence for RA-sample/);
  assert.doesNotMatch(html, /low-fail/);
});

test("board uses priority, explains categories, and exposes explicit selection buttons", () => {
  const html = render(<Board rows={[row]} selected={null} onSelect={() => {}} />);
  assert.match(html, /Priority/);
  assert.match(html, /not confidence or urgency/);
  assert.match(html, /Blocked does not mean false/);
  assert.match(html, /<button[^>]*aria-controls="evidence"/);
  assert.doesNotMatch(html, /risk|medium|in_flight/);
});

test("header distinguishes unchecked, matching, and stale visions", () => {
  const state = fixture();
  assert.match(render(<Header state={state} />), /Vision freshness not checked/);
  state.classification.vision_drift = { checked: true, stale: false };
  assert.match(render(<Header state={state} />), /Vision matched the ledger/);
  state.classification.vision_drift.stale = true;
  assert.match(render(<Header state={state} />), /Vision changed/);
  assert.doesNotMatch(render(<Header state={state} />), /recommended_mode|in_progress/);
});

test("past assumptions are conditional and missing scores are not invented", () => {
  const state = fixture();
  assert.equal(render(<PastAssumptions state={state} />), "");
  state.past_assumptions = [{ id: "RA-past", assumption: "A previous assumption." }];
  const html = render(<PastAssumptions state={state} />);
  assert.match(html, /Priority/);
  assert.match(html, /Not recorded/);
  assert.doesNotMatch(html, /<details[^>]*open|0\.00|risk/);
});

test("load guard preserves additive fields and fails helpfully on unusable data", () => {
  const state = { ...fixture(), extension: { harmless: true } };
  assert.equal(parseRevisionState(state), state);
  assert.throws(() => parseRevisionState({}), /repo and generated_at text/);
  const bad = fixture();
  bad.classification.rows[0].confidence = 2;
  assert.throws(() => parseRevisionState(bad), /classification.rows\[0\].confidence/);
  assert.throws(() => parseRevisionState({ ...fixture(), evidence: { bad: { ...evidence, derisking: "wrong" } } }), /derisking/);
  assert.throws(() => parseRevisionState({ ...fixture(), warnings: ["wrong"] }), /warnings/);
});

for (const axes of [
  {},
  { risk: null, confidence: null },
  { risk: 0, confidence: 0 },
  { risk: 0.6, confidence: -0.8 },
  { risk: 1, confidence: 0.7 },
]) {
  test(`past axes ${JSON.stringify(axes)} parse and render without invented values`, () => {
    const state = fixture();
    state.past_assumptions = [{ id: "RA-past", assumption: "A previous assumption.", ...axes }];
    const parsed = parseRevisionState(state);
    assert.equal(parsed, state);
    const html = render(<PastAssumptions state={parsed} />);
    if (axes.risk == null && axes.confidence == null) {
      assert.equal(html.match(/Not recorded/g)?.length, 2);
      assert.doesNotMatch(html, /role="meter"|0\.00/);
    } else {
      assert.ok(html.includes(`<span class="nums">${axes.risk!.toFixed(2)}</span>`));
      assert.ok(html.includes(`aria-valuenow="${axes.confidence}"`));
      assert.ok(html.includes(`${axes.confidence! >= 0 ? "+" : ""}${axes.confidence!.toFixed(2)}`));
      assert.doesNotMatch(html, /Not recorded/);
    }
  });
}

test("header identifies unreadable vision using the source-relative warning path", () => {
  const state = fixture();
  state.vision.markdown = null;
  state.warnings = [{ path: "vision.md", message: "Unable to decode UTF-8 text." }];
  const html = render(<Header state={parseRevisionState(state)} />);
  assert.match(html, /Vision could not be read/);
  assert.doesNotMatch(html, /No vision document recorded|present but empty/);
  assert.ok(html.includes(state.vision.path));
});

test("header preserves missing and empty vision states without a vision warning", () => {
  for (const markdown of [null, "", " \n"]) {
    const state = fixture();
    state.vision.markdown = markdown;
    state.warnings = [{ path: "data/probe-1/findings.md", message: "Unable to decode UTF-8 text." }];
    const html = render(<Header state={parseRevisionState(state)} />);
    assert.match(html, markdown === null ? /No vision document recorded/ : /present but empty/);
    assert.doesNotMatch(html, /Vision could not be read/);
    assert.ok(html.includes(state.vision.path));
  }
});

test("header resolves vision links in the copied-artifact namespace and keeps its displayed repo path", () => {
  const state = fixture();
  state.vision.markdown = "# Vision\n\nRead [source](data/probe-1/source.md) and [unavailable](data/probe-1/missing.md).";
  state.evidence["probe-1"] = {
    ...evidence, artifacts: [{ path: "data/probe-1/source.md", bytes: 42 }],
  };
  const html = render(<Header state={parseRevisionState(state)} />);
  assert.match(html, /<h4>Vision<\/h4>/);
  assert.match(html, /href="\/data\/probe-1\/source.md"[^>]*download/);
  assert.match(html, /<span>unavailable<\/span>/);
  assert.doesNotMatch(html, /No vision document recorded|present but empty|Vision could not be read/);
  assert.ok(html.includes(state.vision.path));
});