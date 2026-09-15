from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import NotFoundError
from app.core.config import get_settings
from app.db.models import Artifact, ChatSession, Message
from app.services.agent.prompts import (
    artifact_system_prompt,
    artifact_user_prompt,
    build_context_block,
    qa_system_prompt,
    qa_user_prompt,
    ship30_system_prompt,
    ship30_user_prompt,
)
from app.services.agent.providers import ProviderRegistry
from app.services.agent.router import RouteClassifier
from app.services.artifacts import ArtifactPayload, ArtifactService
from app.services.knowledge import RetrievalService


class ConversationService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.providers = ProviderRegistry()
        self.router = RouteClassifier()
        self.retrieval = RetrievalService()
        self.artifacts = ArtifactService()

    def create_session(
        self,
        db: Session,
        *,
        title: str | None,
        user_name: str,
        user_role: str | None,
        tags: list[str] | None = None,
    ) -> ChatSession:
        session = ChatSession(
            title=title or "New chat",
            user_name=user_name or self.settings.default_user_name,
            user_role=user_role,
            metadata_json={"tags": tags or []},
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def list_sessions(self, db: Session) -> list[ChatSession]:
        return list(db.scalars(select(ChatSession).order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())))

    def get_session(self, db: Session, session_id: str) -> ChatSession:
        session = db.get(ChatSession, session_id)
        if not session:
            raise NotFoundError(f"Session '{session_id}' not found")
        return session

    def process_chat(
        self, db: Session, *, session_id: str, content: str, provider_name: str | None = None
    ) -> dict[str, Any]:
        session = self.get_session(db, session_id)

        user_message = Message(
            session_id=session.id,
            role="user",
            content=content,
            route="user",
            provider=provider_name or self.settings.llm_provider,
            citations=[],
        )
        db.add(user_message)
        db.flush()

        history = self._history_block(session.messages + [user_message])
        retrieval_query = self._build_retrieval_query(session.messages + [user_message])
        results = self.retrieval.search(retrieval_query)
        retrieval_summary = self.retrieval.summarize_search(results)
        citations = [self._citation_from_result(item) for item in results]

        decision = self.router.classify(content)
        provider, fallback_note = self.providers.resolve(provider_name)

        if retrieval_summary["status"] != "grounded":
            if decision.route == "qa":
                answer_text = (
                    "I couldn't find enough grounded evidence in the indexed Lenny transcripts to answer that confidently. "
                    "Try naming a product area, guest, company, or framework so I can retrieve the right episodes."
                )
            else:
                answer_text = (
                    "I don't have enough grounded transcript evidence to generate that artifact safely. "
                    "Please narrow the request or point me to a specific guest, topic, or episode."
                )
            if fallback_note:
                answer_text = f"{fallback_note}\n\n{answer_text}"
            assistant_message = self._persist_assistant_message(
                db,
                session=session,
                content=answer_text,
                route=decision.route,
                provider=provider.key,
                citations=citations,
                artifact=None,
            )
            self._maybe_set_session_title(session, content)
            db.commit()
            db.refresh(assistant_message)
            db.refresh(session)
            return {"message": assistant_message, "provider": provider.key, "retrieval_summary": retrieval_summary}

        artifact_payload: ArtifactPayload | None = None
        if decision.route == "qa":
            completion = provider.generate(
                system=qa_system_prompt(),
                prompt=qa_user_prompt(content, history, build_context_block(results)),
            )
            answer_text = completion.text.strip()
        elif decision.route == "ship30":
            completion = provider.generate(
                system=ship30_system_prompt(),
                prompt=ship30_user_prompt(content, history, build_context_block(results)),
            )
            answer_text, artifact_payload = self.artifacts.parse_artifact_block(completion.text)
            if artifact_payload is None:
                artifact_payload = self.artifacts.create_markdown_artifact(
                    "Grounded Ship 30 Essay", completion.text.strip()
                )
                answer_text = "I drafted a grounded long-form essay in the artifact pane."
        else:
            artifact_type = decision.artifact_type or "markdown"
            completion = provider.generate(
                system=artifact_system_prompt(),
                prompt=artifact_user_prompt(content, history, build_context_block(results), artifact_type),
            )
            answer_text, artifact_payload = self.artifacts.parse_artifact_block(completion.text)
            if artifact_payload is None:
                artifact_payload = (
                    self.artifacts.create_html_artifact("Grounded HTML Artifact", completion.text)
                    if artifact_type == "html"
                    else self.artifacts.create_markdown_artifact("Grounded Markdown Artifact", completion.text)
                )
                answer_text = "I created a grounded artifact in the viewer."

        if fallback_note:
            answer_text = f"{fallback_note}\n\n{answer_text}".strip()

        assistant_message = self._persist_assistant_message(
            db,
            session=session,
            content=answer_text,
            route=decision.route,
            provider=provider.key,
            citations=citations,
            artifact=artifact_payload,
        )
        self._maybe_set_session_title(session, content)
        db.commit()
        db.refresh(assistant_message)
        db.refresh(session)
        return {"message": assistant_message, "provider": provider.key, "retrieval_summary": retrieval_summary}

    def _persist_assistant_message(
        self,
        db: Session,
        *,
        session: ChatSession,
        content: str,
        route: str,
        provider: str,
        citations: list[dict[str, Any]],
        artifact: ArtifactPayload | None,
    ) -> Message:
        artifact_row: Artifact | None = None
        if artifact:
            artifact_row = Artifact(
                session_id=session.id,
                title=artifact.title,
                artifact_type=artifact.artifact_type,
                raw_content=artifact.raw_content,
                sanitized_content=artifact.sanitized_content,
                render_mode=artifact.render_mode,
            )
            db.add(artifact_row)
            db.flush()

        assistant_message = Message(
            session_id=session.id,
            role="assistant",
            content=content,
            route=route,
            provider=provider,
            citations=citations,
            artifact_id=artifact_row.id if artifact_row else None,
        )
        db.add(assistant_message)
        db.flush()
        if artifact_row:
            assistant_message.artifact = artifact_row
        return assistant_message

    def _history_block(self, messages: list[Message]) -> str:
        recent = messages[-6:]
        return "\n".join(f"{msg.role.upper()}: {msg.content}" for msg in recent)

    def _build_retrieval_query(self, messages: list[Message]) -> str:
        user_turns = [msg.content for msg in messages if msg.role == "user"][-3:]
        return "\n".join(user_turns)

    def _citation_from_result(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "transcript_title": item["transcript_title"],
            "guest": item.get("guest"),
            "publish_date": item.get("publish_date"),
            "source_path": item["source_path"],
            "youtube_url": item.get("youtube_url"),
            "snippet": item.get("snippet") or item["text"][:280],
            "score": round(float(item.get("score", 0.0)), 4),
        }

    def _maybe_set_session_title(self, session: ChatSession, first_message: str) -> None:
        session.updated_at = datetime.now(timezone.utc)
        if session.title and session.title != "New chat":
            return
        compact = first_message.strip().splitlines()[0][:70]
        session.title = compact if len(compact) < 70 else f"{compact[:67]}..."
