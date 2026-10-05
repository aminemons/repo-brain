"""Thin HTTP routes for deterministic Project Brain evidence and teaching."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.schemas.project_brain import (
    ArtifactListResponse,
    BrainAnswer,
    BrainStatus,
    DocumentSearchResponse,
    DocumentSection,
    DocumentVersion,
    IngestDocumentRequest,
    IngestDocumentResponse,
    SourceExcerpt,
)
from backend.app.services.async_tasks import repo_write_lock, run_blocking
from backend.app.services.project_brain.service import ProjectBrainService

router = APIRouter(prefix="/{repo_id}/brain")


def project_brain_service() -> ProjectBrainService:
    return ProjectBrainService()


BrainService = Annotated[ProjectBrainService, Depends(project_brain_service)]
SearchQuery = Annotated[str, Query(max_length=2_000)]
ResultLimit = Annotated[int, Query(ge=1, le=60)]


def _http_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status = 404 if "not found" in message.lower() else 400
    return HTTPException(status_code=status, detail=message)


@router.get("")
async def brain_status(repo_id: str, service: BrainService) -> BrainStatus:
    try:
        return await run_blocking(service.status, repo_id)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.post("/documents")
async def ingest_document(
    repo_id: str,
    payload: IngestDocumentRequest,
    service: BrainService,
) -> IngestDocumentResponse:
    try:
        async with repo_write_lock(repo_id):
            return await run_blocking(service.ingest, repo_id, payload)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.get("/documents")
async def search_documents(
    repo_id: str,
    service: BrainService,
    query: SearchQuery = "",
    limit: ResultLimit = 20,
) -> DocumentSearchResponse:
    try:
        return await run_blocking(service.search_documents, repo_id, query, limit)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.get("/documents/{document_id}/versions")
async def document_versions(
    repo_id: str,
    document_id: str,
    service: BrainService,
) -> list[DocumentVersion]:
    try:
        return await run_blocking(service.document_versions, repo_id, document_id)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.get("/documents/{section_id}")
async def document_section(
    repo_id: str,
    section_id: str,
    service: BrainService,
) -> DocumentSection:
    try:
        return await run_blocking(service.document_section, repo_id, section_id)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.get("/source")
async def source_excerpt(
    repo_id: str,
    service: BrainService,
    path: Annotated[str, Query(min_length=1, max_length=1_024)],
    start_line: Annotated[int, Query(ge=1, le=10_000_000)] = 1,
    end_line: Annotated[int | None, Query(ge=1, le=10_000_000)] = None,
    kind: Literal["code", "documentation"] = "code",
) -> SourceExcerpt:
    try:
        return await run_blocking(service.source_excerpt, repo_id, path, start_line, end_line, kind)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.get("/walkthrough")
async def walkthrough(
    repo_id: str,
    service: BrainService,
    query: SearchQuery = "",
    limit: ResultLimit = 12,
) -> BrainAnswer:
    try:
        async with repo_write_lock(repo_id):
            return await run_blocking(service.walkthrough, repo_id, query, limit)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.get("/architecture")
async def architecture(
    repo_id: str,
    service: BrainService,
    query: SearchQuery = "",
    limit: ResultLimit = 30,
) -> ArtifactListResponse:
    try:
        async with repo_write_lock(repo_id):
            return await run_blocking(service.architecture, repo_id, query, limit)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.get("/artifacts")
async def artifacts(
    repo_id: str,
    service: BrainService,
    query: SearchQuery = "",
    limit: ResultLimit = 30,
) -> ArtifactListResponse:
    try:
        return await run_blocking(service.artifacts, repo_id, query, limit)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.get("/artifacts/{artifact_id}/versions")
async def artifact_versions(
    repo_id: str,
    artifact_id: str,
    service: BrainService,
) -> ArtifactListResponse:
    try:
        return await run_blocking(service.artifact_versions, repo_id, artifact_id)
    except ValueError as exc:
        raise _http_error(exc) from exc
