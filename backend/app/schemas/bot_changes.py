"""Request and response models for reviewed bot repository changes."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class BotChangeRequest(BaseModel):
    request: str = Field(min_length=1, max_length=8_000)
    api_key: SecretStr | None = Field(default=None, min_length=1, max_length=512)

    @field_validator("api_key")
    @classmethod
    def nonempty_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        if not value.get_secret_value().strip():
            raise ValueError("An API key is required.")
        return value


class ProposedFileChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=1_024)
    action: Literal["create", "update", "delete"]
    content: str | None = Field(default=None, max_length=200_000)


class BotChangeProposal(BaseModel):
    summary: str = Field(min_length=1, max_length=2_000)
    files: list[ProposedFileChange] = Field(min_length=1, max_length=20)


class BotChangeFile(BaseModel):
    path: str
    action: Literal["create", "update", "delete"]
    content: str | None = None
    diff: str = ""


class BotChange(BaseModel):
    id: str
    bot_id: str
    status: Literal["proposed", "applied", "published", "failed"]
    request: str
    branch: str
    base_commit: str
    summary: str
    files: list[BotChangeFile]
    documentation_sources: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str
    error: str | None = None
    pull_request_url: str | None = None


class DocumentationJob(BaseModel):
    path: str
    status: Literal["pending", "proposed", "completed"]
    detected_at: str
    change_id: str | None = None


class DocumentationStatus(BaseModel):
    bot_id: str
    recorded_commit: str | None = None
    current_commit: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    pending_jobs: list[DocumentationJob] = Field(default_factory=list)
    last_checked_at: str | None = None
    proposed_commit: str | None = None


class DocumentationCheckResult(DocumentationStatus):
    queued_count: int = 0


class DocumentationProposalRequest(BaseModel):
    api_key: SecretStr | None = Field(default=None, min_length=1, max_length=512)
    paths: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("api_key")
    @classmethod
    def nonempty_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        if not value.get_secret_value().strip():
            raise ValueError("An API key is required.")
        return value
