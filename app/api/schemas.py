from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class UserMetadata(BaseModel):
    user_name: str = Field(default="Evaluator", max_length=120)
    user_role: str | None = Field(default=None, max_length=120)
    tags: list[str] = Field(default_factory=list)


class SessionCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    user: UserMetadata = Field(default_factory=UserMetadata)


class Citation(BaseModel):
    transcript_title: str
    guest: str | None = None
    publish_date: str | None = None
    source_path: str
    youtube_url: str | None = None
    snippet: str
    score: float | None = None


class ArtifactResponse(BaseModel):
    id: str
    title: str
    artifact_type: Literal["markdown", "html"]
    raw_content: str
    sanitized_content: str
    render_mode: Literal["markdown", "html"]
    created_at: datetime


class MessageResponse(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    route: str
    provider: str
    citations: list[Citation] = Field(default_factory=list)
    artifact: ArtifactResponse | None = None
    created_at: datetime


class SessionResponse(BaseModel):
    id: str
    title: str
    user_name: str
    user_role: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime | None = None
    messages: list[MessageResponse] = Field(default_factory=list)


class ChatRequest(BaseModel):
    session_id: str
    content: str = Field(min_length=1, max_length=6000)
    provider: Literal["ollama", "anthropic"] | None = None


class ChatResponse(BaseModel):
    session_id: str
    provider: str
    message: MessageResponse
    retrieval_summary: dict[str, Any] = Field(default_factory=dict)


class ProviderStatus(BaseModel):
    key: Literal["ollama", "anthropic"]
    label: str
    selected: bool
    available: bool
    reason: str | None = None
    model: str | None = None


class ProvidersResponse(BaseModel):
    providers: list[ProviderStatus]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "error"]
    database: str
    knowledge_base: str
    llm_provider: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: str
    detail: str
    trace_id: str | None = None


class IngestResponse(BaseModel):
    status: str
    transcripts_indexed: int
    chunks_indexed: int
    source_dir: str
