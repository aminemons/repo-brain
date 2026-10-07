"""Owner-only repository selection; GitHub credentials remain on the server."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response

from backend.app.schemas.github import GitHubRepositoriesResponse
from backend.app.services.async_tasks import run_blocking
from backend.app.services.github.discovery import GitHubDiscoveryError, GitHubDiscoveryService

router = APIRouter()


@router.get("/repositories", response_model=GitHubRepositoriesResponse)
async def list_github_repositories(
    request: Request,
    response: Response,
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 30,
) -> GitHubRepositoriesResponse:
    response.headers["Cache-Control"] = "no-store"
    if getattr(request.state, "project_role", "denied") not in {"owner", "local"}:
        raise HTTPException(status_code=403, detail="Only the owner can browse the connected GitHub account.")
    try:
        return await run_blocking(GitHubDiscoveryService().list_repositories, page, per_page)
    except GitHubDiscoveryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
