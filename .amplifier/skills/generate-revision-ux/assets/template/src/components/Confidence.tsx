import { signed } from "../format";

export function ConfidenceLegend() {
  return (
    <div className="confidence-legend">
      <span>−1 · Strong evidence against</span>
      <span>0 · Unknown / inconclusive</span>
      <span>+1 · Strong evidence supports</span>
    </div>
  );
}

interface Props {
  value?: number | null;
  compact?: boolean;
  label?: string;
}

export default function Confidence({ value, compact = false, label = "Confidence" }: Props) {
  if (value == null) return <span className="empty">Not recorded</span>;
  if (!Number.isFinite(value) || value < -1 || value > 1) {
    return <span className="error">Invalid recorded confidence</span>;
  }
  const position = (value + 1) * 50;
  const direction = value < 0 ? "against" : value > 0 ? "supports" : "neutral";
  const meaning = value === 0 ? "Unknown / inconclusive" :
    `Evidence ${direction === "against" ? "against" : "supports"} the assumption`;
  return (
    <div className={`confidence ${compact ? "confidence-compact" : ""}`}>
      <div className="confidence-value">
        <strong className="nums">{signed(value)}</strong>
        {!compact && <span className="muted small">{meaning}</span>}
      </div>
      <div
        className={`confidence-track confidence-${direction}`}
        role="meter"
        aria-label={label}
        aria-valuemin={-1}
        aria-valuemax={1}
        aria-valuenow={value}
        aria-valuetext={`${signed(value)}. ${meaning}. Magnitude is evidence strength, not probability.`}
      >
        <span className="confidence-fill" style={{
          left: `${Math.min(50, position)}%`, width: `${Math.abs(value) * 50}%`,
        }} />
        <span className="confidence-zero" />
        <span className="confidence-marker" style={{ left: `${position}%` }} />
      </div>
      {compact ? (
        <div className="confidence-ticks">
          <span>−1 <br />Against</span><span>0</span><span>+1 <br />Supports</span>
        </div>
      ) : <ConfidenceLegend />}
    </div>
  );
}