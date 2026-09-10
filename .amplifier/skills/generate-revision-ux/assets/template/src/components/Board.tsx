import type { Row } from "../types";
import { CATEGORY_HINT, CATEGORY_LABEL, PRIORITY_HINT, runState } from "../format";
import Confidence, { ConfidenceLegend } from "./Confidence";

interface Props {
  rows: Row[];
  selected: string | null;
  onSelect: (id: string) => void;
}

export default function Board({ rows, selected, onSelect }: Props) {
  return (
    <section aria-labelledby="board-heading">
      <div className="section-heading">
        <div>
          <h2 id="board-heading">Current assumptions</h2>
          <p className="muted">Read the assumption, then open its evidence. A spike is a focused test or research task.</p>
        </div>
        <span className="section-count">{rows.length}</span>
      </div>
      <div className="surface board-guide">
        <div>
          <h3>Priority</h3>
          <p>{PRIORITY_HINT}</p>
        </div>
        <div>
          <h3>Confidence</h3>
          <p>Direction is against or in support; distance from zero is evidence strength, not probability.</p>
          <ConfidenceLegend />
        </div>
      </div>
      {rows.length === 0 ? (
        <p className="surface empty-state">No current-vision assumptions recorded.</p>
      ) : (
        <ul className="board">
          {rows.map((row) => (
            <li key={row.id} className={`surface board-row ${selected === row.id ? "selected" : ""}`}>
              <div className="board-assumption">
                <h3 className="assumption">{row.assumption}</h3>
                <div className="row-footer">
                  <span className="mono small muted">{row.id}</span>
                  <button className="button button-quiet" onClick={() => onSelect(row.id)}
                    aria-pressed={selected === row.id} aria-controls="evidence"
                    aria-label={`View evidence for ${row.id}`}>
                    {selected === row.id ? "Viewing evidence" : "View evidence"}
                  </button>
                </div>
              </div>
              <div className="board-priority">
                <div className="metric-label">Priority</div>
                <strong className="nums">{row.risk.toFixed(2)}</strong>
                {row.high_risk && <span className="tag tag-high">High</span>}
              </div>
              <div className="board-confidence">
                <div className="metric-label">Confidence</div>
                <Confidence value={row.confidence} compact label={`Confidence for ${row.id}`} />
              </div>
              <div className="board-category">
                <span className={`tag tag-${row.category}`}>{CATEGORY_LABEL[row.category]}</span>
                <p className="small muted">{CATEGORY_HINT[row.category]}</p>
                <span className="small muted">Run: {runState(row.status)}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}