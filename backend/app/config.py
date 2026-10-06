from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProfileSettings(BaseModel):
    model: str | None = None
    provider_type: str | None = None
    endpoint: str | None = None
    api_key: str | None = None
    max_tokens: int | None = Field(default=None, ge=0)

    @field_validator("max_tokens", mode="before")
    @classmethod
    def _blank_max_tokens_as_none(cls, value: Any) -> Any:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


class LLMSettings(BaseModel):
    mode: str = Field(default="sdk", pattern="^(sdk|proxy)$")
    default: LLMProfileSettings = Field(
        default_factory=lambda: LLMProfileSettings(model="provider/strong-coding-model")
    )
    profiles: dict[str, LLMProfileSettings] = Field(default_factory=dict)
    timeout_seconds: int = 120
    max_retries: int = 3
    cache_enabled: bool = True


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CODEWIKI_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    app_name: str = "Project Brain"
    database_url: str = "sqlite+aiosqlite:///./data/codewiki.sqlite3"
    storage_dir: Path = Path("./storage")
    project_root: Path | None = None
    documentation_root: Path | None = None
    auth_token: str | None = None
    viewer_token: str | None = None
    local_only: bool = True
    privacy_mode: str = Field(
        default="local_only", pattern="^(local_only|sanitized|relevant_excerpts|maximum_intelligence)$"
    )
    external_excerpt_max_chars: int = Field(default=16000, ge=1000, le=100000)
    local_llm_hosts: str = "localhost,127.0.0.1,::1,ollama,vllm,litellm"
    api_requests_per_minute: int = Field(default=120, ge=1, le=10000)
    bot_documentation_watch_enabled: bool = True
    bot_documentation_watch_seconds: int = Field(default=60, ge=15, le=86400)
    bot_github_sync_enabled: bool = True
    najm_enabled: bool = False
    najm_endpoint: str = "http://najm:8080"
    najm_timeout_seconds: float = Field(default=20.0, ge=1, le=120)

    llm: LLMSettings = Field(default_factory=LLMSettings)

    graphrag_context_token_budget: int = 8000
    graphrag_max_source_chunks: int = 20

    wiki_base_language: str = "en"
    wiki_translation_languages: str | None = None

    @field_validator("project_root", "documentation_root", mode="before")
    @classmethod
    def _blank_optional_path(cls, value: Any) -> Any:
        return None if isinstance(value, str) and not value.strip() else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
