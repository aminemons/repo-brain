"""Private, local inference provider for repository bots."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping, Sequence

import httpx

_INFERENCE_SLOT = asyncio.Semaphore(1)


class BotProviderError(RuntimeError):
    """A safe provider error that does not retain request or credential details."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(message)


def _bounded_messages(
    messages: Sequence[Mapping[str, object]], limit: int = 12_000
) -> list[dict[str, str]]:
    """Keep the latest context, reserving it before spending the budget on conversation history."""
    if limit <= 0:
        return []
    normalized = [
        {"role": str(item.get("role", "user")), "content": str(item.get("content", ""))}
        for item in messages
    ]
    if sum(len(item["content"]) for item in normalized) <= limit:
        return normalized

    # The current evidence and question are last; keep them intact when possible.
    protected_count = min(2, len(normalized))
    protected = normalized[-protected_count:]
    protected_size = sum(len(item["content"]) for item in protected)
    if protected_size > limit:
        # In unusual oversized requests preserve the current question and the tail of evidence.
        remaining = limit
        result = []
        for item in reversed(protected):
            content = item["content"][-remaining:]
            result.append({"role": item["role"], "content": content})
            remaining -= len(content)
            if remaining <= 0:
                break
        return list(reversed(result))

    budget = limit - protected_size
    history: list[dict[str, str]] = []
    for item in reversed(normalized[:-protected_count]):
        if budget <= 0:
            break
        content = item["content"][-budget:]
        history.append({"role": item["role"], "content": content})
        budget -= len(content)
    return list(reversed(history)) + protected


async def generate_text(
    model: str,
    instructions: str,
    input_messages: Sequence[Mapping[str, object]],
    api_key: str | None = None,
) -> str:
    """Generate text with the configured private Ollama endpoint."""
    del api_key  # Local inference never consumes or forwards BYOK credentials.
    endpoint = os.environ.get("CODEWIKI_BOT_LOCAL_ENDPOINT", "http://127.0.0.1:11434").rstrip("/")
    ollama_model = model.removeprefix("ollama/")
    messages = [
        {"role": "system", "content": instructions},
        *_bounded_messages(input_messages, max(0, 12_000 - len(instructions))),
    ]
    body = {
        "model": ollama_model,
        "messages": messages,
        "stream": False,
        "keep_alive": 0,
        "options": {"num_ctx": 4096, "num_predict": 512, "num_thread": 2},
    }
    try:
        async with _INFERENCE_SLOT, httpx.AsyncClient(
            timeout=180.0, trust_env=False, follow_redirects=False
        ) as client:
            response = await client.post(f"{endpoint}/api/chat", json=body)
            response.raise_for_status()
            payload = response.json()
        answer = payload.get("message", {}).get("content", "").strip()
        if not answer:
            raise BotProviderError(502, "The local model returned an empty response.")
        return answer
    except BotProviderError:
        raise
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code == 404:
            raise BotProviderError(400, "The selected local model was not found. Check the model name.") from None
        if code in {400, 422}:
            raise BotProviderError(400, "The local model rejected this request. Check the model and message.") from None
        raise BotProviderError(502, "The local model could not complete this request. Check the local inference service.") from None
    except httpx.TimeoutException:
        raise BotProviderError(504, "The local model timed out. Try again after checking inference service load.") from None
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        raise BotProviderError(502, "The local model could not complete this request. Check the local inference service.") from None
