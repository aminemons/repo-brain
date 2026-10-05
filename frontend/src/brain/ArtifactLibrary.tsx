import { PanelsTopLeft } from "lucide-react";
import { useState } from "react";

import { ArtifactPanel } from "./ArtifactPanel";
import type { BrainArtifact, SourceCard } from "./types";

export function ArtifactLibrary({ repoId, artifacts, currentSnapshot, onSource }: {
  repoId: string; artifacts: BrainArtifact[]; currentSnapshot?: string; onSource: (source: SourceCard) => void;
}) {
  const [selectedId, setSelectedId] = useState(artifacts[0]?.id ?? "");
  const selected = artifacts.find((artifact) => artifact.id === selectedId) ?? artifacts[0];
  if (!selected) return <div className="brain-empty"><PanelsTopLeft size={28} /><h3>No saved artifacts match this view</h3><p>Open Learning map to build a walkthrough from the repository index. Its graph snapshot and versions appear here.</p></div>;
  return <div className="brain-doc-layout">
    <nav className="brain-document-list" aria-label="Saved artifacts">{artifacts.map((artifact) => <button type="button" key={artifact.id} className={selected.id === artifact.id ? "is-selected" : ""} onClick={() => setSelectedId(artifact.id)}><strong>{artifact.title}</strong><span>{artifact.type.replaceAll("_", " ")} · v{artifact.version}</span><small title={artifact.source_snapshot_id}>Snapshot {artifact.source_snapshot_id.slice(0, 12)}</small></button>)}</nav>
    <ArtifactPanel key={`${selected.id}:${selected.version}`} repoId={repoId} artifact={selected} currentSnapshot={currentSnapshot} sources={[]} onSource={onSource} />
  </div>;
}
