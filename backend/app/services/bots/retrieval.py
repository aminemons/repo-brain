"""Fresh, repository-scoped evidence for bot answers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from backend.app.config import Settings
from backend.app.database import CodeWikiStore
from backend.app.schemas.bots import BotSource
from backend.app.services.analyzer import AnalysisService
from backend.app.services.graphrag import GraphRAGRetriever
from backend.app.services.project_brain.service import ProjectBrainService
from backend.app.services.project_brain.sources import SourceReader
from backend.app.services.project_policy import validate_project_root

MAX_CODE_SOURCES = 6
MAX_DOCUMENT_SOURCES = 3
MAX_EVIDENCE_CHARS = 18_000
MAX_DOCUMENT_FRESHNESS_SECTIONS = 100


@dataclass(frozen=True)
class BotEvidence:
    source: BotSource
    interpretation: str


class BotEvidenceRetriever:
    """Refresh the repository index before retrieval and label each evidence source."""

    def __init__(self, store: CodeWikiStore, settings: Settings) -> None:
        self.store = store
        self.settings = settings

    async def retrieve(self, repo_id: str, query: str) -> list[BotEvidence]:
        repo = self.store.get_repo(repo_id)
        if repo is None:
            raise ValueError("Repository not found")

        # Analyze every chat request. AnalysisService uses file hashes to avoid reparsing
        # unchanged files, while still noticing uncommitted and recently edited sources.
        analysis = await asyncio.to_thread(AnalysisService(store=self.store).analyze, repo_id)
        if analysis.status != "done":
            raise ValueError("Repository analysis did not complete")

        retriever = GraphRAGRetriever(store=self.store, settings=self.settings)
        if analysis.mode != "unchanged":
            build = await retriever.build_index(repo_id, include_embeddings=False)
            if build.status not in {"built", "empty_graph"}:
                raise ValueError("Repository evidence index could not be refreshed")
        trace = await retriever.retrieve(repo_id, query, include_embeddings=False)

        nodes, _edges = await asyncio.to_thread(self.store.get_graph, repo_id)
        hashes_by_path = {
            node.file_path: node.hash
            for node in nodes
            if node.type == "file" and node.file_path and node.hash
        }
        root = validate_project_root(repo.path)
        reader = SourceReader(root)
        results: list[BotEvidence] = []
        used_chars = 0

        for item in trace.source_chunks[:MAX_CODE_SOURCES]:
            path = str(item.get("file_path") or "")
            start = _int(item.get("start_line"), 1)
            end = _int(item.get("end_line"), start)
            try:
                excerpt = reader.excerpt(repo_id, path, start, end)
            except (ValueError, OSError):
                continue
            expected_hash = hashes_by_path.get(excerpt.file_path)
            if expected_hash is None or excerpt.source_snapshot_id != expected_hash:
                # The filesystem changed after analysis. Fail closed instead of citing a
                # live excerpt against stale graph spans or chunks.
                raise ValueError("Repository changed while evidence was being retrieved")
            snippet = excerpt.content[: min(6_000, MAX_EVIDENCE_CHARS - used_chars)]
            if not snippet.strip():
                continue
            source = BotSource(
                id=f"S{len(results) + 1}",
                type="code",
                path=excerpt.file_path,
                start_line=excerpt.start_line,
                end_line=excerpt.start_line + snippet.count("\n"),
                snippet=snippet,
            )
            results.append(BotEvidence(
                source=source,
                interpretation="Current code implementation. Static source does not prove runtime behavior.",
            ))
            used_chars += len(snippet)
            if used_chars >= MAX_EVIDENCE_CHARS:
                return results

        try:
            brain = ProjectBrainService(
                store=self.store,
                settings=_project_settings(self.settings, repo.path),
            )
            # Refresh a bounded set of indexed document source checksums before ranking
            # sections for this query. The targeted search also refreshes its own results,
            # so changed files cannot be cited even when they fall outside this preflight.
            brain.search_documents(repo_id, "", limit=MAX_DOCUMENT_FRESHNESS_SECTIONS)
            documents = brain.search_documents(repo_id, query, limit=MAX_DOCUMENT_SOURCES)
        except (ValueError, OSError):
            documents = None
        if documents is not None:
            for section in documents.results:
                # Archived document versions may remain useful in Project Brain history,
                # but they cannot support a current bot answer.
                if section.source.status != "current":
                    continue
                remaining = MAX_EVIDENCE_CHARS - used_chars
                if remaining <= 0:
                    break
                snippet = section.content[: min(4_000, remaining)]
                if not snippet.strip():
                    continue
                source = BotSource(
                    id=f"S{len(results) + 1}",
                    type="documentation",
                    path=section.source.path,
                    start_line=section.source.start_line,
                    end_line=section.source.end_line,
                    snippet=snippet,
                )
                status = "authoritative" if section.authoritative else "unreviewed"
                results.append(BotEvidence(
                    source=source,
                    interpretation=(
                        f"Current documentation, version {section.version}, {status}; "
                        "documents describe intended behavior, not necessarily implementation."
                    ),
                ))
                used_chars += len(snippet)
        return results


def format_evidence(evidence: list[BotEvidence]) -> str:
    return "\n\n".join(
        f"[{item.source.id}] {item.interpretation}\n"
        f"{item.source.path}:{item.source.start_line}-{item.source.end_line}\n"
        f"{item.source.snippet}"
        for item in evidence
    )


def _project_settings(settings: Settings, repo_path: str) -> Settings:
    project_settings = settings.model_copy(deep=True)
    configured_root = project_settings.project_root
    if configured_root is None or configured_root.expanduser().resolve() != Path(repo_path).resolve():
        project_settings.documentation_root = None
    return project_settings


def _int(value: object, default: int) -> int:
    return value if isinstance(value, int) else default
