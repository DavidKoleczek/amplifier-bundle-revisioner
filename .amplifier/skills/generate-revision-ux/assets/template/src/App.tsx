import { useEffect, useMemo, useState } from "react";
import { flushSync } from "react-dom";
import type { RevisionState } from "./types";
import { CATEGORY_LABEL, MODE_HINT, timestamp } from "./format";
import { parseRevisionState } from "./loadState";
import Attention from "./components/Attention";
import Board from "./components/Board";
import Confidence from "./components/Confidence";
import DrillDown, { Document } from "./components/DrillDown";

type Load =
  | { phase: "loading" }
  | { phase: "error"; message: string }
  | { phase: "ready"; state: RevisionState };

export function Header({ state }: { state: RevisionState }) {
  const { classification: c } = state;
  const drift = c.vision_drift;
  const sourcePath = "vision.md";
  return (
    <header className="page-header">
      <div className="brand-line">
        <span className="brand">ReVisioner</span>
        <span className="muted repo-name">{state.repo}</span>
        <span className="snapshot-label">Read-only snapshot</span>
      </div>
      <h1>Revision overview</h1>
      <div className="next-action">
        <span className="metric-label">Recommended next action</span>
        <p>{MODE_HINT[c.recommended_mode]}</p>
      </div>
      <p className="small muted">
        Snapshot <time dateTime={state.generated_at} title={state.generated_at}>{timestamp(state.generated_at)}</time>
        {" · Local time · Regenerate the dashboard to refresh."}
      </p>
      {drift?.stale ? (
        <p className="notice">
          <strong>Vision changed.</strong> These assumptions reflect an earlier vision. Refresh them before relying on this classification.
        </p>
      ) : !drift?.checked ? (
        <p className="notice notice-neutral">
          <strong>Vision freshness not checked.</strong> This snapshot does not establish whether the assumptions match the current vision.
        </p>
      ) : <p className="small muted">Vision matched the ledger when this snapshot was generated.</p>}
      <div className="counts" aria-label="Assumption counts">
        {(Object.keys(CATEGORY_LABEL) as (keyof typeof CATEGORY_LABEL)[]).map((category) => (
          <span key={category} className="count">
            <span className={`count-dot dot-${category}`} aria-hidden="true" />
            <strong>{c.counts[category]}</strong> {CATEGORY_LABEL[category]}
          </span>
        ))}
        <span className="count holding-count"><strong>{c.high_risk_holding}/{c.high_risk_total}</strong> high-priority holding</span>
      </div>
      <details className="surface vision disclosure">
        <summary>Vision document <span className="small muted">{state.vision.path}</span></summary>
        <Document title="Vision" value={state.vision.markdown} path={sourcePath}
          artifacts={Object.values(state.evidence).flatMap((entry) => entry.artifacts)}
          warning={state.warnings?.some((warning) => warning.path === sourcePath)} />
      </details>
    </header>
  );
}

export function PastAssumptions({ state }: { state: RevisionState }) {
  if (state.past_assumptions.length === 0) return null;
  return (
    <details className="surface past disclosure">
      <summary>Past-vision assumptions <span className="muted">({state.past_assumptions.length})</span></summary>
      <p className="small muted">Historical context, excluded from the current classification. Priority still means dependency, not urgency.</p>
      <ul className="past-list">
        {state.past_assumptions.map((entry) => (
          <li key={entry.id}>
            <h3 className="assumption">{entry.assumption}</h3>
            <span className="mono muted small">{entry.id}</span>
            <div className="past-metrics">
              <div><div className="metric-label">Priority</div>
                <span className="nums">{entry.risk == null ? "Not recorded" : entry.risk.toFixed(2)}</span>
              </div>
              <div><div className="metric-label">Confidence</div>
                <Confidence value={entry.confidence} label={`Historical confidence for ${entry.id}`} />
              </div>
            </div>
            {entry.archived_note && <p className="source-text muted">{entry.archived_note}</p>}
          </li>
        ))}
      </ul>
    </details>
  );
}

export default function App() {
  const [load, setLoad] = useState<Load>({ phase: "loading" });
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/revision-state.json", { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json() as Promise<unknown>;
      })
      .then((value) => setLoad({ phase: "ready", state: parseRevisionState(value) }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setLoad({ phase: "error", message: String(error) });
      });
    return () => controller.abort();
  }, []);

  const state = load.phase === "ready" ? load.state : null;
  const selectedRow = useMemo(
    () => state?.classification.rows.find((row) => row.id === selected) ?? null,
    [state, selected],
  );
  const onSelect = (id: string) => {
    flushSync(() => setSelected(id));
    const heading = document.getElementById("evidence-heading");
    heading?.focus({ preventScroll: true });
    heading?.scrollIntoView({
      block: "start",
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    });
  };

  if (load.phase === "loading") return <main className="wrap" aria-busy="true">Loading revision snapshot…</main>;
  if (load.phase === "error") return (
    <main className="wrap">
      <h1>Could not display this snapshot</h1>
      <p className="error" role="alert">{load.message}</p>
      <p>Generate the dashboard from the repository root, then reload this page:</p>
      <pre className="pre">python3 .amplifier/skills/generate-revision-ux/scripts/build_ux.py</pre>
    </main>
  );

  const current = load.state;
  return (
    <main className="wrap">
      <Header state={current} />
      {!!current.warnings?.length && (
        <aside className="notice data-warnings" aria-labelledby="warnings-heading">
          <h2 id="warnings-heading">Data warnings ({current.warnings.length})</h2>
          <p>Some source files could not be read. Unavailable content is not evidence of absence.</p>
          <ul>{current.warnings.map((warning, i) =>
            <li key={i}><code>{warning.path}</code>: {warning.message}</li>)}</ul>
        </aside>
      )}
      <Attention fails={current.classification.buckets.fails}
        blocked={current.classification.buckets.blocked} onSelect={onSelect} />
      <Board rows={current.classification.rows} selected={selected} onSelect={onSelect} />
      <DrillDown row={selectedRow}
        evidence={selected ? (current.evidence[selected] ?? null) : null}
        artifacts={Object.values(current.evidence).flatMap((entry) => entry.artifacts)}
        warnings={current.warnings} />
      <PastAssumptions state={current} />
    </main>
  );
}