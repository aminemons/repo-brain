import { BookOpenText, GraduationCap, PanelsTopLeft, RefreshCw, Search } from "lucide-react";
import { useState, type FormEvent } from "react";

import { ArtifactLibrary } from "../brain/ArtifactLibrary";
import { DocumentsPanel } from "../brain/DocumentsPanel";
import { LearningPanel } from "../brain/LearningPanel";
import { SourcePanel } from "../brain/SourcePanel";
import type { SourceCard } from "../brain/types";
import { useBrainWorkspace, type BrainView } from "../brain/useBrainWorkspace";
import { useRepos } from "../hooks/useRepos";

export function BrainPage({ selectedRepoId, onRepoChange }: {
  selectedRepoId: string; onRepoChange: (repoId: string) => void;
}) {
  const { repos, loading, selectedRepo, error } = useRepos({ selectedRepoId, onRepoChange });
  return <section id="brain" className="side-panel brain-page">
    <header className="ops-header"><div><h2>Learn your project</h2><p className="brain-muted">Read the code and documentation behind each explanation.</p></div><span className="brain-badge">Read only</span></header>
    <div className="ops-toolbar">
      <label className="field"><span>Repository</span><select value={selectedRepoId} onChange={(event) => onRepoChange(event.target.value)}>
        {!repos.length ? <option value="">No repositories</option> : null}
        {repos.map((repo) => <option key={repo.id} value={repo.id}>{repo.name}</option>)}
      </select></label>
      {selectedRepo ? <div className="ops-path">{selectedRepo.path}</div> : null}
    </div>
    {loading ? <p className="brain-state" role="status">Loading repositories…</p> : null}
    {error ? <p className="brain-callout is-warning" role="alert">{error}</p> : null}
    {!loading && !error && !selectedRepoId ? <div className="brain-empty"><BookOpenText size={28} /><h3>Select your repository</h3><p>Add your project in Repos, analyze it in Graph, then open its learning map and documentation.</p><a className="brain-button" href="/repos">Open Repos</a></div> : null}
    {selectedRepoId ? <BrainWorkspace key={selectedRepoId} repoId={selectedRepoId} /> : null}
  </section>;
}

function BrainWorkspace({ repoId }: { repoId: string }) {
  const [view, setView] = useState<BrainView>("learn");
  const [queryInput, setQueryInput] = useState("");
  const [query, setQuery] = useState("");
  const [source, setSource] = useState<SourceCard | null>(null);
  const { status, statusError, answer, documents, artifacts, loading, error, refresh } = useBrainWorkspace(repoId, view, query);
  const search = (event: FormEvent) => {
    event.preventDefault();
    setSource(null);
    if (queryInput.trim() === query) refresh();
    else setQuery(queryInput.trim());
  };
  const changeView = (next: BrainView) => { setView(next); setSource(null); };
  return <div className="brain-workspace">
    {status ? <div className="brain-status-strip" aria-label="Knowledge index status">
      <span><strong>{status.code_node_count.toLocaleString()}</strong> code entities</span>
      <span><strong>{status.document_count.toLocaleString()}</strong> documents</span>
      <span><strong>{status.section_count.toLocaleString()}</strong> sections</span>
      <span><strong>{status.link_count.toLocaleString()}</strong> code references</span>
      {status.stale_link_count ? <span className="brain-warning-text">{status.stale_link_count} stale references</span> : null}
      <span title={status.graph_snapshot_id}>Graph snapshot {status.graph_snapshot_id.slice(0, 12)}</span>
    </div> : null}
    {statusError ? <p className="brain-callout is-warning" role="alert">{statusError}</p> : null}
    <div className="brain-toolbar">
      <nav className="brain-tabs" aria-label="Project Brain views">
        <button type="button" className={view === "learn" ? "is-active" : ""} aria-current={view === "learn" ? "page" : undefined} onClick={() => changeView("learn")}><GraduationCap size={16} />Learning map</button>
        <button type="button" className={view === "documents" ? "is-active" : ""} aria-current={view === "documents" ? "page" : undefined} onClick={() => changeView("documents")}><BookOpenText size={16} />Documentation</button>
        <button type="button" className={view === "artifacts" ? "is-active" : ""} aria-current={view === "artifacts" ? "page" : undefined} onClick={() => changeView("artifacts")}><PanelsTopLeft size={16} />Artifacts</button>
      </nav>
      <button type="button" className="icon-button" aria-label="Refresh project knowledge" onClick={refresh} disabled={loading}><RefreshCw size={15} /></button>
    </div>
    <form className="brain-search" onSubmit={search}>
      <label className="ops-search"><Search size={15} /><input aria-label={view === "documents" ? "Search documentation" : view === "artifacts" ? "Search saved artifacts" : "Focus learning map"} value={queryInput} onChange={(event) => setQueryInput(event.target.value)} placeholder={view === "artifacts" ? "Search saved artifact titles" : "Search by symbol, file path, or documented term"} /></label>
      <button className="brain-button" type="submit" disabled={loading}>{view === "learn" ? "Build reading map" : "Search"}</button>
      {query ? <button className="brain-button is-secondary" type="button" onClick={() => { setQueryInput(""); setQuery(""); setSource(null); }}>Clear search</button> : null}
    </form>
    {loading ? <p className="brain-state" role="status">{view === "learn" ? "Building a reading map from indexed evidence…" : "Loading project evidence…"}</p> : null}
    {error ? <p className="brain-callout is-warning" role="alert">{error}</p> : null}
    <div className={`brain-content${source ? " has-source" : ""}`}>
      <div className="brain-main-content">
        {!loading && !error && view === "learn" && answer ? <LearningPanel key={answer.answer_id} repoId={repoId} answer={answer} currentSnapshot={status?.graph_snapshot_id} onSource={setSource} /> : null}
        {!error && view === "documents" ? <DocumentsPanel repoId={repoId} documents={documents} query={query} onRefresh={refresh} onSource={setSource} /> : null}
        {!loading && !error && view === "artifacts" ? <ArtifactLibrary repoId={repoId} artifacts={artifacts} currentSnapshot={status?.graph_snapshot_id} onSource={setSource} /> : null}
      </div>
      {source ? <SourcePanel key={source.id} repoId={repoId} source={source} onClose={() => setSource(null)} /> : null}
    </div>
    {status?.limitations.length ? <details className="brain-limitations"><summary>Available scope and limitations</summary><ul>{status.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul><p className="brain-muted">Document formats: {status.document_formats.join(", ")}</p></details> : null}
  </div>;
}
