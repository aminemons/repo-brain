"""HTTP API for repository bots and their isolated conversation histories."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError

from backend.app.schemas.bots import (
    Bot,
    BotCreateRequest,
    BotListResponse,
    BotMessage,
    BotMessageRequest,
    BotRefreshResponse,
    BotUpdateRequest,
    Conversation,
    ConversationCreateRequest,
    ConversationDetail,
)
from backend.app.services.async_tasks import run_blocking
from backend.app.services.bots import BotProviderError, BotService

router = APIRouter()


def get_bot_service() -> BotService:
    return BotService()


BotServiceDep = Annotated[BotService, Depends(get_bot_service)]


def _http_error(exc: ValueError) -> HTTPException:
    text = str(exc)
    code = 404 if "not found" in text.lower() else 400
    return HTTPException(status_code=code, detail=text)


@router.get("", response_model=BotListResponse)
async def list_bots(
    service: BotServiceDep,
    repo_id: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
) -> BotListResponse:
    try:
        return BotListResponse(bots=await run_blocking(service.list_bots, repo_id))
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.post("", response_model=Bot, status_code=status.HTTP_201_CREATED)
async def create_bot(payload: BotCreateRequest, service: BotServiceDep) -> Bot:
    try:
        return await run_blocking(
            service.create_bot, payload.repo_id, payload.name, payload.instructions, payload.model
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="A bot already exists for this repository") from exc
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.get("/{bot_id}", response_model=Bot)
async def get_bot(bot_id: str, service: BotServiceDep) -> Bot:
    try:
        return await run_blocking(service.get_bot, bot_id)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.patch("/{bot_id}", response_model=Bot)
async def update_bot(bot_id: str, payload: BotUpdateRequest, service: BotServiceDep) -> Bot:
    try:
        return await run_blocking(service.update_bot, bot_id, **payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bot(bot_id: str, service: BotServiceDep) -> Response:
    try:
        await run_blocking(service.delete_bot, bot_id)
    except ValueError as exc:
        raise _http_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{bot_id}/conversations", response_model=list[Conversation])
async def list_conversations(bot_id: str, service: BotServiceDep) -> list[Conversation]:
    try:
        return await run_blocking(service.list_conversations, bot_id)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.post(
    "/{bot_id}/conversations", response_model=Conversation, status_code=status.HTTP_201_CREATED
)
async def create_conversation(
    bot_id: str, payload: ConversationCreateRequest, service: BotServiceDep
) -> Conversation:
    try:
        return await run_blocking(service.create_conversation, bot_id, payload.title)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.get("/{bot_id}/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    bot_id: str, conversation_id: str, service: BotServiceDep
) -> ConversationDetail:
    try:
        return await run_blocking(service.get_conversation, bot_id, conversation_id)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.delete("/{bot_id}/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    bot_id: str, conversation_id: str, service: BotServiceDep
) -> Response:
    try:
        await run_blocking(service.delete_conversation, bot_id, conversation_id)
    except ValueError as exc:
        raise _http_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{bot_id}/conversations/{conversation_id}/messages", response_model=BotMessage
)
async def send_message(
    bot_id: str,
    conversation_id: str,
    payload: BotMessageRequest,
    service: BotServiceDep,
) -> BotMessage:
    try:
        return await service.send_message(
            bot_id,
            conversation_id,
            payload.message,
            payload.mode,
            payload.api_key.get_secret_value() if payload.api_key is not None else None,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc
    except BotProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from None
    except RuntimeError:
        raise HTTPException(status_code=502, detail="The assistant could not complete this request. Try again.") from None


@router.get("/{bot_id}/messages/{message_id}/illustration")
async def get_illustration(bot_id: str, message_id: str, service: BotServiceDep) -> Response:
    try:
        image = await run_blocking(service.illustration_bytes, bot_id, message_id)
    except ValueError as exc:
        raise _http_error(exc) from exc
    return Response(
        content=image,
        media_type="image/png",
        headers={"Cache-Control": "no-store", "Content-Disposition": "inline"},
    )


@router.post("/{bot_id}/refresh", response_model=BotRefreshResponse)
async def refresh_bot(bot_id: str, service: BotServiceDep) -> BotRefreshResponse:
    try:
        return await service.refresh(bot_id)
    except ValueError as exc:
        raise _http_error(exc) from exc
