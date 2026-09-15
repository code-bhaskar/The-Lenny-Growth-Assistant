from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from html import escape as html_escape
from typing import Any, Literal

from app.agent.providers import ProviderConfig, ProviderRegistry
from app.agent.skills import load_all_skills
from app.api.errors import ProviderUnavailableError
from app.core.config import REPO_ROOT, get_settings
from app.core.logging import get_logger, info, warning

logger = get_logger(__name__)

try:  # pragma: no cover - optional at import time
    from pi_coding_agent import MessageUpdateEvent, create_agent_session_from_config
except Exception:  # pragma: no cover - optional dependency missing
    MessageUpdateEvent = None
    create_agent_session_from_config = None


@dataclass
class AgentResult:
    route: Literal["qa", "ship30", "artifact"]
    answer: str
    artifact: dict[str, Any] | None
    provider: str
    model: str


class PiAgentService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.providers = ProviderRegistry()

    def generate(
        self,
        *,
        conversation: str,
        retrieval_context: str,
        user_request: str,
        provider_name: str | None = None,
        force_artifact_type: str | None = None,
    ) -> tuple[AgentResult, str | None]:
        provider, fallback_note = self.providers.resolve(provider_name)
        if create_agent_session_from_config is None:
            raise ProviderUnavailableError("pi-coding-agent-python-sdk is not installed")
        result = asyncio.run(
            self._generate_async(
                provider=provider,
                conversation=conversation,
                retrieval_context=retrieval_context,
                user_request=user_request,
                force_artifact_type=force_artifact_type,
            )
        )
        return result, fallback_note

    async def _generate_async(
        self,
        *,
        provider: ProviderConfig,
        conversation: str,
        retrieval_context: str,
        user_request: str,
        force_artifact_type: str | None,
    ) -> AgentResult:
        prompt = self._build_prompt(
            conversation=conversation,
            retrieval_context=retrieval_context,
            user_request=user_request,
            force_artifact_type=force_artifact_type,
        )
        config = self._build_config(provider)
        session_result = await create_agent_session_from_config(config, cwd=str(REPO_ROOT))
        session = session_result.session
        deltas: list[str] = []

        if MessageUpdateEvent is not None:
            session.subscribe(
                lambda event: deltas.append(getattr(event.assistant_message_event, "delta", ""))
                if isinstance(event, MessageUpdateEvent)
                else None
            )

        try:
            await session.prompt(prompt)
            raw_output = "".join(deltas).strip() if deltas else self._serialized_output(session)
            try:
                parsed = self._parse_output(raw_output)
            except ProviderUnavailableError:
                if self.settings.pi_agent_backend == "in_process":
                    parsed = self._offline_result(user_request, retrieval_context, force_artifact_type)
                else:
                    raise
            info(
                logger,
                "pi_agent_completed",
                provider=provider.key,
                model=provider.model,
                route=parsed["route"],
            )
            return AgentResult(
                route=parsed["route"],
                answer=parsed["answer"],
                artifact=parsed.get("artifact"),
                provider=provider.key,
                model=provider.model,
            )
        finally:
            await session.dispose()

    def _build_config(self, provider: ProviderConfig) -> dict[str, Any]:
        config: dict[str, Any] = {
            "version": 1,
            "run": {"cwd": str(REPO_ROOT), "backend": self.settings.pi_agent_backend},
            "model": {
                "provider": provider.key,
                "id": provider.model,
                "api": provider.api_mode,
                "base_url": provider.base_url,
                "context_window": provider.context_window,
                "max_tokens": provider.max_tokens,
                "reasoning": provider.reasoning,
            },
            "provider_options": {
                "temperature": self.settings.pi_agent_temperature,
                "tool_choice": "auto",
                "parallel_tool_calls": False,
            },
            "tools": {"allow": []},
            "thinking_level": self.settings.pi_agent_thinking_level,
        }
        if provider.api_key_env:
            config["model"]["api_key_env"] = provider.api_key_env
        if provider.api_key:
            config["model"]["api_key"] = provider.api_key
        return config

    def _build_prompt(
        self,
        *,
        conversation: str,
        retrieval_context: str,
        user_request: str,
        force_artifact_type: str | None,
    ) -> str:
        skills = load_all_skills()
        artifact_instruction = (
            f"The caller explicitly requested an artifact of type '{force_artifact_type}'."
            if force_artifact_type
            else "Decide whether this is grounded Q&A, Ship 30 essay generation, or general artifact generation."
        )
        return f"""
You are the agent layer for The Lenny Growth Assistant.

Use the conversation and retrieved transcript evidence to choose the correct route:
- qa
- ship30
- artifact

Rules:
- Ground every major claim in the retrieved transcript evidence.
- If the evidence is insufficient, answer conservatively and say what is not established.
- If an artifact is produced, return it inline as JSON.
- For HTML artifacts, return full HTML/CSS with no JavaScript.
- For Ship 30 essays, produce approximately 1,250 words with a strong hook, skimmable headings, bullets, selective bold emphasis, and a useful takeaway.
- Never include markdown code fences around the final JSON.

Available skill definitions:
{skills}

Conversation:
{conversation}

Retrieved transcript evidence:
{retrieval_context}

User request:
{user_request}

Additional routing guidance:
{artifact_instruction}

Return valid JSON exactly matching this schema:
{{
  "route": "qa" | "ship30" | "artifact",
  "answer": "string",
  "artifact": null | {{
    "title": "string",
    "type": "markdown" | "html",
    "content": "string"
  }}
}}
""".strip()

    def _serialized_output(self, session: Any) -> str:
        data = session.serialize()
        messages = data.get("messages", [])
        assistant_messages = [m.get("content", "") for m in messages if m.get("role") == "assistant"]
        return assistant_messages[-1].strip() if assistant_messages else ""

    def _offline_result(
        self, user_request: str, retrieval_context: str, force_artifact_type: str | None
    ) -> dict[str, Any]:
        lowered = user_request.lower()
        route = "qa"
        artifact = None
        first_excerpt = retrieval_context.split("Transcript excerpt:")[-1].strip() if retrieval_context else ""
        supporting_text = re.sub(r"\s+", " ", first_excerpt)[:500]
        if force_artifact_type == "html" or "html" in lowered or "css" in lowered:
            route = "artifact"
            artifact = {
                "title": "Grounded HTML Artifact",
                "type": "html",
                "content": (
                    "<html><body><h1>Lenny Growth Notes</h1><p>"
                    + html_escape(supporting_text)
                    + "</p></body></html>"
                ),
            }
            answer = "Created a grounded HTML artifact using the retrieved transcript evidence."
        elif force_artifact_type == "markdown" or "ship 30" in lowered or "essay" in lowered:
            route = "ship30" if "ship 30" in lowered or "essay" in lowered else "artifact"
            artifact = {
                "title": "Grounded Ship 30 Essay" if route == "ship30" else "Grounded Markdown Artifact",
                "type": "markdown",
                "content": (
                    "# Grounded takeaway\n\n"
                    "**Hook.** The clearest teams make fewer, sharper bets.\n\n"
                    "## Evidence\n"
                    f"- {supporting_text}\n\n"
                    "## Practical takeaway\n"
                    "Audit your onboarding around one core action.\n"
                ),
            }
            answer = "Drafted a grounded markdown artifact based on the retrieved transcript evidence."
        else:
            answer = (
                "Based on the retrieved transcripts, the strongest signal is: "
                + (supporting_text or "the evidence is limited, so narrow the question further.")
            )
        return {"route": route, "answer": answer, "artifact": artifact}

    def _parse_output(self, raw_output: str) -> dict[str, Any]:
        text = raw_output.strip()
        if not text:
            raise ProviderUnavailableError("Pi agent returned an empty response")
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL)
        if not text.startswith("{"):
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if match:
                text = match.group(0)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            warning(logger, "pi_agent_parse_failed", raw_output=raw_output)
            raise ProviderUnavailableError(f"Pi agent returned non-JSON output: {exc}") from exc

        route = data.get("route") or "qa"
        answer = (data.get("answer") or "").strip()
        artifact = data.get("artifact")
        if route not in {"qa", "ship30", "artifact"}:
            route = "qa"
        if artifact and artifact.get("type") not in {"markdown", "html"}:
            artifact = None
        return {"route": route, "answer": answer, "artifact": artifact}
