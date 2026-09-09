import { useEffect, useMemo, useState } from "react";
import type { RevisionState } from "./types";
import { CATEGORY_LABEL, MODE_HINT, signed } from "./format";
import Attention from "./components/Attention";
import Board from "./components/Board";
import DrillDown from "./components/DrillDown";

type Load =
  | { phase: "loading" }
  | { phase: "error"; message: string }
  | { phase: "ready"; state: RevisionState };

function Header({ state }: { state: RevisionState }) {
  const { classification: c } = state;
  const drift = c.vision_drift;
  return (
    <header>
      <h1>
        ReVisioner &mdash; <span className="mono">{state.repo}</span>
      </h1>
      <div className="mode">
        Recommended mode: <b>{c.recommended_mode}</b>{" "}
        <span className="muted">&mdash; {MODE_HINT[c.recommended_mode]}</span>
      </div>
      {drift?.stale && (
        <div className="drift">
          Vision drift: vision.md changed since this ledger was built. The assumptions
          below are stale.
        </div>
      )}
      <div className="counts">
        {(Object.keys(CATEGORY_LABEL) as (keyof typeof CATEGORY_LABEL)[]).map((cat) => (
          <span key={cat} className={`count tag-${cat}`}>
            {CATEGORY_LABEL[cat]} {c.counts[cat] ?? 0}
          </span>
        ))}
        <span className="count">
          high-risk holding {c.high_risk_holding}/{c.high_risk_total}
        </span>
      </div>
      <div className="muted small">
        Generated {state.generated_at} from {state.vision.path}
      </div>
      <details className="vision">
        <summary>Vision document</summary>
        {state.vision.markdown === null ? (
          <p className="empty">No vision.md found at {state.vision.path}.</p>
        ) : (
          <pre className="pre">{state.vision.markdown}</pre>
        )}
      </details>
    </header>
  );
}

function PastAssumptions({ state }: { state: RevisionState }) {
  const past = state.past_assumptions ?? [];
  return (
    <details className="past">
      <summary>4 &middot; Past-vision assumptions ({past.length})</summary>
      {past.length === 0 ? (
        <p className="empty">No past-vision assumptions recorded.</p>
      ) : (
        <ul>
          {past.map((entry) => (
            <li key={entry.id}>
              <span className="mono">{entry.id}</span>{" "}
              <span className="nums">
                risk {(entry.risk ?? 0).toFixed(2)} &middot; confidence{" "}
                {signed(entry.confidence ?? 0)}
              </span>
              <div>{entry.assumption}</div>
              {entry.archived_note && <div className="muted">{entry.archived_note}</div>}
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}

export default function App() {
  const [load, setLoad] = useState<Load>({ phase: "loading" });
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    fetch("/revision-state.json")
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json() as Promise<RevisionState>;
      })
      .then((state) => setLoad({ phase: "ready", state }))
      .catch((error: unknown) =>
        setLoad({ phase: "error", message: String(error) }),
      );
  }, []);

  const state = load.phase === "ready" ? load.state : null;
  const selectedRow = useMemo(
    () => state?.classification.rows.find((row) => row.id === selected) ?? null,
    [state, selected],
  );

  if (load.phase === "loading") return <main className="wrap">Loading&hellip;</main>;

  if (load.phase === "error") {
    return (
      <main className="wrap">
        <h1>No state to render</h1>
        <p className="error">Could not load /revision-state.json ({load.message}).</p>
        <p>Generate it from the repo root, then reload this page:</p>
        <pre className="pre">
          python3 .amplifier/skills/generate-revision-ux/scripts/build_ux.py
        </pre>
      </main>
    );
  }

  const current = load.state;
  return (
    <main className="wrap">
      <Header state={current} />
      <Attention
        fails={current.classification.buckets.fails ?? []}
        blocked={current.classification.buckets.blocked ?? []}
        mode={current.classification.recommended_mode}
        onSelect={setSelected}
      />
      <Board
        rows={current.classification.rows}
        selected={selected}
        onSelect={setSelected}
      />
      <DrillDown
        row={selectedRow}
        evidence={selected ? (current.evidence[selected] ?? null) : null}
      />
      <PastAssumptions state={current} />
    </main>
  );
}
