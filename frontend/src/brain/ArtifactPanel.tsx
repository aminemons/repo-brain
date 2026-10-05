import { Background, Controls, MarkerType, Position, ReactFlow, type Edge, type Node } from "@xyflow/react";
import { Download, History } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { getBrainArtifactVersions, getBrainDocumentSection } from "../api/brain";
import { layoutBoxes } from "../graph/layout";
import { MermaidBlock } from "../wiki/mermaid/MermaidBlock";
import type { BrainArtifact, GraphArtifactNode, SourceCard } from "./types";
import { sourceLocation } from "./SourcePanel";
import { errorMessage } from "./useBrainWorkspace";

export function ArtifactPanel({ repoId, artifact, currentSnapshot, sources, onSource }: {
  repoId: string; artifact: BrainArtifact; currentSnapshot?: string;
  sources: SourceCard[]; onSource: (source: SourceCard) => void;
}) {
  const [versions, setVersions] = useState<BrainArtifact[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<BrainArtifact | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState(artifact.spec.nodes[0]?.id ?? "");
  const [showMermaid, setShowMermaid] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [positions, setPositions] = useState<Map<string, { x: number; y: number }> | null>(null);
  const active = selectedVersion ?? artifact;
  const selectedNode = active.spec.nodes.find((node) => node.id === selectedNodeId) ?? active.spec.nodes[0];
  const selectedStep = active.spec.steps.find((step) => step.node_id === selectedNode?.id);
  const stale = Boolean(currentSnapshot && active.source_snapshot_id !== currentSnapshot);

  useEffect(() => {
    let cancelled = false;
    setPositions(null);
    layoutBoxes(active.spec.nodes.map((node) => ({ id: node.id, width: 210, height: 82 })), active.spec.edges, "LR")
      .then((result) => { if (!cancelled) setPositions(result); });
    return () => { cancelled = true; };
  }, [active.spec]);

  const flowNodes = useMemo<Node[]>(() => active.spec.nodes.map((node) => ({
    id: node.id, position: positions?.get(node.id) ?? { x: 0, y: 0 },
    data: { label: <div className="brain-map-label"><strong>{node.name}</strong><span>{node.type}</span></div> },
    sourcePosition: Position.Right, targetPosition: Position.Left,
    selected: node.id === selectedNode?.id,
    style: { width: 210, height: 82 }
  })), [active.spec.nodes, positions, selectedNode?.id]);
  const nodeIds = useMemo(() => new Set(active.spec.nodes.map((node) => node.id)), [active.spec.nodes]);
  const flowEdges = useMemo<Edge[]>(() => active.spec.edges
    .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
    .map((edge) => ({
      id: edge.id, source: edge.source, target: edge.target, label: edge.type,
      markerEnd: { type: MarkerType.ArrowClosed, color: "var(--color-accent)" },
      style: { stroke: "var(--color-accent)", strokeDasharray: edge.is_inferred ? "5 5" : undefined },
      labelStyle: { fill: "var(--color-text-secondary)", fontSize: 10 },
      labelBgStyle: { fill: "var(--color-panel)" }
    })), [active.spec.edges, nodeIds]);

  const loadHistory = async () => {
    setHistoryLoading(true);
    setError(null);
    try { setVersions((await getBrainArtifactVersions(repoId, artifact.id)).artifacts); }
    catch (reason) { setError(errorMessage(reason)); }
    finally { setHistoryLoading(false); }
  };
  const openDoc = async (sectionId: string) => {
    setError(null);
    try { onSource((await getBrainDocumentSection(repoId, sectionId)).source); }
    catch (reason) { setError(errorMessage(reason)); }
  };
  const nodeSource = (node: GraphArtifactNode): SourceCard => sources.find((source) => source.id === node.source_id) ?? {
    id: node.id, type: "code", title: node.name, path: node.file_path,
    start_line: node.start_line ?? 1, end_line: node.end_line ?? node.start_line ?? 1,
    page: null, heading_path: [], excerpt: "", source_snapshot_id: active.source_snapshot_id,
    document_version: null, status: stale ? "stale" : "unknown"
  };
  const download = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(active, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "project-brain-artifact.json";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="brain-artifact" aria-label={active.title}>
      <header className="brain-panel-header">
        <div><h3>{active.title}</h3><p className="brain-muted">Version {active.version} · snapshot <span title={active.source_snapshot_id}>{active.source_snapshot_id.slice(0, 12)}</span></p></div>
        <div className="brain-actions">
          <button type="button" className="icon-button" aria-label="Show artifact versions" onClick={() => void loadHistory()} disabled={historyLoading}><History size={15} /></button>
          <button type="button" className="icon-button" aria-label="Download artifact JSON" onClick={download}><Download size={15} /></button>
        </div>
      </header>
      {versions.length ? <label className="field"><span>Artifact version</span><select value={active.version} onChange={(event) => {
        setSelectedVersion(versions.find((version) => version.version === Number(event.target.value)) ?? null);
      }}>{versions.map((version) => <option value={version.version} key={version.version}>Version {version.version}{version.created_at ? ` · ${version.created_at}` : ""}</option>)}</select></label> : null}
      {stale ? <p className="brain-callout is-warning">This artifact uses an older graph snapshot. Refresh the learning map to inspect the current index.</p> : null}
      {error ? <p className="brain-callout is-warning" role="alert">{error}</p> : null}
      {active.spec.truncated ? <p className="brain-callout">This is a scoped view. Search for a narrower topic to inspect more relevant connections.</p> : null}
      {!active.spec.nodes.length ? <p className="brain-state">No indexed entities are available for this view. Analyze the repository in Graph, then refresh.</p> : (
        <>
          <div className="brain-map" aria-label="Indexed dependency graph">
            {positions ? <ReactFlow
              key={`${active.id}:${active.version}:${active.source_snapshot_id}`}
              nodes={flowNodes} edges={flowEdges} fitView fitViewOptions={{ padding: 0.2 }}
              nodesDraggable={false} nodesConnectable={false} minZoom={0.15} maxZoom={2}
              onNodeClick={(_, node) => setSelectedNodeId(node.id)} proOptions={{ hideAttribution: true }}
            ><Background color="var(--color-graph-grid)" gap={24} /><Controls showInteractive={false} /></ReactFlow> : <p className="brain-state" role="status">Arranging indexed entities…</p>}
          </div>
          <p className="brain-muted">Select a node for its evidence. Dashed edges indicate inferred relationships.</p>
          <div className="brain-walkthrough-layout">
            <nav className="brain-reading-list" aria-label="Project reading path">
              {(active.spec.steps.length ? active.spec.steps : active.spec.nodes.map((node) => ({ node_id: node.id, title: node.name })))
                .map((step) => <button type="button" key={step.node_id} className={selectedNode?.id === step.node_id ? "is-selected" : ""} onClick={() => setSelectedNodeId(step.node_id)}>{step.title}</button>)}
            </nav>
            {selectedNode ? <article className="brain-node-detail">
              <span className="brain-badge">{selectedNode.type}</span><h4>{selectedNode.name}</h4>
              <p>{selectedStep?.explanation ?? selectedNode.description}</p>
              {selectedNode.file_path ? <button type="button" className="brain-source-link" onClick={() => onSource(nodeSource(selectedNode))}>{sourceLocation(nodeSource(selectedNode))}</button> : null}
              {active.spec.edges.filter((edge) => edge.source === selectedNode.id || edge.target === selectedNode.id).map((edge) => {
                const peer = active.spec.nodes.find((node) => node.id === (edge.source === selectedNode.id ? edge.target : edge.source));
                return peer ? <button className="brain-relationship" type="button" key={edge.id} title={edge.provenance} onClick={() => setSelectedNodeId(peer.id)}>
                  <span>{edge.source === selectedNode.id ? "Outgoing" : "Incoming"} {edge.type}{edge.is_inferred ? " (inferred)" : ""}</span><strong>{peer.name}</strong>
                </button> : null;
              })}
              {selectedNode.documentation_ids.length ? <div className="brain-related-docs"><h4>Documentation references</h4>{selectedNode.documentation_ids.map((id) => {
                const source = sources.find((candidate) => candidate.id === id);
                return <button key={id} type="button" className="brain-source-link" onClick={() => source ? onSource(source) : void openDoc(id)}>{source ? sourceLocation(source) : "Open linked document section"}</button>;
              })}</div> : null}
            </article> : null}
          </div>
        </>
      )}
      {active.spec.mermaid ? <details onToggle={(event) => setShowMermaid(event.currentTarget.open)}><summary>Diagram and Mermaid source</summary>{showMermaid ? <MermaidBlock chart={active.spec.mermaid} /> : null}<pre className="brain-raw-spec">{active.spec.mermaid}</pre></details> : null}
    </section>
  );
}
