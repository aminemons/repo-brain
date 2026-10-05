"""Exact document references; an exact mention never proves behavioral agreement."""

import hashlib
import re
from collections import defaultdict
from typing import Literal

from backend.app.schemas.project_brain import DocCodeLink, DocumentSection
from backend.app.services.graph.models import CodeGraphEdge, CodeGraphNode

LinkProvenance = Literal["exact_symbol", "exact_path", "exact_route", "exact_config"]
LEXICAL_TERMS = re.compile(r"[\w./:{}-]+", re.UNICODE)


def graph_snapshot(nodes: list[CodeGraphNode], edges: list[CodeGraphEdge]) -> str:
    digest = hashlib.sha256()
    for node in sorted(nodes, key=lambda item: item.id):
        digest.update(
            repr(
                (
                    node.id,
                    node.type,
                    node.name,
                    node.file_path,
                    node.start_line,
                    node.end_line,
                    node.hash,
                )
            ).encode()
        )
    for edge in sorted(edges, key=lambda item: item.id):
        digest.update(
            repr(
                (
                    edge.id,
                    edge.source_id,
                    edge.target_id,
                    edge.type,
                    edge.is_inferred,
                    edge.confidence,
                )
            ).encode()
        )
    return digest.hexdigest()


def link_sections(
    sections: list[DocumentSection],
    nodes: list[CodeGraphNode],
    snapshot: str,
) -> None:
    references: dict[str, list[tuple[CodeGraphNode, LinkProvenance]]] = defaultdict(list)
    for node in nodes:
        if not node.file_path or node.type in {"repository", "directory", "module"}:
            continue
        if node.type in {"file", "config"}:
            references[node.file_path].append((node, "exact_path"))
        elif len(node.name) >= 3:
            references[node.name].append((node, "exact_symbol"))
        route = node.metadata.get("route_path")
        if isinstance(route, str) and route.startswith("/"):
            references[route].append((node, "exact_route"))
        config_key = node.metadata.get("config_key")
        if isinstance(config_key, str) and len(config_key) >= 3:
            references[config_key].append((node, "exact_config"))
    for section in sections:
        # A term index avoids scanning every graph symbol for every manual chunk.
        candidates: set[str] = set()
        for term in LEXICAL_TERMS.findall(section.content):
            candidates.add(term)
            candidates.add(term.strip(".:"))
            candidates.update(part for part in term.split(".") if part)
            candidates.update(part for part in term.split("/") if part)
        linked: set[tuple[str, str]] = set()
        for reference in sorted(candidates & references.keys()):
            if not re.search(r"(?<![\w])" + re.escape(reference) + r"(?![\w])", section.content):
                continue
            for node, provenance in references[reference]:
                identity = (node.id, provenance)
                if identity in linked:
                    continue
                linked.add(identity)
                link_id = hashlib.sha256(
                    f"{section.id}\x00{node.id}\x00{provenance}".encode(),
                ).hexdigest()[:32]
                section.code_links.append(
                    DocCodeLink(
                        id=link_id,
                        doc_section_id=section.id,
                        code_entity_id=node.id,
                        code_name=node.name,
                        file_path=node.file_path,
                        start_line=node.start_line,
                        end_line=node.end_line,
                        provenance=provenance,
                        reference=reference,
                        graph_snapshot_id=snapshot,
                    )
                )
                if len(section.code_links) >= 200:
                    break
            if len(section.code_links) >= 200:
                break
