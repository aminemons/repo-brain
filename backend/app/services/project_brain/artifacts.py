"""Deterministic scoped graph selection and teaching steps from indexed facts."""

import hashlib
import html
import re
from collections import defaultdict, deque

from backend.app.schemas.project_brain import (
    BrainArtifact,
    GraphArtifactEdge,
    GraphArtifactNode,
    GraphArtifactSpec,
    WalkthroughStep,
)
from backend.app.services.graph.models import CodeGraphEdge, CodeGraphNode

STRUCTURAL_TYPES = {"repository", "directory", "file", "module"}
RELATIONSHIP_TYPES = {
    "calls",
    "imports",
    "inherits",
    "implements",
    "routes_to",
    "uses_config",
    "references",
    "contains",
    "defines",
}


def select_subgraph(
    nodes: list[CodeGraphNode],
    edges: list[CodeGraphEdge],
    query: str,
    limit: int,
) -> tuple[list[CodeGraphNode], list[CodeGraphEdge], bool]:
    """Exact lexical seeds, then bounded graph neighbors; no invented topology."""
    limit = max(1, min(limit, 60))
    by_id = {node.id: node for node in nodes}
    terms = re.findall(r"[\w./-]+", query.lower())
    adjacency: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, int] = defaultdict(int)
    for edge in edges:
        if edge.type not in RELATIONSHIP_TYPES:
            continue
        if edge.source_id in by_id and edge.target_id in by_id:
            adjacency[edge.source_id].append(edge.target_id)
            adjacency[edge.target_id].append(edge.source_id)
            if edge.type == "calls":
                incoming[edge.target_id] += 1

    def score(node: CodeGraphNode) -> tuple[int, int, str, str]:
        name, path = node.name.lower(), node.file_path.lower()
        matches = sum(
            10 if term == name else 4 if term in name else 1 if term in path else 0
            for term in terms
        )
        useful = int(node.type not in STRUCTURAL_TYPES)
        entry = int(node.type == "route" or not incoming[node.id])
        return (-matches, -(useful * 3 + entry), node.file_path, node.id)

    ranked = sorted((node for node in nodes if node.file_path), key=score)
    if terms:
        ranked = [node for node in ranked if score(node)[0] < 0]
    if not ranked:
        return [], [], False
    seeds = [node.id for node in ranked[: max(1, min(4, limit // 3))]]
    selected = list(seeds)
    seen = set(seeds)
    queue: deque[tuple[str, int]] = deque((seed, 0) for seed in seeds)
    while queue and len(selected) < limit:
        node_id, depth = queue.popleft()
        if depth >= 2:
            continue
        neighbors = sorted(adjacency[node_id], key=lambda item: score(by_id[item]))
        for neighbor in neighbors:
            if neighbor in seen or not by_id[neighbor].file_path:
                continue
            if by_id[neighbor].type in {"repository", "directory", "module"}:
                continue
            seen.add(neighbor)
            selected.append(neighbor)
            queue.append((neighbor, depth + 1))
            if len(selected) >= limit:
                break
    # Unconnected lexical matches still deserve representation.
    for node in ranked:
        if len(selected) >= limit:
            break
        if node.id not in seen:
            selected.append(node.id)
            seen.add(node.id)
    scoped = [edge for edge in edges if edge.source_id in seen and edge.target_id in seen]
    truncated = len(scoped) > 150 or len(ranked) > len(selected)
    return [by_id[item] for item in selected], scoped[:150], truncated


def graph_artifact(
    repo_id: str,
    name: str,
    query: str,
    snapshot: str,
    nodes: list[GraphArtifactNode],
    edges: list[CodeGraphEdge],
    *,
    walkthrough: bool,
    truncated: bool,
) -> BrainArtifact:
    kind = "interactive_walkthrough" if walkthrough else "architecture_graph"
    identity = hashlib.sha256(f"{repo_id}\x00{kind}\x00{query.strip()}".encode()).hexdigest()[:32]
    node_ids = {node.id for node in nodes}
    artifact_edges = [
        GraphArtifactEdge(
            id=edge.id,
            source=edge.source_id,
            target=edge.target_id,
            type=edge.type,
            is_inferred=edge.is_inferred,
            provenance="graph_inference" if edge.is_inferred else "indexed_graph",
        )
        for edge in edges
        if edge.source_id in node_ids and edge.target_id in node_ids
    ]
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in artifact_edges:
        if edge.type in {"calls", "routes_to", "uses_config"}:
            outgoing[edge.source].append(edge.target)
    steps = (
        [
            WalkthroughStep(
                node_id=node.id,
                title=node.name,
                explanation=node.description,
                source_ids=([node.source_id] if node.source_id else []) + node.documentation_ids,
                next_node_ids=sorted(set(outgoing[node.id])),
            )
            for node in nodes
        ]
        if walkthrough
        else []
    )
    return BrainArtifact(
        id=identity,
        type=kind,
        title=f"{query.strip() or name} {'walkthrough' if walkthrough else 'architecture'}",
        source_snapshot_id=snapshot,
        spec=GraphArtifactSpec(
            nodes=nodes,
            edges=artifact_edges,
            mermaid=_mermaid(nodes, artifact_edges),
            steps=steps,
            truncated=truncated,
        ),
    )


def _safe_label(value: str) -> str:
    # Mermaid gets inert labels only: no user-supplied syntax, links or directives.
    value = html.escape(value, quote=True).replace("\n", " ").replace("\r", " ")
    return re.sub(r"[^\w ./:&;#-]", " ", value)[:120]


def _mermaid(nodes: list[GraphArtifactNode], edges: list[GraphArtifactEdge]) -> str:
    ids = {node.id: f"n{index}" for index, node in enumerate(nodes)}
    lines = ["flowchart LR"]
    for node in nodes:
        lines.append(f'    {ids[node.id]}["{_safe_label(node.name)}"]')
    for edge in edges:
        arrow = "-.->" if edge.is_inferred else "-->"
        lines.append(f"    {ids[edge.source]} {arrow}|{_safe_label(edge.type)}| {ids[edge.target]}")
    return "\n".join(lines)
