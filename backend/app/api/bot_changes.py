"""HTTP boundary for bot change proposals and documentation checks."""

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.app.schemas.bot_changes import (
    BotChange,
    BotChangeRequest,
    DocumentationCheckResult,
    DocumentationProposalRequest,
    DocumentationStatus,
)
from backend.app.services.async_tasks import repo_write_lock, run_blocking
from backend.app.services.bot_changes.service import BotChangeService

router = APIRouter(prefix="/{bot_id}")


def _service() -> BotChangeService:
    return BotChangeService()


def _raise_http(exc: ValueError) -> HTTPException:
    message = str(exc)
    status = 404 if "not found" in message.lower() else 400
    return HTTPException(status_code=status, detail=message)


@router.get("/changes", response_model=list[BotChange])
async def list_changes(bot_id: str) -> list[dict[str, Any]]:
    try:
        return await run_blocking(_service().list_changes, bot_id)
    except ValueError as exc:
        raise _raise_http(exc) from exc


@router.post("/changes", response_model=BotChange)
async def propose_change(bot_id: str, payload: BotChangeRequest) -> dict[str, Any]:
    try:
        async with repo_write_lock(bot_id):
            return await run_blocking(
                _service().propose, bot_id, payload.request, payload.api_key.get_secret_value()
            )
    except ValueError as exc:
        raise _raise_http(exc) from exc


@router.get("/changes/{change_id}", response_model=BotChange)
async def get_change(bot_id: str, change_id: str) -> dict[str, Any]:
    try:
        return await run_blocking(_service().get_change, bot_id, change_id)
    except ValueError as exc:
        raise _raise_http(exc) from exc


@router.post("/changes/{change_id}/apply", response_model=BotChange)
async def apply_change(bot_id: str, change_id: str) -> dict[str, Any]:
    try:
        async with repo_write_lock(bot_id):
            return await run_blocking(_service().apply, bot_id, change_id)
    except ValueError as exc:
        raise _raise_http(exc) from exc


@router.post("/changes/{change_id}/publish", response_model=BotChange)
async def publish_change(bot_id: str, change_id: str) -> dict[str, Any]:
    try:
        async with repo_write_lock(bot_id):
            return await run_blocking(_service().publish, bot_id, change_id)
    except ValueError as exc:
        raise _raise_http(exc) from exc


@router.get("/documentation/status", response_model=DocumentationStatus)
async def documentation_status(bot_id: str) -> dict[str, Any]:
    try:
        return await run_blocking(_service().documentation_status, bot_id)
    except ValueError as exc:
        raise _raise_http(exc) from exc


@router.post("/documentation/check", response_model=DocumentationCheckResult)
async def check_documentation(bot_id: str) -> dict[str, Any]:
    try:
        async with repo_write_lock(bot_id):
            return await run_blocking(_service().check_documentation, bot_id)
    except ValueError as exc:
        raise _raise_http(exc) from exc


@router.post("/documentation/propose", response_model=BotChange)
async def propose_documentation(bot_id: str, payload: DocumentationProposalRequest) -> dict[str, Any]:
    try:
        async with repo_write_lock(bot_id):
            return await run_blocking(
                _service().propose_documentation, bot_id, payload.api_key.get_secret_value(), payload.paths
            )
    except ValueError as exc:
        raise _raise_http(exc) from exc
