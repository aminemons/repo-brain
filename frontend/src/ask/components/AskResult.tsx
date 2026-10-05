import { Sparkles } from "lucide-react";
import { useState } from "react";

import type { AskResponse, SourceRef } from "../../api/types";
import { SourcePanel, sourceLocation } from "../../brain/SourcePanel";
import type { SourceCard } from "../../brain/types";

export function AskResult({
  repoId,
  answer,
  relatedNodeIds,
  onHighlight
}: {
  repoId: string;
  answer: AskResponse;
  relatedNodeIds: string[];
  onHighlight: () => void;
}) {
  const [selectedSource, setSelectedSource] = useState<SourceCard | null>(null);
  const docs = answer.documentation_sources ?? [];
  const answerParts = answer.answer.split(/(\[doc:[^\]]+\])/g);
  return (
    <div className="ask-result">
      <div className="ask-answer">{answerParts.map((part, index) => {
        const id = part.match(/^\[doc:([^\]]+)\]$/)?.[1];
        const source = id ? docs.find((candidate) => candidate.id === id || candidate.id === `doc:${id}`) : null;
        return source ? <button type="button" className="ask-citation" key={index} title={sourceLocation(source)} onClick={() => setSelectedSource(source)}>{part}</button> : part;
      })}</div>

      <button
        className="ask-highlight-button"
        type="button"
        disabled={relatedNodeIds.length === 0}
        onClick={onHighlight}
      >
        <Sparkles size={14} />
        Highlight graph
      </button>

      <AskSources sources={answer.sources} onSource={setSelectedSource} />
      {docs.length ? <div className="ask-section"><h3>Documentation evidence</h3><div className="ask-document-sources">{docs.map((source) => <button type="button" className="brain-relationship" key={source.id} onClick={() => setSelectedSource(source)}><strong>{source.title}</strong><span>{sourceLocation(source)} · {source.status}{source.document_version ? ` · document v${source.document_version}` : ""}</span></button>)}</div></div> : null}
      {selectedSource ? <SourcePanel key={selectedSource.id} repoId={repoId} source={selectedSource} onClose={() => setSelectedSource(null)} /> : null}
      <AskRelatedNodes nodes={answer.related_nodes} />
    </div>
  );
}

function AskSources({ sources, onSource }: { sources: SourceRef[]; onSource: (source: SourceCard) => void }) {
  if (sources.length === 0) {
    return null;
  }
  return (
    <div className="ask-section">
      <h3>Sources</h3>
      <div className="ask-chip-list">
        {sources.slice(0, 8).map((source) => (
          <button type="button" key={`${source.file_path}:${source.start_line}:${source.end_line}`} className="ask-chip ask-source-button" onClick={() => onSource({
            id: `${source.file_path}:${source.start_line}:${source.end_line}`, type: "code", title: source.file_path,
            path: source.file_path, start_line: source.start_line, end_line: source.end_line,
            page: null, heading_path: [], excerpt: "", source_snapshot_id: "", document_version: null, status: "unknown"
          })}>
            {source.file_path}:L{source.start_line}-L{source.end_line}
          </button>
        ))}
      </div>
    </div>
  );
}

function AskRelatedNodes({ nodes }: { nodes: AskResponse["related_nodes"] }) {
  if (nodes.length === 0) {
    return null;
  }
  return (
    <div className="ask-section">
      <h3>Related nodes</h3>
      <div className="ask-node-list">
        {nodes.slice(0, 6).map((node) => (
          <div key={String(node.id)} className="ask-node-row">
            <span>{String(node.name ?? node.id)}</span>
            <strong>{String(node.type ?? "node")}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}
