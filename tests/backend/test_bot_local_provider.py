from __future__ import annotations

import json

import httpx
import pytest

from backend.app.services.bots.provider import BotProviderError, generate_text


@pytest.mark.asyncio
async def test_ollama_provider_posts_bounded_prompt_without_api_key(monkeypatch) -> None:
    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"message": {"content": " local answer "}})

    monkeypatch.setenv("CODEWIKI_BOT_LOCAL_ENDPOINT", "http://local-inference:11434/")
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "backend.app.services.bots.provider.httpx.AsyncClient",
        lambda **kwargs: real_async_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    history = [{"role": "user", "content": "old" * 5_000}]
    evidence = {"role": "user", "content": "evidence"}
    question = {"role": "user", "content": "question"}

    answer = await generate_text(
        "ollama/qwen2.5-coder:0.5b",
        "follow these rules",
        [*history, evidence, question],
        api_key=None,
    )

    assert answer == "local answer"
    request = captured[0]
    assert request.url == "http://local-inference:11434/api/chat"
    payload = json.loads(request.content)
    assert payload["model"] == "qwen2.5-coder:0.5b"
    assert payload["stream"] is False
    assert payload["keep_alive"] == 0
    assert payload["options"] == {
        "num_ctx": 4096, "num_predict": 512, "num_thread": 2, "temperature": 0.0,
    }
    assert payload["messages"][0] == {"role": "system", "content": "follow these rules"}
    user_messages = payload["messages"][1:]
    assert sum(len(message["content"]) for message in user_messages) <= 12_000
    assert user_messages[-2:] == [evidence, question]


@pytest.mark.asyncio
async def test_ollama_provider_uses_schema_for_structured_output(monkeypatch) -> None:
    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"message": {"content": '{"ok":true}'}})

    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "backend.app.services.bots.provider.httpx.AsyncClient",
        lambda **kwargs: real_async_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    output_schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }

    answer = await generate_text(
        "ollama/qwen2.5-coder:7b",
        "Return JSON",
        [{"role": "user", "content": '{"task":"test"}'}],
        output_schema=output_schema,
    )

    payload = json.loads(captured[0].content)
    assert answer == '{"ok":true}'
    assert payload["format"] == output_schema
    assert payload["options"] == {
        "num_ctx": 4096, "num_predict": 1024, "num_thread": 2, "temperature": 0.0,
    }


@pytest.mark.asyncio
async def test_ollama_errors_are_safe(monkeypatch) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "private server details"})

    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "backend.app.services.bots.provider.httpx.AsyncClient",
        lambda **kwargs: real_async_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    with pytest.raises(BotProviderError) as caught:
        await generate_text("ollama/missing", "rules", [{"role": "user", "content": "hi"}])
    assert caught.value.status_code == 400
    assert "private server details" not in str(caught.value)
