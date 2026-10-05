import { Network } from "lucide-react";
import { useState } from "react";

import { ArtifactPanel } from "./ArtifactPanel";
import { EvidenceMarkdown } from "./EvidenceMarkdown";
import type { BrainAnswer, ClaimStatus, SourceCard } from "./types";
import { sourceLocation } from "./SourcePanel";

const claimLabels: Record<ClaimStatus, string> = {
  VERIFIED_CODE: "Verified code", VERIFIED_TEST: "Verified test", DOCUMENTED: "Documented",
  CORROBORATED: "Corroborated", INFERRED: "Inferred", CONFLICT: "Conflict", UNKNOWN: "Unknown"
};

export function LearningPanel({ repoId, answer, currentSnapshot, onSource }: {
  repoId: string; answer: BrainAnswer; currentSnapshot?: string; onSource: (source: SourceCard) => void;
}) {
  const [artifactId, setArtifactId] = useState(answer.artifacts[0]?.id ?? "");
  const artifact = answer.artifacts.find((item) => item.id === artifactId) ?? answer.artifacts[0];
  const sourceById = new Map(answer.sources.map((source) => [source.id, source]));
  return (
    <div className="brain-learning">
      <p className="brain-learning-summary">{answer.summary}</p>
      <p className="brain-muted">This reading map uses indexed structure and documentation. Inspect the source to establish behavior.</p>
      {answer.sections.map((section, index) => <section className={section.type === "prose" ? "brain-answer-section" : `brain-callout ${section.type === "warning" ? "is-warning" : ""}`} key={index}><h3>{section.title}</h3><div className="brain-markdown"><EvidenceMarkdown>{section.markdown}</EvidenceMarkdown></div></section>)}
      {answer.artifacts.length > 1 ? <div className="brain-tabs" aria-label="Learning artifacts">{answer.artifacts.map((item) => <button type="button" className={artifact?.id === item.id ? "is-active" : ""} key={item.id} onClick={() => setArtifactId(item.id)}>{item.title}</button>)}</div> : null}
      {artifact ? <ArtifactPanel key={`${artifact.id}:${artifact.version}`} repoId={repoId} artifact={artifact} currentSnapshot={currentSnapshot} sources={answer.sources} onSource={onSource} /> : <div className="brain-empty"><Network size={28} /><h3>No indexed learning map yet</h3><p>Analyze the repository in Graph, then refresh. Search for a symbol or file to focus the reading map.</p></div>}
      {answer.claims.length ? <details className="brain-claims"><summary>Evidence behind this map ({answer.claims.length} claims)</summary>{answer.claims.map((claim) => <article key={claim.id} className="brain-claim"><span className={`brain-badge ${["CONFLICT", "UNKNOWN", "INFERRED"].includes(claim.status) ? "is-warning" : ""}`}>{claimLabels[claim.status]}</span><p>{claim.claim}</p>{claim.note ? <p className="brain-muted">{claim.note}</p> : null}{claim.evidence_ids.map((id) => {
        const source = sourceById.get(id);
        return source ? <button type="button" className="brain-source-link" key={id} onClick={() => onSource(source)}>{sourceLocation(source)}</button> : <span key={id} className="brain-muted">Evidence reference unavailable: {id}</span>;
      })}</article>)}</details> : null}
      {answer.sources.length ? <details><summary>Source reading list ({answer.sources.length})</summary><div className="brain-reading-sources">{answer.sources.map((source) => <button type="button" key={source.id} className="brain-source-link" onClick={() => onSource(source)}>{source.title}<small>{sourceLocation(source)}</small></button>)}</div></details> : null}
    </div>
  );
}
