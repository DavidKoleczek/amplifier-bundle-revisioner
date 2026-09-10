import type { Category, Mode, Row } from "./types";

export const CATEGORY_LABEL: Record<Category, string> = {
  fails: "Does not hold",
  blocked: "Blocked",
  in_flight: "In progress",
  open: "Open",
  holds: "Holds",
};

// Blocked is not failed: a blocked spike means unknown. Distinct label and colour.
export const CATEGORY_HINT: Record<Category, string> = {
  fails: "Evidence is strong enough against this assumption.",
  blocked: "More evidence needs access, data, or a decision from you. Blocked does not mean false.",
  in_flight: "An evidence-gathering spike is running.",
  open: "Not yet tested or evidence is inconclusive. More testing is possible.",
  holds: "Evidence is strong enough to support this assumption.",
};

export const MODE_HINT: Record<Mode, string> = {
  pivot: "Review the evidence and consider amending the vision.",
  unblock: "Provide the access, data, or decisions needed below.",
  in_progress: "Continue gathering evidence for open assumptions.",
  all_clear: "No intervention is needed on high-priority assumptions.",
  stale: "Refresh assumptions against the changed vision before deciding.",
};

export const PRIORITY_HINT =
  "Priority is the stakes: how much the vision depends on an assumption. " +
  "0 = little dependency; 1 = essential. It is not confidence or urgency. " +
  "High is the classifier's designation.";

export function runState(value: string): string {
  const labels: Record<string, string> = {
    unset: "Not recorded", running: "Running", done: "Done", blocked: "Blocked",
  };
  return labels[value] ?? value.replace(/_/g, " ");
}

export function timestamp(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString(undefined, {
    dateStyle: "medium", timeStyle: "short", timeZoneName: undefined,
  });
}

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
