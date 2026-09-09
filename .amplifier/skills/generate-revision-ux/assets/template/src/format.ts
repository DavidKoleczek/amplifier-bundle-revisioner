import type { Category, Mode, Row } from "./types";

export const CATEGORY_LABEL: Record<Category, string> = {
  fails: "INVALIDATED",
  blocked: "BLOCKED",
  in_flight: "IN FLIGHT",
  open: "OPEN",
  holds: "HOLDS",
};

// Blocked is not failed: a blocked spike means unknown. Distinct label and colour.
export const CATEGORY_HINT: Record<Category, string> = {
  fails: "evidence came back against this bet",
  blocked: "needs something only you can supply",
  in_flight: "a spike is running now",
  open: "untested or inconclusive, still spike-able",
  holds: "de-risked, the bet looks true",
};

export const MODE_HINT: Record<Mode, string> = {
  pivot: "a high-risk assumption failed - the vision should change",
  unblock: "a high-risk assumption is blocked - it needs something from you",
  in_progress: "work remains; let the spikes run",
  all_clear: "every high-risk assumption holds",
  stale: "the vision changed since this ledger was built - re-run find-risky-assumptions",
};

export function signed(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
}

export function bytes(count: number): string {
  if (count < 1024) return `${count} B`;
  if (count < 1024 * 1024) return `${(count / 1024).toFixed(1)} KB`;
  return `${(count / (1024 * 1024)).toFixed(1)} MB`;
}

/** High-risk first, then risk descending, then id. */
export function byAttention(a: Row, b: Row): number {
  if (a.high_risk !== b.high_risk) return a.high_risk ? -1 : 1;
  if (a.risk !== b.risk) return b.risk - a.risk;
  return a.id.localeCompare(b.id);
}
