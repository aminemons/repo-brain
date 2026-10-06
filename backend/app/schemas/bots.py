"""HTTP schemas for repository bots and private conversation histories."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class BotCreateRequest(BaseModel):
    repo_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=120)
    instructions: str = Field(default="", max_length=8_000)
    model: str = Field(default="gpt-5.5", min_length=1, max_length=160)


class BotUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    instructions: str | None = Field(default=None, max_length=8_000)
    model: str | None = Field(default=None, min_length=1, max_length=160)


class Bot(BaseModel):
    id: str
    repo_id: str
    name: str
    instructions: str
    model: str
    created_at: str
    updated_at: str


class BotListResponse(BaseModel):
    bots: list[Bot]


class ConversationCreateRequest(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=160)


class Conversation(BaseModel):
    id: str
    bot_id: str
    title: str
    created_at: str
    updated_at: str


class BotSource(BaseModel):
    id: str
    type: Literal["code", "documentation"]
    path: str
    start_line: int
    end_line: int
    snippet: str


class BotMessage(BaseModel):
    id: str
    conversation_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: str
    sources: list[BotSource] = Field(default_factory=list)
    illustration: "BotIllustration | None" = None


class BotIllustration(BaseModel):
    status: Literal["ready", "unavailable"]
    url: str | None = None
    caption: str
    alt_text: str
    detail: str | None = None


class ConversationDetail(BaseModel):
    conversation: Conversation
    messages: list[BotMessage]


class BotMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12_000)
    mode: Literal["explain", "teach", "illustrate"] = "explain"
    api_key: SecretStr = Field(min_length=1, max_length=512)


class BotRefreshResponse(BaseModel):
    repo_id: str
    status: str
    chunk_count: int
    documents_indexed: int = 0
    commit_hash: str | None = None
    refreshed_at: str
    warnings: list[str] = Field(default_factory=list)
