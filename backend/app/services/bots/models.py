"""Database records for bots and their independent conversation histories."""

from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, JSONText, RecordMixin


class BotRecord(Base, RecordMixin):
    __tablename__ = "assistant_bot"
    __table_args__ = (
        UniqueConstraint("repo_id", name="uq_assistant_bot_repo"),
        Index("idx_assistant_bot_repo", "repo_id", "created_at"),
    )
    __record_fields__ = ("id", "repo_id", "name", "instructions", "model", "created_at", "updated_at")

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    repo_id: Mapped[str] = mapped_column(Text, ForeignKey("repo.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    model: Mapped[str] = mapped_column(Text, nullable=False, default="gpt-5.5", server_default="gpt-5.5")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class BotConversationRecord(Base, RecordMixin):
    __tablename__ = "assistant_bot_conversation"
    __table_args__ = (Index("idx_bot_conversation_bot", "bot_id", "updated_at"),)
    __record_fields__ = ("id", "bot_id", "title", "created_at", "updated_at")

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    bot_id: Mapped[str] = mapped_column(Text, ForeignKey("assistant_bot.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="New conversation", server_default="New conversation")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class BotMessageRecord(Base, RecordMixin):
    __tablename__ = "assistant_bot_message"
    __table_args__ = (Index("idx_bot_message_conversation", "conversation_id", "created_at"),)
    __record_fields__ = ("id", "conversation_id", "role", "content", "sources", "created_at")

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        Text, ForeignKey("assistant_bot_conversation.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(
        "sources_json", JSONText(list), nullable=False, default=list, server_default="[]"
    )
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
