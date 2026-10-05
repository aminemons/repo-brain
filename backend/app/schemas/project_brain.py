"""Typed, source-grounded Project Brain API and artifact protocol."""

from typing import Literal

from pydantic import BaseModel, Field

ClaimStatus = Literal[
    "VERIFIED_CODE",
    "VERIFIED_TEST",
    "DOCUMENTED",
    "CORROBORATED",
    "INFERRED",
    "CONFLICT",
    "UNKNOWN",
]


class SourceCard(BaseModel):
    id: str
    type: Literal["code", "documentation"]
    title: str
    path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    page: int | None = None
    heading_path: list[str] = Field(default_factory=list)
    excerpt: str = ""
    source_snapshot_id: str
    document_version: int | None = None
    status: Literal["current", "stale", "unknown"] = "current"


class SourceExcerpt(BaseModel):
    repo_id: str
    file_path: str
    start_line: int
    end_line: int
    content: str
    source_snapshot_id: str
    redacted: bool = False
    truncated: bool = False


class DocCodeLink(BaseModel):
    id: str
    doc_section_id: str
    code_entity_id: str
    code_name: str
    file_path: str
    start_line: int | None = None
    end_line: int | None = None
    relation: Literal["REFERENCES"] = "REFERENCES"
    provenance: Literal["exact_symbol", "exact_path", "exact_route", "exact_config"]
    verification: Literal["exact_reference"] = "exact_reference"
    reference: str
    graph_snapshot_id: str
    stale: bool = False


class DocumentSection(BaseModel):
    id: str
    document_id: str
    document_title: str
    version: int
    authoritative: bool
    parent_id: str | None = None
    level: int
    ordinal: int
    heading_path: list[str]
    content_type: Literal["text", "code", "table", "mixed"]
    content: str
    source: SourceCard
    code_links: list[DocCodeLink] = Field(default_factory=list)


class DocumentSearchResponse(BaseModel):
    repo_id: str
    query: str
    results: list[DocumentSection]
    limit: int
    retrieval: Literal["lexical"] = "lexical"


class IngestDocumentRequest(BaseModel):
    path: str = Field(min_length=1, max_length=1024)
    title: str | None = Field(default=None, max_length=300)
    authoritative: bool = False


class IngestDocumentResponse(BaseModel):
    repo_id: str
    document_id: str
    version: int
    path: str
    checksum: str
    section_count: int
    link_count: int
    changed: bool
    redacted: bool
    parser: Literal["native_markdown", "native_text", "native_pdf"]
    warnings: list[str] = Field(default_factory=list)


class DocumentVersion(BaseModel):
    document_id: str
    version: int
    checksum: str
    title: str
    authoritative: bool
    parser: str
    created_at: str
    section_count: int


class BrainStatus(BaseModel):
    repo_id: str
    project_name: str
    mode: Literal["read_only"] = "read_only"
    graph_snapshot_id: str
    code_node_count: int
    code_edge_count: int
    document_count: int
    section_count: int
    link_count: int
    stale_link_count: int
    artifact_count: int
    document_formats: list[str] = Field(
        default_factory=lambda: [".md", ".markdown", ".txt", ".pdf"]
    )
    capabilities: list[str]
    limitations: list[str]


class EvidenceClaim(BaseModel):
    id: str
    claim: str
    status: ClaimStatus
    evidence_ids: list[str] = Field(default_factory=list)
    note: str = ""


class AnswerSection(BaseModel):
    type: Literal["prose", "note", "warning"] = "prose"
    title: str
    markdown: str


class GraphArtifactNode(BaseModel):
    id: str
    name: str
    type: str
    file_path: str
    start_line: int | None = None
    end_line: int | None = None
    source_id: str | None = None
    documentation_ids: list[str] = Field(default_factory=list)
    description: str


class GraphArtifactEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    is_inferred: bool
    provenance: str


class WalkthroughStep(BaseModel):
    node_id: str
    title: str
    explanation: str
    source_ids: list[str]
    next_node_ids: list[str] = Field(default_factory=list)


class GraphArtifactSpec(BaseModel):
    nodes: list[GraphArtifactNode]
    edges: list[GraphArtifactEdge]
    mermaid: str
    steps: list[WalkthroughStep] = Field(default_factory=list)
    truncated: bool = False


class BrainArtifact(BaseModel):
    id: str
    type: Literal["architecture_graph", "interactive_walkthrough"]
    title: str
    source: Literal["deterministic_graph"] = "deterministic_graph"
    version: int = 1
    source_snapshot_id: str
    created_at: str = ""
    spec: GraphArtifactSpec


class ArtifactListResponse(BaseModel):
    repo_id: str
    artifacts: list[BrainArtifact]


class BrainAnswer(BaseModel):
    answer_id: str
    repo_id: str
    mode: Literal["teach", "walkthrough"]
    summary: str
    sections: list[AnswerSection]
    artifacts: list[BrainArtifact]
    claims: list[EvidenceClaim]
    sources: list[SourceCard]
    suggested_actions: list[str]
    graph_snapshot_id: str
    generated_by: Literal["deterministic_evidence"] = "deterministic_evidence"
