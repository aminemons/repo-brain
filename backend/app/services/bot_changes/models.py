"""Durable proposals and local-HEAD documentation jobs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, JSONText, RecordMixin


class BotChangeRecord(Base, RecordMixin):
    __tablename__ = "assistant_bot_change"
    __table_args__ = (Index("idx_bot_change_bot_created", "bot_id", "created_at"),)
    __record_fields__ = (
        "id", "bot_id", "request", "branch", "base_commit", "summary", "files",
        "status", "worktree_path", "commit_hash", "error", "pull_request_url",
        "documentation_commit", "documentation_sources", "base_branch", "created_at", "updated_at",
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    bot_id: Mapped[str] = mapped_column(Text, ForeignKey("assistant_bot.id", ondelete="CASCADE"), nullable=False)
    request: Mapped[str] = mapped_column(Text, nullable=False)
    branch: Mapped[str] = mapped_column(Text, nullable=False)
    base_commit: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    files: Mapped[list[dict[str, Any]]] = mapped_column(JSONText(list), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="proposed")
    worktree_path: Mapped[str | None] = mapped_column(Text)
    commit_hash: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    pull_request_url: Mapped[str | None] = mapped_column(Text)
    documentation_commit: Mapped[str | None] = mapped_column(Text)
    documentation_sources: Mapped[list[str]] = mapped_column(JSONText(list), nullable=False, default=list)
    base_branch: Mapped[str] = mapped_column(Text, nullable=False, default="main")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class BotDocumentationJobRecord(Base, RecordMixin):
    __tablename__ = "assistant_bot_documentation_job"
    __table_args__ = (Index("idx_bot_doc_job_bot_status", "bot_id", "status"),)
    __record_fields__ = ("id", "bot_id", "path", "commit_hash", "status", "change_id", "detected_at")

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    bot_id: Mapped[str] = mapped_column(Text, ForeignKey("assistant_bot.id", ondelete="CASCADE"), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    commit_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    change_id: Mapped[str | None] = mapped_column(Text)
    detected_at: Mapped[str] = mapped_column(Text, nullable=False)


class BotDocumentationStateRecord(Base, RecordMixin):
    __tablename__ = "assistant_bot_documentation_state"
    __record_fields__ = ("bot_id", "recorded_commit", "last_checked_at")

    bot_id: Mapped[str] = mapped_column(Text, ForeignKey("assistant_bot.id", ondelete="CASCADE"), primary_key=True)
    recorded_commit: Mapped[str | None] = mapped_column(Text)
    last_checked_at: Mapped[str | None] = mapped_column(Text)

