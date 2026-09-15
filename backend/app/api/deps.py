from __future__ import annotations

from app.services.conversations import SessionService
from app.services.knowledge import RetrievalService, TranscriptIngestionService


def get_session_service() -> SessionService:
    return SessionService()


def get_ingestion_service() -> TranscriptIngestionService:
    return TranscriptIngestionService()


def get_retrieval_service() -> RetrievalService:
    return RetrievalService()
