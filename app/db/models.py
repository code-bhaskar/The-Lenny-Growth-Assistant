from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), default="New chat")
    user_name: Mapped[str] = mapped_column(String(120), default="Evaluator")
    user_role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list[Message]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Message.created_at"
    )
    artifacts: Mapped[list[Artifact]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Artifact.created_at"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    route: Mapped[str] = mapped_column(String(50), default="qa")
    provider: Mapped[str] = mapped_column(String(50), default="ollama")
    citations: Mapped[list[dict]] = mapped_column(JSON, default=list)
    artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[ChatSession] = relationship(back_populates="messages")
    artifact: Mapped[Artifact | None] = relationship(
        back_populates="message", foreign_keys=[artifact_id], uselist=False
    )

    __table_args__ = (Index("ix_messages_session_created_at", "session_id", "created_at"),)


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255), default="Untitled artifact")
    artifact_type: Mapped[str] = mapped_column(String(20), default="markdown")
    raw_content: Mapped[str] = mapped_column(Text)
    sanitized_content: Mapped[str] = mapped_column(Text)
    render_mode: Mapped[str] = mapped_column(String(20), default="markdown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[ChatSession] = relationship(back_populates="artifacts")
    message: Mapped[Message | None] = relationship(
        back_populates="artifact",
        uselist=False,
        primaryjoin="Artifact.id == Message.artifact_id",
        foreign_keys="Message.artifact_id",
    )
