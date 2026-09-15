from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_conversation_service, get_ingestion_service, get_retrieval_service
from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    IngestResponse,
    MessageResponse,
    ProviderStatus,
    ProvidersResponse,
    SessionCreateRequest,
    SessionResponse,
)
from app.core.config import BASE_DIR, get_settings
from app.db.models import Artifact, ChatSession, Message
from app.db.session import get_db
from app.services.conversations import ConversationService
from app.services.knowledge import RetrievalService, TranscriptIngestionService

router = APIRouter()


def _artifact_to_schema(artifact: Artifact):
    from app.api.schemas import ArtifactResponse

    return ArtifactResponse(
        id=artifact.id,
        title=artifact.title,
        artifact_type=artifact.artifact_type,
        raw_content=artifact.raw_content,
        sanitized_content=artifact.sanitized_content,
        render_mode=artifact.render_mode,
        created_at=artifact.created_at,
    )


def _message_to_schema(message: Message) -> MessageResponse:
    artifact = _artifact_to_schema(message.artifact) if message.artifact else None
    return MessageResponse(
        id=message.id,
        role=message.role,
        content=message.content,
        route=message.route,
        provider=message.provider,
        citations=message.citations or [],
        artifact=artifact,
        created_at=message.created_at,
    )


def _session_to_schema(session: ChatSession, include_messages: bool = True) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        title=session.title,
        user_name=session.user_name,
        user_role=session.user_role,
        metadata=session.metadata_json or {},
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[_message_to_schema(message) for message in session.messages] if include_messages else [],
    )


@router.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "app" / "static" / "index.html")


@router.get("/health", response_model=HealthResponse)
def health(
    db: Session = Depends(get_db),
    retrieval: RetrievalService = Depends(get_retrieval_service),
) -> HealthResponse:
    database_status = "ready"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database_status = "unavailable"

    settings = get_settings()
    providers = {item["key"]: item for item in ConversationService().providers.describe()}
    selected_provider = providers.get(settings.llm_provider, {})
    selected_status = "ready" if selected_provider.get("available") else "degraded"
    kb_status = retrieval.health()

    app_status = "ok"
    if database_status != "ready" or kb_status != "ready" or selected_status != "ready":
        app_status = "degraded"

    return HealthResponse(
        status=app_status,
        database=database_status,
        knowledge_base=kb_status,
        llm_provider=selected_status,
        details={"selected_provider": settings.llm_provider, "provider_model": selected_provider.get("model")},
    )


@router.get("/health/ready", response_model=HealthResponse)
def ready(
    db: Session = Depends(get_db),
    retrieval: RetrievalService = Depends(get_retrieval_service),
) -> HealthResponse:
    return health(db, retrieval)


@router.get("/api/providers", response_model=ProvidersResponse)
def providers(service: ConversationService = Depends(get_conversation_service)) -> ProvidersResponse:
    return ProvidersResponse(providers=[ProviderStatus(**item) for item in service.providers.describe()])


@router.get("/api/sessions", response_model=list[SessionResponse])
def list_sessions(
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> list[SessionResponse]:
    return [_session_to_schema(session, include_messages=False) for session in service.list_sessions(db)]


@router.post("/api/sessions", response_model=SessionResponse)
def create_session(
    payload: SessionCreateRequest,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> SessionResponse:
    session = service.create_session(
        db,
        title=payload.title,
        user_name=payload.user.user_name,
        user_role=payload.user.user_role,
        tags=payload.user.tags,
    )
    return _session_to_schema(session)


@router.get("/api/sessions/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> SessionResponse:
    session = service.get_session(db, session_id)
    return _session_to_schema(session)


@router.post("/api/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> ChatResponse:
    result = service.process_chat(
        db,
        session_id=payload.session_id,
        content=payload.content,
        provider_name=payload.provider,
    )
    message = result["message"]
    db.refresh(message)
    return ChatResponse(
        session_id=payload.session_id,
        provider=result["provider"],
        message=_message_to_schema(message),
        retrieval_summary=result["retrieval_summary"],
    )


@router.post("/api/admin/reingest", response_model=IngestResponse)
def reingest(
    ingestion: TranscriptIngestionService = Depends(get_ingestion_service),
    retrieval: RetrievalService = Depends(get_retrieval_service),
) -> IngestResponse:
    stats = retrieval.refresh()
    return IngestResponse(status="ok", **stats)


@router.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    icon = BASE_DIR / "app" / "static" / "favicon.ico"
    if icon.exists():
        return FileResponse(icon)
    return FileResponse(BASE_DIR / "app" / "static" / "logo.svg")
