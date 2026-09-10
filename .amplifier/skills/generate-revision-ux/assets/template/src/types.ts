// Mirrors references/state-contract.md. The builder emits exactly this shape into
// public/revision-state.json; nothing here is computed in the browser.

export type Category = "holds" | "fails" | "blocked" | "in_flight" | "open";

export type Mode = "pivot" | "unblock" | "in_progress" | "all_clear" | "stale";

export interface Row {
  id: string;
  assumption: string;
  /** 0.00 .. 1.00, stakes only. */
  risk: number;
  /** -1.00 .. +1.00, signed belief that the assumption holds. */
  confidence: number;
  /** risk >= the classifier's high-risk threshold. */
  high_risk: boolean;
  /** status.json state, or "unset". */
  status: string;
  category: Category;
  lean: "positive" | "neutral" | "negative";
  has_blocked_residual: boolean;
  /** Verbatim `needs:` text from every blocked de-risking approach. */
  needs: string[];
}

export interface VisionDrift {
  checked: boolean;
  stale: boolean;
  stored?: string | null;
  current?: string | null;
  vision_path?: string;
}

/** Verbatim output of vision-check-in/scripts/classify.py --json. Never recomputed. */
export interface Classification {
  recommended_mode: Mode;
  counts: Record<Category, number>;
  high_risk_total: number;
  high_risk_holding: number;
  vision_drift?: VisionDrift;
  buckets: Record<Category, Row[]>;
  rows: Row[];
}

export interface DeriskingApproach {
  approach?: string;
  needs?: string;
  blocked?: boolean;
}

export interface Artifact {
  /** Relative to public/, e.g. "data/RA-LniKzX/sources.md". */
  path: string;
  bytes: number;
}

export interface Evidence {
  /** null when the spike recorded no plan. Absence is data, not an empty string. */
  spike_plan: string | null;
  findings: string | null;
  verdict: Record<string, unknown> | null;
  status: { state?: string; updated?: string } | null;
  /** From the ledger entry, not from the verdict. */
  derisking: DeriskingApproach[];
  artifacts: Artifact[];
}

export interface PastAssumption {
  id: string;
  assumption: string;
  risk?: number | null;
  confidence?: number | null;
  archived_note?: string;
  [key: string]: unknown;
}

export interface RevisionState {
  generated_at: string;
  repo: string;
  vision: { path: string; markdown: string | null };
  classification: Classification;
  evidence: Record<string, Evidence>;
  past_assumptions: PastAssumption[];
  warnings?: Array<{ path: string; message: string }>;
}
