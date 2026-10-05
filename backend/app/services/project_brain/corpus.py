"""Versioned documents and artifacts in the existing SQLite/PostgreSQL database."""

import hashlib
import json
import re
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from weakref import WeakSet

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    and_,
    func,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.sql.selectable import Join

from backend.app.models import Base
from backend.app.schemas.project_brain import (
    BrainArtifact,
    DocCodeLink,
    DocumentSection,
    DocumentVersion,
)

DOCUMENTS = Table(
    "brain_document",
    Base.metadata,
    Column("id", String(64), primary_key=True),
    Column("repo_id", ForeignKey("repo.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("path", Text, nullable=False),
    Column("source_root_id", String(64), nullable=False),
    Column("current_version", Integer, nullable=False),
)
VERSIONS = Table(
    "brain_document_version",
    Base.metadata,
    Column("document_id", ForeignKey("brain_document.id", ondelete="CASCADE"), primary_key=True),
    Column("version", Integer, primary_key=True),
    Column("checksum", String(64), nullable=False),
    Column("title", Text, nullable=False),
    Column("authoritative", Boolean, nullable=False),
    Column("parser", String(32), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("section_count", Integer, nullable=False),
    Column("graph_snapshot_id", String(64), nullable=False),
)
SECTIONS = Table(
    "brain_document_section",
    Base.metadata,
    Column("id", String(64), primary_key=True),
    Column("document_id", ForeignKey("brain_document.id", ondelete="CASCADE"), nullable=False),
    Column("version", Integer, nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("heading", Text, nullable=False),
    Column("content", Text, nullable=False),
    Column("payload", Text, nullable=False),
)
LINKS = Table(
    "brain_doc_code_link",
    Base.metadata,
    Column("id", String(64), primary_key=True),
    Column(
        "section_id",
        ForeignKey("brain_document_section.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("graph_snapshot_id", String(64), nullable=False),
    Column("payload", Text, nullable=False),
)
ARTIFACTS = Table(
    "brain_artifact_version",
    Base.metadata,
    Column("repo_id", ForeignKey("repo.id", ondelete="CASCADE"), primary_key=True),
    Column("artifact_id", String(64), primary_key=True),
    Column("version", Integer, primary_key=True),
    Column("fingerprint", String(64), nullable=False),
    Column("title", Text, nullable=False),
    Column("payload", Text, nullable=False),
)
TABLES = [DOCUMENTS, VERSIONS, SECTIONS, LINKS, ARTIFACTS]
_SCHEMA_LOCK = threading.Lock()
_READY_ENGINES: WeakSet[Engine] = WeakSet()


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class CurrentDocument:
    id: str
    path: str
    version: int
    checksum: str
    title: str
    authoritative: bool
    graph_snapshot_id: str


class DocumentCorpus:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        with _SCHEMA_LOCK:
            if engine not in _READY_ENGINES:
                Base.metadata.create_all(engine, tables=TABLES)
                self._ensure_lexical_index()
                _READY_ENGINES.add(engine)

    def _ensure_lexical_index(self) -> None:
        with self.engine.begin() as connection:
            if self.engine.dialect.name == "sqlite":
                connection.execute(
                    text(
                        "CREATE VIRTUAL TABLE IF NOT EXISTS brain_section_fts "
                        "USING fts5(section_id UNINDEXED, heading, content, tokenize='unicode61')"
                    )
                )
                connection.execute(
                    text(
                        "CREATE TRIGGER IF NOT EXISTS brain_section_fts_insert "
                        "AFTER INSERT ON brain_document_section BEGIN "
                        "INSERT INTO brain_section_fts(section_id,heading,content) "
                        "VALUES(new.id,new.heading,new.content); END"
                    )
                )
                connection.execute(
                    text(
                        "CREATE TRIGGER IF NOT EXISTS brain_section_fts_delete "
                        "AFTER DELETE ON brain_document_section BEGIN "
                        "DELETE FROM brain_section_fts WHERE section_id=old.id; END"
                    )
                )
            elif self.engine.dialect.name == "postgresql":
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS brain_section_lexical_idx "
                        "ON brain_document_section USING GIN "
                        "(to_tsvector('simple', heading || ' ' || content))"
                    )
                )

    def current_document(self, repo_id: str, document_id: str) -> CurrentDocument | None:
        query = (
            select(DOCUMENTS, VERSIONS)
            .join(
                VERSIONS,
                and_(
                    VERSIONS.c.document_id == DOCUMENTS.c.id,
                    VERSIONS.c.version == DOCUMENTS.c.current_version,
                ),
            )
            .where(DOCUMENTS.c.repo_id == repo_id, DOCUMENTS.c.id == document_id)
        )
        with self.engine.connect() as connection:
            row = connection.execute(query).mappings().first()
        if row is None:
            return None
        return CurrentDocument(
            id=row["id"],
            path=row["path"],
            version=row["current_version"],
            checksum=row["checksum"],
            title=row["title"],
            authoritative=row["authoritative"],
            graph_snapshot_id=row["graph_snapshot_id"],
        )

    def save_document(
        self,
        repo_id: str,
        document_id: str,
        path: str,
        *,
        version: int,
        checksum: str,
        title: str,
        authoritative: bool,
        parser: str,
        sections: list[DocumentSection],
        source_root_id: str,
        graph_snapshot_id: str,
    ) -> None:
        with self.engine.begin() as connection:
            current = connection.execute(
                select(DOCUMENTS.c.id).where(
                    DOCUMENTS.c.id == document_id,
                    DOCUMENTS.c.repo_id == repo_id,
                )
            ).first()
            if current is None:
                connection.execute(
                    insert(DOCUMENTS).values(
                        id=document_id,
                        repo_id=repo_id,
                        path=path,
                        current_version=version,
                        source_root_id=source_root_id,
                    )
                )
            else:
                connection.execute(
                    update(DOCUMENTS)
                    .where(
                        DOCUMENTS.c.id == document_id,
                        DOCUMENTS.c.repo_id == repo_id,
                    )
                    .values(current_version=version)
                )
            connection.execute(
                insert(VERSIONS).values(
                    document_id=document_id,
                    version=version,
                    checksum=checksum,
                    title=title,
                    authoritative=authoritative,
                    parser=parser,
                    created_at=now_iso(),
                    section_count=len(sections),
                    graph_snapshot_id=graph_snapshot_id,
                )
            )
            # Separate batches avoid SQLite parameter ceilings for large manuals.
            for first in range(0, len(sections), 100):
                batch = sections[first : first + 100]
                connection.execute(
                    insert(SECTIONS),
                    [
                        {
                            "id": section.id,
                            "document_id": document_id,
                            "version": version,
                            "ordinal": section.ordinal,
                            "heading": " / ".join(section.heading_path),
                            "content": section.content,
                            "payload": section.model_copy(
                                update={"code_links": []}
                            ).model_dump_json(),
                        }
                        for section in batch
                    ],
                )
                links = [link for section in batch for link in section.code_links]
                if links:
                    connection.execute(
                        insert(LINKS),
                        [
                            {
                                "id": link.id,
                                "section_id": link.doc_section_id,
                                "graph_snapshot_id": link.graph_snapshot_id,
                                "payload": link.model_dump_json(),
                            }
                            for link in links
                        ],
                    )

    def _active_sections(self) -> Join:
        return SECTIONS.join(
            DOCUMENTS,
            and_(
                SECTIONS.c.document_id == DOCUMENTS.c.id,
                SECTIONS.c.version == DOCUMENTS.c.current_version,
            ),
        )

    def search(
        self,
        repo_id: str,
        query: str = "",
        limit: int = 20,
        source_root_id: str = "",
    ) -> list[DocumentSection]:
        limit = max(1, min(limit, 100))
        tokens = re.findall(r"\w+", query, flags=re.UNICODE)[:30]
        meaningful = [
            token
            for token in tokens
            if token.lower()
            not in {
                "a",
                "an",
                "the",
                "is",
                "are",
                "was",
                "were",
                "be",
                "to",
                "of",
                "in",
                "for",
                "and",
                "or",
                "how",
                "what",
                "where",
                "why",
                "when",
                "does",
                "do",
                "this",
                "that",
                "it",
                "me",
                "my",
                "please",
                "explain",
                "implemented",
                "work",
            }
        ]
        tokens = meaningful or tokens
        statement = (
            select(SECTIONS.c.payload)
            .select_from(self._active_sections())
            .where(
                DOCUMENTS.c.repo_id == repo_id,
                DOCUMENTS.c.source_root_id == source_root_id,
            )
            .order_by(DOCUMENTS.c.path, SECTIONS.c.ordinal)
            .limit(limit)
        )
        with self.engine.connect() as connection:
            if tokens and self.engine.dialect.name == "sqlite":
                match = " OR ".join('"' + token + '"' for token in tokens)
                rows = (
                    connection.execute(
                        text(
                            "SELECT s.payload FROM brain_section_fts f "
                            "JOIN brain_document_section s ON s.id=f.section_id "
                            "JOIN brain_document d ON d.id=s.document_id AND d.current_version=s.version "
                            "WHERE d.repo_id=:repo AND d.source_root_id=:root AND brain_section_fts MATCH :query "
                            "ORDER BY bm25(brain_section_fts), d.path,s.ordinal LIMIT :limit"
                        ),
                        {"repo": repo_id, "root": source_root_id, "query": match, "limit": limit},
                    )
                    .scalars()
                    .all()
                )
            elif tokens and self.engine.dialect.name == "postgresql":
                rows = (
                    connection.execute(
                        text(
                            "SELECT s.payload FROM brain_document_section s "
                            "JOIN brain_document d ON d.id=s.document_id AND d.current_version=s.version "
                            "WHERE d.repo_id=:repo AND d.source_root_id=:root AND to_tsvector('simple',s.heading || ' ' || s.content) "
                            "@@ websearch_to_tsquery('simple',:query) "
                            "ORDER BY ts_rank(to_tsvector('simple',s.heading || ' ' || s.content), "
                            "websearch_to_tsquery('simple',:query)) DESC,d.path,s.ordinal LIMIT :limit"
                        ),
                        {
                            "repo": repo_id,
                            "root": source_root_id,
                            "query": " OR ".join('"' + token + '"' for token in tokens),
                            "limit": limit,
                        },
                    )
                    .scalars()
                    .all()
                )
            elif tokens:
                for token in tokens:
                    statement = statement.where(
                        func.lower(SECTIONS.c.content).contains(
                            token.lower(),
                            autoescape=True,
                        )
                    )
                rows = connection.execute(statement).scalars().all()
            elif query.strip():
                # Punctuation-only queries have no searchable lexical terms.
                rows = []
            else:
                rows = connection.execute(statement).scalars().all()
            sections = [DocumentSection.model_validate_json(payload) for payload in rows]
            return self._hydrate_links(connection, sections)

    def _hydrate_links(
        self,
        connection: Connection,
        sections: list[DocumentSection],
    ) -> list[DocumentSection]:
        if not sections:
            return sections
        by_id = {section.id: section for section in sections}
        rows = connection.execute(
            select(LINKS.c.payload).where(
                LINKS.c.section_id.in_(list(by_id)),
            )
        ).scalars()
        for payload in rows:
            link = DocCodeLink.model_validate_json(payload)
            by_id[link.doc_section_id].code_links.append(link)
        return sections

    def section(
        self,
        repo_id: str,
        section_id: str,
        source_root_id: str,
    ) -> DocumentSection | None:
        with self.engine.connect() as connection:
            payload = connection.execute(
                select(SECTIONS.c.payload)
                .join(DOCUMENTS)
                .where(
                    DOCUMENTS.c.repo_id == repo_id,
                    SECTIONS.c.id == section_id,
                    DOCUMENTS.c.source_root_id == source_root_id,
                )
            ).scalar_one_or_none()
            if payload is None:
                return None
            section = DocumentSection.model_validate_json(payload)
            return self._hydrate_links(connection, [section])[0]

    def versions(
        self,
        repo_id: str,
        document_id: str,
        source_root_id: str,
    ) -> list[DocumentVersion]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(VERSIONS)
                    .join(DOCUMENTS)
                    .where(
                        DOCUMENTS.c.repo_id == repo_id,
                        DOCUMENTS.c.id == document_id,
                        DOCUMENTS.c.source_root_id == source_root_id,
                    )
                    .order_by(VERSIONS.c.version.desc())
                )
                .mappings()
                .all()
            )
        return [DocumentVersion.model_validate(dict(row)) for row in rows]

    def counts(
        self,
        repo_id: str,
        graph_snapshot_id: str,
        source_root_id: str,
    ) -> dict[str, int]:
        with self.engine.connect() as connection:
            document_count = connection.execute(
                select(func.count())
                .select_from(DOCUMENTS)
                .where(
                    DOCUMENTS.c.repo_id == repo_id,
                    DOCUMENTS.c.source_root_id == source_root_id,
                )
            ).scalar_one()
            active = self._active_sections()
            section_count = connection.execute(
                select(func.count())
                .select_from(active)
                .where(
                    DOCUMENTS.c.repo_id == repo_id,
                    DOCUMENTS.c.source_root_id == source_root_id,
                )
            ).scalar_one()
            linked = active.join(LINKS, LINKS.c.section_id == SECTIONS.c.id)
            link_count = connection.execute(
                select(func.count())
                .select_from(linked)
                .where(
                    DOCUMENTS.c.repo_id == repo_id,
                    DOCUMENTS.c.source_root_id == source_root_id,
                )
            ).scalar_one()
            stale_count = connection.execute(
                select(func.count())
                .select_from(linked)
                .where(
                    DOCUMENTS.c.repo_id == repo_id,
                    LINKS.c.graph_snapshot_id != graph_snapshot_id,
                    DOCUMENTS.c.source_root_id == source_root_id,
                )
            ).scalar_one()
            artifact_count = connection.execute(
                select(
                    func.count(
                        func.distinct(
                            ARTIFACTS.c.artifact_id,
                        )
                    )
                ).where(ARTIFACTS.c.repo_id == repo_id)
            ).scalar_one()
        return {
            "document_count": document_count,
            "section_count": section_count,
            "link_count": link_count,
            "stale_link_count": stale_count,
            "artifact_count": artifact_count,
        }

    def save_artifact(self, repo_id: str, artifact: BrainArtifact) -> BrainArtifact:
        payload = artifact.model_dump(exclude={"version", "created_at"})
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    select(ARTIFACTS)
                    .where(
                        ARTIFACTS.c.repo_id == repo_id,
                        ARTIFACTS.c.artifact_id == artifact.id,
                    )
                    .order_by(ARTIFACTS.c.version.desc())
                    .limit(1)
                )
                .mappings()
                .first()
            )
            if row is not None and row["fingerprint"] == fingerprint:
                return BrainArtifact.model_validate_json(row["payload"])
            stored = artifact.model_copy(
                update={
                    "version": row["version"] + 1 if row is not None else 1,
                    "created_at": now_iso(),
                }
            )
            connection.execute(
                insert(ARTIFACTS).values(
                    repo_id=repo_id,
                    artifact_id=stored.id,
                    version=stored.version,
                    fingerprint=fingerprint,
                    payload=stored.model_dump_json(),
                    title=stored.title,
                )
            )
        return stored

    def artifact_versions(self, repo_id: str, artifact_id: str) -> list[BrainArtifact]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(ARTIFACTS.c.payload)
                    .where(
                        ARTIFACTS.c.repo_id == repo_id,
                        ARTIFACTS.c.artifact_id == artifact_id,
                    )
                    .order_by(ARTIFACTS.c.version.desc())
                )
                .scalars()
                .all()
            )
        return [BrainArtifact.model_validate_json(payload) for payload in rows]

    def list_artifacts(self, repo_id: str, query: str = "", limit: int = 30) -> list[BrainArtifact]:
        latest = (
            select(
                ARTIFACTS.c.artifact_id,
                func.max(ARTIFACTS.c.version).label("version"),
            )
            .where(ARTIFACTS.c.repo_id == repo_id)
            .group_by(ARTIFACTS.c.artifact_id)
            .subquery()
        )
        statement = (
            select(ARTIFACTS.c.payload)
            .join(
                latest,
                and_(
                    ARTIFACTS.c.artifact_id == latest.c.artifact_id,
                    ARTIFACTS.c.version == latest.c.version,
                ),
            )
            .where(ARTIFACTS.c.repo_id == repo_id)
        )
        if query.strip():
            statement = statement.where(
                func.lower(ARTIFACTS.c.title).contains(
                    query.strip().lower(),
                    autoescape=True,
                )
            )
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    statement.order_by(ARTIFACTS.c.title).limit(
                        max(1, min(limit, 100)),
                    )
                )
                .scalars()
                .all()
            )
        return [BrainArtifact.model_validate_json(payload) for payload in rows]
