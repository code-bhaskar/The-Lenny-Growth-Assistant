from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session as OrmSession

from app.agent.providers import ProviderRegistry
from app.api.deps import get_ingestion_service, get_retrieval_service, get_session_service
from app.api.schemas import (
    ArtifactCreateRequest,
    ArtifactView,
    HealthResponse,
    IngestionResponse,
    MessageCreateRequest,
    MessageView,
    ProviderStatus,
    ProvidersResponse,
    SessionCreateRequest,
    SessionDetailView,
    SessionView,
)
from app.db.models import Artifact, Message, Session
from app.db.session import get_db
from app.services.conversations import SessionService
from app.services.knowledge import RetrievalService, TranscriptIngestionService

router = APIRouter()


def to_artifact_view(artifact: Artifact) -> ArtifactView:
    return ArtifactView(
        id=artifact.id,
        session_id=artifact.session_id,
        message_id=artifact.message_id,
        title=artifact.title,
        type=artifact.type,
        content=artifact.content,
        sanitized_content=artifact.sanitized_content,
        render_mode=artifact.render_mode,
        created_at=artifact.created_at,
    )


def to_message_view(message: Message) -> MessageView:
    return MessageView(
        id=message.id,
        session_id=message.session_id,
        role=message.role,
        content=message.content,
        metadata=message.metadata_json or {},
        citations=message.citations or [],
        artifacts=[to_artifact_view(artifact) for artifact in message.artifacts],
        created_at=message.created_at,
    )


def to_session_view(session: Session) -> SessionView:
    return SessionView(
        id=session.id,
        title=session.title,
        user_metadata=session.user_metadata or {},
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def to_session_detail_view(session: Session) -> SessionDetailView:
    return SessionDetailView(
        **to_session_view(session).model_dump(),
        messages=[to_message_view(message) for message in session.messages],
    )


@router.get("/health", response_model=HealthResponse)
def health(db: OrmSession = Depends(get_db)) -> HealthResponse:
    database = "ready"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database = "unavailable"

    retrieval = RetrievalService()
    knowledge = retrieval.health(db) if database == "ready" else "missing"

    providers = ProviderRegistry().describe()
    selected = next((item for item in providers if item["selected"]), providers[0])
    agent_layer = "ready" if any(item["available"] for item in providers) else "degraded"
    status = "ok"
    if database != "ready" or knowledge != "ready" or agent_layer != "ready":
        status = "degraded"

    return HealthResponse(
        status=status,
        database=database,
        knowledge_base=knowledge,
        agent_layer=agent_layer,
        selected_provider=selected["key"],
        details={"provider_model": selected.get("model"), "checked_at": datetime.now(timezone.utc).isoformat()},
    )


@router.get("/api/providers", response_model=ProvidersResponse)
def providers() -> ProvidersResponse:
    return ProvidersResponse(providers=[ProviderStatus(**item) for item in ProviderRegistry().describe()])


@router.get("/api/sessions", response_model=list[SessionView])
def list_sessions(
    db: OrmSession = Depends(get_db), service: SessionService = Depends(get_session_service)
) -> list[SessionView]:
    return [to_session_view(item) for item in service.list_sessions(db)]


@router.post("/api/sessions", response_model=SessionView)
def create_session(
    payload: SessionCreateRequest,
    db: OrmSession = Depends(get_db),
    service: SessionService = Depends(get_session_service),
) -> SessionView:
    session = service.create_session(db, title=payload.title, user_metadata=payload.user_metadata)
    return to_session_view(session)


@router.get("/api/sessions/{session_id}", response_model=SessionDetailView)
def get_session(
    session_id: str,
    db: OrmSession = Depends(get_db),
    service: SessionService = Depends(get_session_service),
) -> SessionDetailView:
    return to_session_detail_view(service.get_session(db, session_id))


@router.get("/api/sessions/{session_id}/messages", response_model=list[MessageView])
def get_messages(
    session_id: str,
    db: OrmSession = Depends(get_db),
    service: SessionService = Depends(get_session_service),
) -> list[MessageView]:
    return [to_message_view(item) for item in service.list_messages(db, session_id)]


@router.post("/api/sessions/{session_id}/messages", response_model=MessageView)
def post_message(
    session_id: str,
    payload: MessageCreateRequest,
    db: OrmSession = Depends(get_db),
    service: SessionService = Depends(get_session_service),
) -> MessageView:
    message = service.create_message(
        db,
        session_id=session_id,
        content=payload.content,
        provider_name=payload.provider,
    )
    db.refresh(message)
    return to_message_view(message)


@router.post("/api/ingestion", response_model=IngestionResponse)
def ingest(
    db: OrmSession = Depends(get_db),
    service: TranscriptIngestionService = Depends(get_ingestion_service),
) -> IngestionResponse:
    result = service.ingest(db)
    return IngestionResponse(status="ok", **result)


@router.post("/api/artifacts", response_model=ArtifactView)
def create_artifact(
    payload: ArtifactCreateRequest,
    db: OrmSession = Depends(get_db),
    service: SessionService = Depends(get_session_service),
) -> ArtifactView:
    artifact = service.create_artifact(
        db,
        session_id=payload.session_id,
        instruction=payload.instruction,
        artifact_type=payload.type,
        provider_name=payload.provider,
        message_id=payload.message_id,
    )
    return to_artifact_view(artifact)


@router.get("/api/artifacts/{artifact_id}", response_model=ArtifactView)
def get_artifact(
    artifact_id: str,
    db: OrmSession = Depends(get_db),
    service: SessionService = Depends(get_session_service),
) -> ArtifactView:
    return to_artifact_view(service.get_artifact(db, artifact_id))
