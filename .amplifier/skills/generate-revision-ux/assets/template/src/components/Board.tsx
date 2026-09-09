import type { Row } from "../types";
import { CATEGORY_HINT, CATEGORY_LABEL, signed } from "../format";

interface Props {
  rows: Row[];
  selected: string | null;
  onSelect: (id: string) => void;
}

export default function Board({ rows, selected, onSelect }: Props) {
  return (
    <section>
      <h2>2 &middot; The board</h2>
      <p className="muted">
        Every current-vision assumption. Click a row to open its evidence below.
      </p>
      <table className="board">
        <thead>
          <tr>
            <th></th>
            <th>id</th>
            <th>risk</th>
            <th>conf</th>
            <th>category</th>
            <th>run state</th>
            <th>assumption</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.id}
              onClick={() => onSelect(row.id)}
              className={selected === row.id ? "row selected" : "row"}
            >
              <td className="high">{row.high_risk ? "*" : ""}</td>
              <td className="mono">{row.id}</td>
              <td className="num">{row.risk.toFixed(2)}</td>
              <td className="num">{signed(row.confidence)}</td>
              <td>
                <span
                  className={`tag tag-${row.category}`}
                  title={CATEGORY_HINT[row.category]}
                >
                  {CATEGORY_LABEL[row.category]}
                </span>
              </td>
              <td className="mono muted">{row.status}</td>
              <td className="assumption-cell">{row.assumption}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted">* = high-risk</p>
    </section>
  );
}
