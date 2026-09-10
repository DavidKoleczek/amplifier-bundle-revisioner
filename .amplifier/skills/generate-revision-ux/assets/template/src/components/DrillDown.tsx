import type { Artifact, Evidence, RevisionState, Row } from "../types";
import { CATEGORY_HINT, CATEGORY_LABEL, PRIORITY_HINT, bytes, runState, timestamp } from "../format";
import Confidence from "./Confidence";
import Markdown, { artifactHref } from "./Markdown";

export function Document({ title, value, path, artifacts, warning }: {
  title: string; value: string | null; path: string; artifacts: Artifact[]; warning?: boolean;
}) {
  if (warning) return <p className="warning-text">{title} could not be read. See data warnings for details.</p>;
  if (value === null) return <p className="empty">No {title.toLowerCase()} document recorded.</p>;
  if (!value.trim()) return <p className="empty">The {title.toLowerCase()} document is present but empty.</p>;
  return <Markdown text={value} documentPath={path} artifacts={artifacts} />;
}

export function Artifacts({ artifacts, id }: { artifacts: Artifact[]; id: string }) {
  const groups = new Map<string, Artifact[]>();
  for (const artifact of artifacts) {
    const relative = artifact.path.startsWith(`data/${id}/`) ?
      artifact.path.slice(`data/${id}/`.length) : artifact.path;
    const parent = relative.includes("/") ? relative.slice(0, relative.lastIndexOf("/")) : "Root files";
    groups.set(parent, [...(groups.get(parent) ?? []), artifact]);
  }
  return (
    <div className="evidence-section">
      <h3>Artifacts <span className="muted small">({artifacts.length})</span></h3>
      <p className="muted small">Copied files, grouped by folder. Links download the source file.</p>
      {artifacts.length === 0 ? <p className="empty">No artifacts recorded.</p> :
        [...groups.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([parent, files]) => (
          <details className="artifact-group" key={parent}>
            <summary>
              <span className="mono">{parent}</span>
              <span className="muted small"> · {files.length} {files.length === 1 ? "file" : "files"} · {bytes(files.reduce((n, f) => n + f.bytes, 0))}</span>
            </summary>
            <ul className="artifacts">
              {files.map((artifact) => {
                const href = artifactHref(artifact.path);
                const name = artifact.path.slice(artifact.path.lastIndexOf("/") + 1);
                return <li key={artifact.path}>
                  {href ? <a href={href} download>{name}</a> : <span>{name} (invalid artifact path)</span>}
                  <span className="muted small">{bytes(artifact.bytes)}</span>
                </li>;
              })}
            </ul>
          </details>
        ))}
    </div>
  );
}

interface Props {
  row: Row | null;
  evidence: Evidence | null;
  artifacts: Artifact[];
  warnings?: RevisionState["warnings"];
}

export default function DrillDown({ row, evidence, artifacts, warnings = [] }: Props) {
  const documentWarning = (file: string) =>
    warnings.some((warning) => warning.path.endsWith(`data/${row?.id}/${file}`));
  return (
    <section id="evidence" aria-labelledby="evidence-heading">
      <div className="section-heading">
        <div>
          <h2 id="evidence-heading" tabIndex={-1}>Evidence{row ? ` · ${row.id}` : ""}</h2>
          <p className="muted">Source material, not an automated summary.</p>
        </div>
      </div>
      {!row ? <p className="surface empty-state">Select “View evidence” on an assumption to read its findings and artifacts.</p> : (
        <article className="surface drill" key={row.id}>
          <h3 className="assumption detail-assumption">{row.assumption}</h3>
          <div className="card-meta">
            <span className={`tag tag-${row.category}`}>{CATEGORY_LABEL[row.category]}</span>
            <span className="muted small">{CATEGORY_HINT[row.category]}</span>
          </div>
          <div className="detail-metrics">
            <div>
              <h4>Priority</h4>
              <div className="card-meta">
                <strong className="nums">{row.risk.toFixed(2)}</strong>
                {row.high_risk && <span className="tag tag-high">High priority</span>}
              </div>
              <p className="small muted">{PRIORITY_HINT}</p>
              <p className="small">Run: {runState(row.status)}
                {evidence?.status?.updated && <> · Updated <time dateTime={evidence.status.updated}>{timestamp(evidence.status.updated)}</time></>}
              </p>
            </div>
            <div>
              <h4>Confidence</h4>
              <Confidence value={row.confidence} label={`Confidence for ${row.id}`} />
              <p className="small muted">The sign shows direction; magnitude shows evidence strength, not probability. This is the current ledger value, not a historical verdict value.</p>
            </div>
          </div>

          <div className="evidence-section">
            <h3>Findings</h3>
            <Document title="Findings" value={evidence?.findings ?? null}
              path={`data/${row.id}/findings.md`} artifacts={artifacts}
              warning={documentWarning("findings.md")} />
          </div>

          {!!evidence?.derisking.length && (
            <div className="evidence-section">
              <h3>Ways to gather more evidence</h3>
              <p className="muted small">Approaches recorded in the ledger.</p>
              <ol className="approaches">
                {evidence.derisking.map((approach, i) => (
                  <li key={i}>
                    <span className={approach.blocked === true ? "tag tag-blocked" : "tag tag-open"}>
                      {approach.blocked === true ? "Blocked" : approach.blocked === false ?
                        "Not marked blocked" : "Blocking status not recorded"}
                    </span>
                    <p className="source-text">{approach.approach ?? "No approach text recorded."}</p>
                    {approach.needs !== undefined && <p className="source-text small">
                      <strong>Needs: </strong>{approach.needs || "Needs text is empty."}
                    </p>}
                  </li>
                ))}
              </ol>
            </div>
          )}

          <details className="evidence-section disclosure">
            <summary>Spike plan</summary>
            <Document title="Spike plan" value={evidence?.spike_plan ?? null}
              path={`data/${row.id}/spike-plan.md`} artifacts={artifacts}
              warning={documentWarning("spike-plan.md")} />
          </details>
          <details className="evidence-section disclosure">
            <summary>Raw verdict</summary>
            <p className="muted small">Recorded JSON fields, unchanged. The current classification and confidence above come from the ledger.</p>
            {documentWarning("verdict.json") ? (
              <p className="warning-text">The verdict could not be parsed. See data warnings and download the raw verdict from Artifacts.</p>
            ) : evidence?.verdict == null ? <p className="empty">No verdict document recorded.</p> : (
              <pre className="pre">{JSON.stringify(evidence.verdict, null, 2)}</pre>
            )}
          </details>
          <Artifacts artifacts={evidence?.artifacts ?? []} id={row.id} />
        </article>
      )}
    </section>
  );
}