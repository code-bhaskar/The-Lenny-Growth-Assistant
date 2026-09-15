from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.agent.pi_agent import AgentResult, PiAgentService
from app.api.errors import NotFoundError
from app.core.config import get_settings
from app.core.logging import get_logger, info
from app.db.models import Artifact, Message, Session
from app.services.artifacts import ArtifactPayload, ArtifactService
from app.services.knowledge import RetrievalService

logger = get_logger(__name__)


class SessionService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.retrieval = RetrievalService()
        self.artifacts = ArtifactService()
        self.agent = PiAgentService()

    def create_session(self, db: OrmSession, *, title: str | None, user_metadata: dict[str, Any]) -> Session:
        session = Session(
            title=title or "New chat",
            user_metadata={"user_name": self.settings.default_user_name, **(user_metadata or {})},
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def list_sessions(self, db: OrmSession) -> list[Session]:
        stmt = select(Session).order_by(Session.updated_at.desc(), Session.created_at.desc())
        return list(db.scalars(stmt))

    def get_session(self, db: OrmSession, session_id: str) -> Session:
        session = db.get(Session, session_id)
        if not session:
            raise NotFoundError(f"Session '{session_id}' not found")
        return session

    def list_messages(self, db: OrmSession, session_id: str) -> list[Message]:
        session = self.get_session(db, session_id)
        return session.messages

    def create_message(
        self,
        db: OrmSession,
        *,
        session_id: str,
        content: str,
        provider_name: str | None,
    ) -> Message:
        session = self.get_session(db, session_id)
        user_message = Message(
            session_id=session.id,
            role="user",
            content=content,
            metadata_json={"provider_request": provider_name or self.settings.llm_provider},
            citations=[],
        )
        db.add(user_message)
        db.flush()

        history = self._history_text(session.messages + [user_message])
        retrieval_query = self._retrieval_query(session.messages + [user_message])
        retrieval_results = self.retrieval.search(db, retrieval_query)
        retrieval_summary = self.retrieval.summarize(retrieval_results)
        citations = self.retrieval.to_citations(retrieval_results)

        if retrieval_summary["status"] != "grounded":
            assistant_message = Message(
                session_id=session.id,
                role="assistant",
                content=(
                    "I couldn't find enough grounded transcript evidence to answer that confidently. "
                    "Try naming a guest, company, framework, or product area."
                ),
                metadata_json={
                    "route": "qa",
                    "provider": provider_name or self.settings.llm_provider,
                    "retrieval_summary": retrieval_summary,
                },
                citations=citations,
            )
            db.add(assistant_message)
            session.updated_at = datetime.now(timezone.utc)
            self._maybe_set_title(session, content)
            db.commit()
            db.refresh(assistant_message)
            return assistant_message

        agent_result, fallback_note = self.agent.generate(
            conversation=history,
            retrieval_context=self.retrieval.build_context_block(retrieval_results),
            user_request=content,
            provider_name=provider_name,
        )
        assistant_message = self._persist_assistant_message(
            db,
            session=session,
            agent_result=agent_result,
            retrieval_summary=retrieval_summary,
            citations=citations,
            fallback_note=fallback_note,
        )
        session.updated_at = datetime.now(timezone.utc)
        self._maybe_set_title(session, content)
        db.commit()
        db.refresh(assistant_message)
        return assistant_message

    def create_artifact(
        self,
        db: OrmSession,
        *,
        session_id: str,
        instruction: str,
        artifact_type: str,
        provider_name: str | None,
        message_id: str | None,
    ) -> Artifact:
        session = self.get_session(db, session_id)
        base_messages = session.messages
        retrieval_query = "\n".join([instruction] + [m.content for m in base_messages if m.role == "user"][-2:])
        retrieval_results = self.retrieval.search(db, retrieval_query)
        retrieval_summary = self.retrieval.summarize(retrieval_results)
        citations = self.retrieval.to_citations(retrieval_results)
        if retrieval_summary["status"] != "grounded":
            raise NotFoundError(
                "The knowledge base did not return enough evidence to safely generate that artifact."
            )

        agent_result, fallback_note = self.agent.generate(
            conversation=self._history_text(base_messages),
            retrieval_context=self.retrieval.build_context_block(retrieval_results),
            user_request=instruction,
            provider_name=provider_name,
            force_artifact_type=artifact_type,
        )
        artifact_info = agent_result.artifact or {
            "title": f"{artifact_type.title()} Artifact",
            "type": artifact_type,
            "content": agent_result.answer,
        }
        payload = self.artifacts.create(artifact_info["type"], artifact_info["title"], artifact_info["content"])
        artifact = Artifact(
            session_id=session.id,
            message_id=message_id,
            title=payload.title,
            type=payload.type,
            content=payload.content,
            sanitized_content=payload.sanitized_content,
            render_mode=payload.render_mode,
        )
        db.add(artifact)
        db.flush()
        if message_id:
            message = db.get(Message, message_id)
            if message:
                meta = dict(message.metadata_json or {})
                meta["route"] = agent_result.route
                meta["provider"] = agent_result.provider
                meta["model"] = agent_result.model
                meta["retrieval_summary"] = retrieval_summary
                meta["fallback_note"] = fallback_note
                meta["runtime_backend"] = agent_result.runtime_backend
                meta["artifact_word_count"] = self._word_count(payload.content)
                meta.setdefault("artifact_ids", []).append(artifact.id)
                message.metadata_json = meta
                message.citations = citations
        db.commit()
        db.refresh(artifact)
        info(
            logger,
            "artifact_created",
            session_id=session_id,
            artifact_id=artifact.id,
            artifact_type=artifact.type,
            provider=agent_result.provider,
        )
        return artifact

    def get_artifact(self, db: OrmSession, artifact_id: str) -> Artifact:
        artifact = db.get(Artifact, artifact_id)
        if not artifact:
            raise NotFoundError(f"Artifact '{artifact_id}' not found")
        return artifact

    def _persist_assistant_message(
        self,
        db: OrmSession,
        *,
        session: Session,
        agent_result: AgentResult,
        retrieval_summary: dict[str, Any],
        citations: list[dict[str, Any]],
        fallback_note: str | None,
    ) -> Message:
        artifact_rows: list[Artifact] = []
        if agent_result.artifact:
            payload = self.artifacts.create(
                agent_result.artifact["type"],
                agent_result.artifact["title"],
                agent_result.artifact["content"],
            )
            artifact = Artifact(
                session_id=session.id,
                title=payload.title,
                type=payload.type,
                content=payload.content,
                sanitized_content=payload.sanitized_content,
                render_mode=payload.render_mode,
            )
            db.add(artifact)
            db.flush()
            artifact_rows.append(artifact)

        content = agent_result.answer
        if fallback_note:
            content = f"{fallback_note}\n\n{content}".strip()

        message = Message(
            session_id=session.id,
            role="assistant",
            content=content,
            metadata_json={
                "route": agent_result.route,
                "provider": agent_result.provider,
                "model": agent_result.model,
                "retrieval_summary": retrieval_summary,
                "fallback_note": fallback_note,
                "artifact_ids": [artifact.id for artifact in artifact_rows],
                "artifact_word_count": self._word_count(artifact_rows[0].content) if artifact_rows else None,
                "runtime_backend": agent_result.runtime_backend,
            },
            citations=citations,
        )
        db.add(message)
        db.flush()

        for artifact in artifact_rows:
            artifact.message_id = message.id
        info(
            logger,
            "assistant_message_created",
            session_id=session.id,
            route=agent_result.route,
            provider=agent_result.provider,
            model=agent_result.model,
            retrieval_count=len(citations),
            artifact_type=artifact_rows[0].type if artifact_rows else None,
        )
        return message

    def _history_text(self, messages: list[Message]) -> str:
        recent = messages[-6:]
        return "\n".join(f"{message.role.upper()}: {message.content}" for message in recent)

    def _retrieval_query(self, messages: list[Message]) -> str:
        return "\n".join([message.content for message in messages if message.role == "user"][-3:])

    def _maybe_set_title(self, session: Session, seed: str) -> None:
        if session.title and session.title != "New chat":
            return
        base = seed.strip().splitlines()[0][:70]
        session.title = base if len(base) < 70 else f"{base[:67]}..."

    def _word_count(self, text: str) -> int:
        return len(re.findall(r"\b\w+\b", text))
