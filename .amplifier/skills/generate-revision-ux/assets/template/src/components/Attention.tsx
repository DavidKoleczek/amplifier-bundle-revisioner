import type { Row } from "../types";
import { MODE_HINT, byAttention, signed } from "../format";
import type { Mode } from "../types";

interface CardProps {
  row: Row;
  kind: "fails" | "blocked";
  onSelect: (id: string) => void;
}

function AttentionCard({ row, kind, onSelect }: CardProps) {
  return (
    <div className={`card card-${kind}`}>
      <div className="card-head">
        <button className="link-id" onClick={() => onSelect(row.id)}>
          {row.id}
        </button>
        <span className={`tag tag-${kind}`}>
          {kind === "fails" ? "INVALIDATED" : "BLOCKED"}
        </span>
        {row.high_risk && <span className="tag tag-high">HIGH RISK</span>}
        <span className="nums">
          risk {row.risk.toFixed(2)} &middot; confidence {signed(row.confidence)}
        </span>
      </div>
      <p className="assumption">{row.assumption}</p>
      {kind === "blocked" &&
        (row.needs.length > 0 ? (
          <>
            <div className="needs-label">Needs from you:</div>
            <ul className="needs">
              {row.needs.map((need, i) => (
                <li key={i}>{need}</li>
              ))}
            </ul>
          </>
        ) : (
          <div className="muted">
            No <code>needs:</code> recorded - the spike reported blocked without naming
            what is missing.
          </div>
        ))}
    </div>
  );
}

interface Props {
  fails: Row[];
  blocked: Row[];
  mode: Mode;
  onSelect: (id: string) => void;
}

export default function Attention({ fails, blocked, mode, onSelect }: Props) {
  const nothing = fails.length === 0 && blocked.length === 0;
  return (
    <section>
      <h2>1 &middot; Needs your attention</h2>
      {nothing && (
        <p className="empty">
          Nothing is waiting on you. Recommended mode is <b>{mode}</b> &mdash;{" "}
          {MODE_HINT[mode]}.
        </p>
      )}
      {fails.length > 0 && (
        <>
          <h3 className="sub">
            The evidence says the vision should change ({fails.length})
          </h3>
          {[...fails].sort(byAttention).map((row) => (
            <AttentionCard key={row.id} row={row} kind="fails" onSelect={onSelect} />
          ))}
        </>
      )}
      {blocked.length > 0 && (
        <>
          <h3 className="sub">
            The tool needs something only you can supply ({blocked.length})
          </h3>
          {[...blocked].sort(byAttention).map((row) => (
            <AttentionCard key={row.id} row={row} kind="blocked" onSelect={onSelect} />
          ))}
        </>
      )}
    </section>
  );
}
