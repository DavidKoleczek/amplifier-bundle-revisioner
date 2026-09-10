import type { Row } from "../types";
import { CATEGORY_LABEL, byAttention } from "../format";

interface Props {
  fails: Row[];
  blocked: Row[];
  onSelect: (id: string) => void;
}

export default function Attention({ fails, blocked, onSelect }: Props) {
  const actionable = [...fails, ...blocked].filter((row) => row.high_risk).sort(byAttention);
  return (
    <section aria-labelledby="attention-heading">
      <div className="section-heading">
        <div>
          <h2 id="attention-heading">Needs your attention</h2>
          <p className="muted">High-priority assumptions that do not hold or need your help to test.</p>
        </div>
        <span className="section-count">{actionable.length}</span>
      </div>
      {actionable.length === 0 ? (
        <p className="surface empty-state">No high-priority failures or blockers in this snapshot.</p>
      ) : (
        <div className="attention-grid">
          {actionable.map((row) => (
            <article className={`surface attention-card card-${row.category}`} key={row.id}>
              <div className="card-meta">
                <span className={`tag tag-${row.category}`}>{CATEGORY_LABEL[row.category]}</span>
                <span className="small muted">High priority · {row.risk.toFixed(2)}</span>
              </div>
              <h3 className="assumption">{row.assumption}</h3>
              <div className="mono small muted">{row.id}</div>
              {row.category === "fails" ? (
                <p>Review what the evidence challenges before deciding how to amend the vision.</p>
              ) : (
                <div className="needs-block">
                  <h4>Needed from you</h4>
                  {row.needs.length ? <ul className="needs">
                    {row.needs.map((need, i) => <li key={i}>{need}</li>)}
                  </ul> : <p className="muted">The blocker does not name what is needed.</p>}
                </div>
              )}
              <button className="button" onClick={() => onSelect(row.id)}
                aria-label={`Review evidence for ${row.id}`} aria-controls="evidence">
                Review evidence <span aria-hidden="true">↗</span>
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}