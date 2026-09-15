from __future__ import annotations

from app.services.conversations import ConversationService
from app.services.knowledge import RetrievalService, TranscriptIngestionService


def get_conversation_service() -> ConversationService:
    return ConversationService()


def get_retrieval_service() -> RetrievalService:
    return RetrievalService()


def get_ingestion_service() -> TranscriptIngestionService:
    return TranscriptIngestionService()
