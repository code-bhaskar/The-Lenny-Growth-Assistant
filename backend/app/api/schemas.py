from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Citation(BaseModel):
    source_id: str
    transcript_title: str
    source_path: str
    source_url: str | None = None
    guest: str | None = None
    publish_date: str | None = None
    snippet: str
    chunk_index: int
    score: float | None = None


class ArtifactView(BaseModel):
    id: str
    session_id: str
    message_id: str | None = None
    title: str
    type: Literal["markdown", "html"]
    content: str
    sanitized_content: str
    render_mode: Literal["markdown", "html"]
    created_at: datetime


class MessageMetadata(BaseModel):
    route: str = "qa"
    provider: str = "ollama"
    model: str | None = None
    retrieval_summary: dict[str, Any] = Field(default_factory=dict)
    fallback_note: str | None = None
    artifact_ids: list[str] = Field(default_factory=list)
    artifact_word_count: int | None = None
    runtime_backend: str | None = None


class MessageCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=6000)
    provider: Literal["ollama", "anthropic"] | None = None


class MessageView(BaseModel):
    id: str
    session_id: str
    role: Literal["user", "assistant"]
    content: str
    metadata: MessageMetadata
    citations: list[Citation] = Field(default_factory=list)
    artifacts: list[ArtifactView] = Field(default_factory=list)
    created_at: datetime


class SessionCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    user_metadata: dict[str, Any] = Field(default_factory=dict)


class SessionView(BaseModel):
    id: str
    title: str
    user_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime | None = None


class SessionDetailView(SessionView):
    messages: list[MessageView] = Field(default_factory=list)


class ArtifactCreateRequest(BaseModel):
    session_id: str
    instruction: str = Field(min_length=1, max_length=6000)
    type: Literal["markdown", "html"]
    provider: Literal["ollama", "anthropic"] | None = None
    message_id: str | None = None


class IngestionResponse(BaseModel):
    status: Literal["ok"]
    sources_indexed: int
    chunks_indexed: int
    source_dir: str
    timestamp: datetime


class ProviderStatus(BaseModel):
    key: Literal["ollama", "anthropic"]
    label: str
    selected: bool
    available: bool
    model: str | None = None
    reason: str | None = None


class ProvidersResponse(BaseModel):
    providers: list[ProviderStatus]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "error"]
    database: str
    knowledge_base: str
    agent_layer: str
    selected_provider: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: str
    detail: str
    request_id: str | None = None
