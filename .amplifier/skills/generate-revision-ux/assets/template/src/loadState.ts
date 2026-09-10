import { CATEGORY_LABEL, MODE_HINT } from "./format";
import type { RevisionState } from "./types";

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
function expect(condition: unknown, path: string, shape: string): asserts condition {
  if (!condition) throw new Error(`Invalid revision-state.json at ${path}: expected ${shape}. Regenerate the dashboard from the ledger.`);
}
const textOrNull = (value: unknown) => value === null || typeof value === "string";
const numberIn = (value: unknown, min: number, max: number) =>
  typeof value === "number" && Number.isFinite(value) && value >= min && value <= max;

/** Guard the fields the view consumes; additive source fields remain untouched. */
export function parseRevisionState(value: unknown): RevisionState {
  expect(record(value), "root", "an object");
  expect(typeof value.repo === "string" && typeof value.generated_at === "string", "root", "repo and generated_at text");
  expect(record(value.vision) && typeof value.vision.path === "string" &&
    textOrNull(value.vision.markdown), "vision", "a path and markdown text or null");
  const c = value.classification;
  expect(record(c), "classification", "an object");
  expect(typeof c.recommended_mode === "string" &&
    Object.prototype.hasOwnProperty.call(MODE_HINT, c.recommended_mode), "classification.recommended_mode", "a supported recommendation");
  expect(record(c.counts) && record(c.buckets) && Array.isArray(c.rows),
    "classification", "counts, buckets, and rows");
  expect(numberIn(c.high_risk_total, 0, Infinity) && numberIn(c.high_risk_holding, 0, Infinity),
    "classification", "numeric high-priority counts");
  const checkRow = (row: unknown, path: string) => {
    expect(record(row), path, "an assumption object");
    expect(typeof row.id === "string" && typeof row.assumption === "string", path, "id and assumption text");
    expect(numberIn(row.risk, 0, 1), `${path}.risk`, "a priority value from 0 to 1");
    expect(numberIn(row.confidence, -1, 1), `${path}.confidence`, "a confidence value from -1 to 1");
    expect(typeof row.high_risk === "boolean" && typeof row.status === "string" &&
      typeof row.category === "string" && Object.prototype.hasOwnProperty.call(CATEGORY_LABEL, row.category),
    path, "a high-priority designation, run state, and supported category");
    expect(Array.isArray(row.needs) && row.needs.every((need) => typeof need === "string"), `${path}.needs`, "a text array");
  };
  c.rows.forEach((row, i) => checkRow(row, `classification.rows[${i}]`));
  for (const category of Object.keys(CATEGORY_LABEL)) {
    expect(numberIn(c.counts[category], 0, Infinity), `classification.counts.${category}`, "a count");
    const bucket = c.buckets[category];
    expect(Array.isArray(bucket), `classification.buckets.${category}`, "an array");
    bucket.forEach((row, i) => checkRow(row, `classification.buckets.${category}[${i}]`));
  }
  if (c.vision_drift !== undefined) {
    expect(record(c.vision_drift) && typeof c.vision_drift.checked === "boolean" &&
      typeof c.vision_drift.stale === "boolean", "classification.vision_drift", "checked and stale booleans");
  }
  expect(record(value.evidence), "evidence", "an object keyed by assumption id");
  for (const [id, evidence] of Object.entries(value.evidence)) {
    const path = `evidence.${id}`;
    expect(record(evidence), path, "an evidence object");
    expect(textOrNull(evidence.findings) && textOrNull(evidence.spike_plan), path, "document text or null");
    expect(evidence.verdict === null || record(evidence.verdict), `${path}.verdict`, "a JSON object or null");
    expect(evidence.status === null || (record(evidence.status) &&
      (evidence.status.updated === undefined || typeof evidence.status.updated === "string")),
    `${path}.status`, "a run record or null");
    expect(Array.isArray(evidence.derisking) && evidence.derisking.every((approach) =>
      record(approach) && ["approach", "needs"].every((key) =>
        approach[key] === undefined || typeof approach[key] === "string") &&
      (approach.blocked === undefined || typeof approach.blocked === "boolean")),
    `${path}.derisking`, "approach records with optional text and blocked boolean");
    expect(Array.isArray(evidence.artifacts) && evidence.artifacts.every((artifact) =>
      record(artifact) && typeof artifact.path === "string" && numberIn(artifact.bytes, 0, Infinity)),
    `${path}.artifacts`, "file paths and byte counts");
  }
  expect(Array.isArray(value.past_assumptions) && value.past_assumptions.every((entry) =>
    record(entry) && typeof entry.id === "string" && typeof entry.assumption === "string" &&
    (entry.risk == null || numberIn(entry.risk, 0, 1)) &&
    (entry.confidence == null || numberIn(entry.confidence, -1, 1)) &&
    (entry.archived_note === undefined || typeof entry.archived_note === "string")),
  "past_assumptions", "past assumption records");
  if (value.warnings !== undefined) {
    expect(Array.isArray(value.warnings) && value.warnings.every((warning) =>
      record(warning) && typeof warning.path === "string" && typeof warning.message === "string"),
    "warnings", "path and message records");
  }
  return value as unknown as RevisionState;
}