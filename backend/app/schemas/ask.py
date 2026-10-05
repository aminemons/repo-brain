from pydantic import BaseModel, Field

from backend.app.schemas.project_brain import SourceCard


class SourceRef(BaseModel):
    citation_id: str | None = None
    file_path: str
    start_line: int
    end_line: int
    source_url: str | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8000)
    mode: str = "graph_rag"
    max_hops: int = Field(default=2, ge=0, le=6)
    include_sources: bool = True
    include_graph: bool = True


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceRef]
    related_nodes: list[dict[str, object]]
    related_edges: list[dict[str, object]]
    related_communities: list[dict[str, object]] = Field(default_factory=list)
    trace_id: str
    documentation_sources: list[SourceCard] = Field(default_factory=list)
