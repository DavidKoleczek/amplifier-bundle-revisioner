import type { Evidence, Row } from "../types";
import { CATEGORY_HINT, CATEGORY_LABEL, bytes, signed } from "../format";

/** Renders text, or an explicit statement of absence. Never invents a summary. */
function TextSection({ title, value, missing }: { title: string; value: string | null; missing: string }) {
  return (
    <div className="section">
      <h4>{title}</h4>
      {value === null ? <p className="empty">{missing}</p> : <pre className="pre">{value}</pre>}
    </div>
  );
}

interface Props {
  row: Row | null;
  evidence: Evidence | null;
}

export default function DrillDown({ row, evidence }: Props) {
  return (
    <section>
      <h2>3 &middot; Evidence</h2>
      {!row && <p className="muted">Select an assumption on the board to see its evidence.</p>}
      {row && (
        <div className="drill">
          <div className="card-head">
            <span className="mono b">{row.id}</span>
            <span className={`tag tag-${row.category}`} title={CATEGORY_HINT[row.category]}>
              {CATEGORY_LABEL[row.category]}
            </span>
            {row.high_risk && <span className="tag tag-high">HIGH RISK</span>}
            <span className="nums">
              risk {row.risk.toFixed(2)} &middot; confidence {signed(row.confidence)} &middot; run
              state {row.status}
            </span>
          </div>
          <p className="assumption">{row.assumption}</p>

          <div className="section">
            <h4>De-risking approaches (from the ledger)</h4>
            {!evidence || evidence.derisking.length === 0 ? (
              <p className="empty">No de-risking approaches recorded for this assumption.</p>
            ) : (
              <ul className="approaches">
                {evidence.derisking.map((approach, i) => (
                  <li key={i}>
                    <span className={approach.blocked ? "tag tag-blocked" : "tag tag-open"}>
                      {approach.blocked ? "BLOCKED" : "OPEN"}
                    </span>{" "}
                    {approach.approach ?? "(no approach text)"}
                    {approach.needs && (
                      <div className="needs-inline">
                        <b>needs:</b> {approach.needs}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <TextSection
            title="Spike plan"
            value={evidence?.spike_plan ?? null}
            missing="No spike plan recorded - this assumption has not been spiked."
          />
          <TextSection
            title="Findings"
            value={evidence?.findings ?? null}
            missing="No findings recorded - this spike produced no write-up."
          />
          <TextSection
            title="Verdict"
            value={evidence?.verdict ? JSON.stringify(evidence.verdict, null, 2) : null}
            missing="No verdict recorded."
          />

          <div className="section">
            <h4>Artifacts</h4>
            {!evidence || evidence.artifacts.length === 0 ? (
              <p className="empty">No artifacts captured.</p>
            ) : (
              <ul className="artifacts">
                {evidence.artifacts.map((artifact) => (
                  <li key={artifact.path}>
                    <a href={"/" + artifact.path} target="_blank" rel="noreferrer">
                      {artifact.path}
                    </a>{" "}
                    <span className="muted">({bytes(artifact.bytes)})</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
