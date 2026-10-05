import { Copy, GitBranch, X } from "lucide-react";
import { useEffect, useState } from "react";

import { getBrainSource } from "../api/brain";
import { openSourceInGraph } from "../wiki/sourceNavigation";
import type { SourceCard, SourceExcerpt } from "./types";
import { errorMessage } from "./useBrainWorkspace";

export function SourcePanel({ repoId, source, onClose }: {
  repoId: string; source: SourceCard; onClose: () => void;
}) {
  const [excerpt, setExcerpt] = useState<SourceExcerpt | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setExcerpt(null);
    setError(null);
    setCopied(false);
    setLoading(false);
    if (source.excerpt) return;
    const controller = new AbortController();
    setLoading(true);
    getBrainSource(repoId, source.path, source.start_line, source.end_line, controller.signal, source.type)
      .then(setExcerpt).catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(errorMessage(reason));
      }).finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [repoId, source]);

  const content = source.excerpt || excerpt?.content || "";
  const firstLine = excerpt?.start_line ?? source.start_line;
  const lastLine = excerpt?.end_line ?? source.end_line;
  const copyExcerpt = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
    } catch {
      setError("Copy was unavailable. Select the excerpt to copy it.");
    }
  };

  return (
    <aside className="brain-source-panel" aria-label="Source evidence">
      <header className="brain-panel-header">
        <div><span className="brain-muted">{source.type === "code" ? "Code evidence" : "Documentation evidence"}</span><h3>{source.title}</h3></div>
        <button className="icon-button" type="button" onClick={onClose} aria-label="Close source"><X size={15} /></button>
      </header>
      <p className="brain-source-location">{sourceLocation({ ...source, start_line: firstLine, end_line: lastLine })}</p>
      {source.heading_path.length ? <p className="brain-muted">{source.heading_path.join(" / ")}</p> : null}
      <div className="brain-source-meta">
        <span className={`brain-badge ${source.status === "stale" ? "is-warning" : ""}`}>{source.status}</span>
        {source.document_version ? <span>Document version {source.document_version}</span> : null}
        <span title={source.source_snapshot_id}>Evidence snapshot {source.source_snapshot_id.slice(0, 12) || "unavailable"}</span>
      </div>
      {excerpt ? <p className="brain-muted" title={excerpt.source_snapshot_id}>Read snapshot {excerpt.source_snapshot_id.slice(0, 12)}</p> : null}
      {source.status === "stale" ? <p className="brain-callout is-warning">The indexed source has changed. Refresh the index or document before using it to establish current behavior.</p> : null}
      {loading ? <p className="brain-state" role="status">Reading source…</p> : null}
      {error ? <p className="brain-callout is-warning" role="alert">{error}</p> : null}
      {excerpt?.redacted ? <p className="brain-callout">Sensitive text was redacted.</p> : null}
      {excerpt?.truncated ? <p className="brain-callout">This excerpt is bounded. Open the file in the graph for context.</p> : null}
      {source.excerpt && content.split("\n").length < lastLine - firstLine + 1 ? <p className="brain-muted">This preview shows part of the cited source range.</p> : null}
      {content ? (
        <div className="brain-code" tabIndex={0} aria-label={`Source lines ${firstLine} to ${lastLine}`}>
          {content.split("\n").map((line, index) => (
            <div className="brain-code-line" key={index}><span aria-hidden="true">{firstLine + index}</span><code>{line || " "}</code></div>
          ))}
        </div>
      ) : !loading && !error ? <p className="brain-state">No source text is available for this reference.</p> : null}
      <div className="brain-actions">
        <button className="brain-button is-secondary" type="button" disabled={!content} onClick={() => void copyExcerpt()}><Copy size={14} />{copied ? "Copied" : "Copy excerpt"}</button>
        {source.type === "code" ? <button className="brain-button is-secondary" type="button" onClick={() => openSourceInGraph(repoId, {
          file_path: source.path, start_line: source.start_line, end_line: source.end_line
        })}><GitBranch size={14} />Open in graph</button> : null}
      </div>
    </aside>
  );
}

export function sourceLocation(source: SourceCard): string {
  if (source.page && source.path.toLowerCase().endsWith(".pdf")) {
    return `${source.path} · page ${source.page}, extracted text lines ${source.start_line}–${source.end_line}`;
  }
  return `${source.path}:${source.start_line}–${source.end_line}${source.page ? ` (page ${source.page})` : ""}`;
}
