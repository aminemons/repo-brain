from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from backend.app.config import Settings
from backend.app.services.llm.model_router import ModelRouter
from backend.app.services.llm.privacy import prepare_embeddings, prepare_messages
from backend.app.services.project_policy import validate_model_destination


@dataclass(frozen=True)
class LLMResult:
    content: str
    model: str
    usage: dict[str, Any]
    provider: str | None = None


@dataclass(frozen=True)
class LLMDelta:
    content: str


class LLMGateway:
    """LiteLLM-first gateway.

    Business services depend on this class instead of importing provider SDKs directly.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.router = ModelRouter(settings)

    async def complete(
        self,
        task_type: str,
        messages: list[dict[str, str]],
        *,
        response_format: str | None = None,
        provider_user_id: str | None = None,
    ) -> LLMResult:
        profile = self.router.profile_for(task_type)
        validate_model_destination(
            self.settings, model=profile.model, endpoint=profile.endpoint,
            provider_type=profile.provider_type,
        )
        from litellm import acompletion
        kwargs: dict[str, Any] = {
            "model": _litellm_model(profile),
            "messages": prepare_messages(
                self.settings, messages, model=profile.model, endpoint=profile.endpoint,
            ),
            "temperature": profile.temperature,
            "timeout": self.settings.llm.timeout_seconds,
            "num_retries": max(0, self.settings.llm.max_retries),
        }
        if profile.max_tokens is not None and profile.max_tokens > 0:
            kwargs["max_tokens"] = profile.max_tokens
        if response_format:
            kwargs["response_format"] = {"type": response_format}
        if profile.endpoint:
            kwargs["api_base"] = profile.endpoint
        if profile.api_key:
            kwargs["api_key"] = profile.api_key
        if provider_user_id and _is_deepseek_profile(profile):
            kwargs["extra_body"] = {"user_id": provider_user_id}

        response = await acompletion(**kwargs)
        choice = response.choices[0]
        content = choice.message.content or ""
        usage_obj = getattr(response, "usage", None)
        model_dump = getattr(usage_obj, "model_dump", None)
        if callable(model_dump):
            usage = model_dump()
        elif isinstance(usage_obj, dict):
            usage = usage_obj
        else:
            usage = {}
        return LLMResult(
            content=content,
            model=profile.model,
            usage=usage,
            provider=profile.provider_type,
        )

    async def stream(self, task_type: str, messages: list[dict[str, str]]) -> AsyncIterator[LLMDelta]:
        profile = self.router.profile_for(task_type)
        validate_model_destination(
            self.settings, model=profile.model, endpoint=profile.endpoint,
            provider_type=profile.provider_type,
        )
        from litellm import acompletion
        kwargs: dict[str, Any] = {
            "model": _litellm_model(profile),
            "messages": prepare_messages(
                self.settings, messages, model=profile.model, endpoint=profile.endpoint,
            ),
            "temperature": profile.temperature,
            "stream": True,
            "timeout": self.settings.llm.timeout_seconds,
            "num_retries": max(0, self.settings.llm.max_retries),
        }
        if profile.endpoint:
            kwargs["api_base"] = profile.endpoint
        if profile.api_key:
            kwargs["api_key"] = profile.api_key
        response = await acompletion(**kwargs)
        async for chunk in response:
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                yield LLMDelta(content=content)

    async def embed(self, texts: list[str], *, task_type: str = "embedding") -> list[list[float]]:
        profile = self.router.profile_for(task_type)
        validate_model_destination(
            self.settings, model=profile.model, endpoint=profile.endpoint,
            provider_type=profile.provider_type,
        )
        from litellm import aembedding
        kwargs: dict[str, Any] = {
            "model": _litellm_model(profile),
            "input": prepare_embeddings(self.settings, texts, endpoint=profile.endpoint),
            "num_retries": max(0, self.settings.llm.max_retries),
        }
        if profile.endpoint:
            kwargs["api_base"] = profile.endpoint
        if profile.api_key:
            kwargs["api_key"] = profile.api_key
        response = await aembedding(**kwargs)
        return [
            item["embedding"] if isinstance(item, dict) else item.embedding
            for item in response.data
        ]


def _litellm_model(profile) -> str:
    if "/" in profile.model:
        return profile.model
    if profile.provider_type:
        return f"{profile.provider_type}/{profile.model}"
    if profile.endpoint:
        return f"openai/{profile.model}"
    return profile.model


def _is_deepseek_profile(profile) -> bool:
    provider = (profile.provider_type or "").lower()
    model = (profile.model or "").lower()
    endpoint = (profile.endpoint or "").lower()
    return provider == "deepseek" or model.startswith("deepseek/") or "deepseek.com" in endpoint
