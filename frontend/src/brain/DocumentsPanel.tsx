import { BookOpenText, History, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";

import { getBrainDocumentVersions, ingestBrainDocument } from "../api/brain";
import { EvidenceMarkdown } from "./EvidenceMarkdown";
import type { DocumentSection, DocumentVersion, IngestDocumentResponse, SourceCard } from "./types";
import { sourceLocation } from "./SourcePanel";
import { errorMessage } from "./useBrainWorkspace";

export function DocumentsPanel({ repoId, documents, query, onRefresh, onSource }: {
  repoId: string; documents: DocumentSection[]; query: string;
  onRefresh: () => void; onSource: (source: SourceCard) => void;
}) {
  const [selectedId, setSelectedId] = useState(documents[0]?.id ?? "");
  const [showIngestion, setShowIngestion] = useState(false);
  const section = documents.find((candidate) => candidate.id === selectedId) ?? documents[0];

  return (
    <div className="brain-documents">
      <div className="brain-panel-header"><p className="brain-muted">{documents.length} matching sections{documents.length === 40 ? " (first 40)" : ""}</p>
        <button type="button" className="brain-button is-secondary" onClick={() => setShowIngestion(!showIngestion)}><Plus size={14} />Add documentation</button>
      </div>
      {showIngestion ? <DocumentIngestion repoId={repoId} onRefresh={onRefresh} /> : null}
      {!documents.length ? <div className="brain-empty"><BookOpenText size={28} /><h3>{query ? "No documentation matches this search" : "Add your project documentation"}</h3><p>{query ? "Try an exact symbol name, file path, or a term from the documentation." : "Add a Markdown, text, or native text PDF file from the selected repository to preserve sections, source references, and links to indexed code."}</p></div> : (
        <div className="brain-doc-layout">
          <nav className="brain-document-list" aria-label="Documentation sections">
            {documents.map((document) => <button type="button" className={document.id === section?.id ? "is-selected" : ""} key={document.id} onClick={() => setSelectedId(document.id)}>
              <strong>{document.heading_path.at(-1) || document.document_title}</strong>
              <span>{document.document_title} · v{document.version}</span>
              <small>{sourceLocation(document.source)}</small>
            </button>)}
          </nav>
          {section ? <DocumentReader key={section.id} section={section} repoId={repoId} onSource={onSource} /> : null}
        </div>
      )}
    </div>
  );
}

function DocumentReader({ repoId, section, onSource }: {
  repoId: string; section: DocumentSection; onSource: (source: SourceCard) => void;
}) {
  const [versions, setVersions] = useState<DocumentVersion[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadHistory = async () => {
    setHistoryLoading(true);
    setError(null);
    try { setVersions(await getBrainDocumentVersions(repoId, section.document_id)); }
    catch (reason) { setError(errorMessage(reason)); }
    finally { setHistoryLoading(false); }
  };
  return (
    <article className="brain-document-reader">
      <header className="brain-panel-header"><div><p className="brain-muted">{section.heading_path.join(" / ")}</p><h3>{section.heading_path.at(-1) || section.document_title}</h3></div><button type="button" className="icon-button" disabled={historyLoading} onClick={() => void loadHistory()} aria-label="Show document versions"><History size={15} /></button></header>
      <div className="brain-source-meta"><span className="brain-badge">{section.authoritative ? "Authoritative documentation" : "Documentation"}</span><span>Version {section.version}</span><span className={`brain-badge ${section.source.status === "stale" ? "is-warning" : ""}`}>{section.source.status}</span></div>
      <button className="brain-source-link" type="button" onClick={() => onSource(section.source)}>{sourceLocation(section.source)}</button>
      {section.source.status === "stale" ? <p className="brain-callout is-warning">The document changed after ingestion. Add it again to refresh sections and references.</p> : null}
      {error ? <p className="brain-callout is-warning" role="alert">{error}</p> : null}
      {versions.length ? <details open><summary>Document version records</summary><ul className="brain-version-list">{versions.map((version) => <li key={version.version}>Version {version.version} · {version.section_count} sections · {version.created_at}<span className="brain-muted" title={version.checksum}>{version.checksum.slice(0, 12)}</span></li>)}</ul></details> : null}
      <div className="brain-markdown"><EvidenceMarkdown>{section.content}</EvidenceMarkdown></div>
      <section className="brain-related-docs">
        <h4>Exact code references</h4>
        <p className="brain-muted">A reference shows where the document mentions code. It does not establish that documented behavior matches the implementation.</p>
        {section.code_links.length ? section.code_links.map((link) => <button type="button" className="brain-relationship" key={link.id} onClick={() => onSource({
          id: link.code_entity_id, type: "code", title: link.code_name, path: link.file_path,
          start_line: link.start_line ?? 1, end_line: link.end_line ?? link.start_line ?? 1,
          page: null, heading_path: [], excerpt: "", source_snapshot_id: link.graph_snapshot_id,
          document_version: null, status: link.stale ? "stale" : "unknown"
        })}><strong>{link.code_name}</strong><span>{link.file_path}:{link.start_line ?? 1}–{link.end_line ?? link.start_line ?? 1} · {link.provenance.replaceAll("_", " ")}{link.stale ? " · stale" : ""}</span></button>) : <p className="brain-muted">No exact references to the current code index were found.</p>}
      </section>
    </article>
  );
}

function DocumentIngestion({ repoId, onRefresh }: { repoId: string; onRefresh: () => void }) {
  const [path, setPath] = useState("");
  const [title, setTitle] = useState("");
  const [authoritative, setAuthoritative] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<IngestDocumentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ingest = async (event: FormEvent) => {
    event.preventDefault();
    if (!path.trim() || loading) return;
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      setResult(await ingestBrainDocument(repoId, { path: path.trim(), title: title.trim() || undefined, authoritative }));
      onRefresh();
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setLoading(false); }
  };
  return (
    <section className="brain-ingestion">
      <h3>Add a document</h3><p className="brain-muted">Use a repository-relative path to an existing .md, .markdown, .txt, or native text .pdf file. Add the file again after changes to create a document version.</p>
      <form className="brain-ingest-form" onSubmit={(event) => void ingest(event)}>
        <label className="field"><span>Document path</span><input value={path} onChange={(event) => setPath(event.target.value)} placeholder="docs/manual.md" required disabled={loading} /></label>
        <label className="field"><span>Title (optional)</span><input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Project documentation" disabled={loading} /></label>
        <label className="brain-checkbox"><input type="checkbox" checked={authoritative} onChange={(event) => setAuthoritative(event.target.checked)} disabled={loading} />Designate as authoritative for intended behavior</label>
        <button className="brain-button" type="submit" disabled={loading || !path.trim()}>{loading ? "Adding document…" : "Add document"}</button>
      </form>
      {error ? <p className="brain-callout is-warning" role="alert">{error}</p> : null}
      {result ? <div className="brain-callout" role="status"><p>{result.changed ? "Document added" : "Document already current"}: version {result.version}, {result.section_count} sections, {result.link_count} exact code references.</p>{result.redacted ? <p>Sensitive text was redacted.</p> : null}{result.warnings.map((warning) => <p key={warning}>{warning}</p>)}</div> : null}
    </section>
  );
}
