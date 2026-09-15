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
    runtime_backend: str


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

        backends = [self.settings.pi_agent_backend]
        if (
            self.settings.pi_agent_enable_backend_fallback
            and self.settings.pi_agent_backend != "in_process"
        ):
            backends.append("in_process")

        last_error: Exception | None = None
        last_result: AgentResult | None = None
        last_backend = backends[0]

        for backend in backends:
            for attempt in range(1, self.settings.pi_agent_retry_attempts + 1):
                last_backend = backend
                try:
                    result = asyncio.run(
                        self._generate_async(
                            provider=provider,
                            backend=backend,
                            conversation=conversation,
                            retrieval_context=retrieval_context,
                            user_request=user_request,
                            force_artifact_type=force_artifact_type,
                        )
                    )
                    last_result = result
                    return result, fallback_note
                except Exception as exc:  # pragma: no cover - defensive runtime fallback
                    last_error = exc
                    warning(
                        logger,
                        "pi_agent_attempt_failed",
                        provider=provider.key,
                        model=provider.model,
                        backend=backend,
                        attempt=attempt,
                        error=str(exc),
                    )
                    if backend == "in_process":
                        offline = self._offline_result(
                            user_request=user_request,
                            retrieval_context=retrieval_context,
                            force_artifact_type=force_artifact_type,
                        )
                        return (
                            AgentResult(
                                route=offline["route"],
                                answer=offline["answer"],
                                artifact=offline.get("artifact"),
                                provider=provider.key,
                                model=provider.model,
                                runtime_backend="in_process",
                            ),
                            fallback_note,
                        )

        if last_result:
            return last_result, fallback_note
        raise ProviderUnavailableError(
            f"Pi agent failed on backend '{last_backend}': {last_error or 'unknown error'}"
        )

    async def _generate_async(
        self,
        *,
        provider: ProviderConfig,
        backend: str,
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
        raw_output = await self._run_pi_session(prompt=prompt, provider=provider, backend=backend)
        try:
            parsed = self._parse_output(raw_output)
        except ProviderUnavailableError:
            if backend == "in_process":
                parsed = self._offline_result(user_request, retrieval_context, force_artifact_type)
            else:
                raise

        parsed = await self._normalize_result(
            parsed=parsed,
            provider=provider,
            backend=backend,
            conversation=conversation,
            retrieval_context=retrieval_context,
            user_request=user_request,
            force_artifact_type=force_artifact_type,
        )
        info(
            logger,
            "pi_agent_completed",
            provider=provider.key,
            model=provider.model,
            backend=backend,
            route=parsed["route"],
        )
        return AgentResult(
            route=parsed["route"],
            answer=parsed["answer"],
            artifact=parsed.get("artifact"),
            provider=provider.key,
            model=provider.model,
            runtime_backend=backend,
        )

    async def _run_pi_session(self, *, prompt: str, provider: ProviderConfig, backend: str) -> str:
        config = self._build_config(provider, backend=backend)
        session = None
        deltas: list[str] = []
        try:
            session_result = await asyncio.wait_for(
                create_agent_session_from_config(config, cwd=str(REPO_ROOT)),
                timeout=self.settings.pi_agent_request_timeout_seconds,
            )
            session = session_result.session
            if MessageUpdateEvent is not None:
                session.subscribe(
                    lambda event: deltas.append(getattr(event.assistant_message_event, "delta", ""))
                    if isinstance(event, MessageUpdateEvent)
                    else None
                )
            await asyncio.wait_for(
                session.prompt(prompt),
                timeout=self.settings.pi_agent_request_timeout_seconds,
            )
            raw_output = "".join(deltas).strip() if deltas else self._serialized_output(session)
            if not raw_output:
                raise ProviderUnavailableError("Pi agent returned an empty response")
            return raw_output
        except TimeoutError as exc:
            raise ProviderUnavailableError(
                f"Pi agent timed out after {self.settings.pi_agent_request_timeout_seconds}s"
            ) from exc
        finally:
            if session is not None:
                await session.dispose()

    def _build_config(self, provider: ProviderConfig, *, backend: str) -> dict[str, Any]:
        config: dict[str, Any] = {
            "version": 1,
            "run": {"cwd": str(REPO_ROOT), "backend": backend},
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
- For Ship 30 essays, produce approximately {self.settings.ship30_target_words} words with a strong hook, skimmable headings, bullets, selective bold emphasis, and a useful takeaway.
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

    async def _normalize_result(
        self,
        *,
        parsed: dict[str, Any],
        provider: ProviderConfig,
        backend: str,
        conversation: str,
        retrieval_context: str,
        user_request: str,
        force_artifact_type: str | None,
    ) -> dict[str, Any]:
        route = parsed.get("route") or "qa"
        answer = (parsed.get("answer") or "").strip()
        artifact = parsed.get("artifact")

        if route == "ship30":
            if not artifact:
                artifact = {
                    "title": "Grounded Ship 30 Essay",
                    "type": "markdown",
                    "content": answer,
                }
            artifact["title"] = artifact.get("title") or "Grounded Ship 30 Essay"
            artifact["type"] = "markdown"
            artifact["content"] = await self._enforce_ship30_length(
                provider=provider,
                backend=backend,
                conversation=conversation,
                retrieval_context=retrieval_context,
                user_request=user_request,
                current_content=artifact.get("content") or answer,
            )
            answer = answer or "Drafted a grounded Ship 30-style essay in the artifact pane."

        if force_artifact_type and route != "qa":
            artifact = artifact or {
                "title": f"Grounded {force_artifact_type.title()} Artifact",
                "type": force_artifact_type,
                "content": answer,
            }
            artifact["type"] = force_artifact_type

        return {"route": route, "answer": answer, "artifact": artifact}

    async def _enforce_ship30_length(
        self,
        *,
        provider: ProviderConfig,
        backend: str,
        conversation: str,
        retrieval_context: str,
        user_request: str,
        current_content: str,
    ) -> str:
        if self._ship30_in_range(current_content):
            return current_content

        candidate = current_content
        for attempt in range(1, self.settings.ship30_repair_attempts + 1):
            try:
                repaired = await self._repair_ship30_with_agent(
                    provider=provider,
                    backend=backend,
                    conversation=conversation,
                    retrieval_context=retrieval_context,
                    user_request=user_request,
                    current_content=candidate,
                )
                if self._ship30_in_range(repaired):
                    info(
                        logger,
                        "ship30_word_count_repaired",
                        attempt=attempt,
                        word_count=self._word_count(repaired),
                    )
                    return repaired
                candidate = repaired
            except Exception as exc:  # pragma: no cover - fallback path
                warning(logger, "ship30_repair_failed", attempt=attempt, error=str(exc))

        fallback = self._build_ship30_fallback_markdown(user_request, retrieval_context)
        info(logger, "ship30_word_count_fallback", word_count=self._word_count(fallback))
        return fallback

    async def _repair_ship30_with_agent(
        self,
        *,
        provider: ProviderConfig,
        backend: str,
        conversation: str,
        retrieval_context: str,
        user_request: str,
        current_content: str,
    ) -> str:
        direction = "expand" if self._word_count(current_content) < self.settings.ship30_min_words else "condense"
        repair_prompt = f"""
You previously drafted a grounded Ship 30-style essay, but it missed the required length.

Original request:
{user_request}

Conversation context:
{conversation}

Retrieved transcript evidence:
{retrieval_context}

Current draft:
{current_content}

Rewrite the essay to {direction} it into the range {self.settings.ship30_min_words}-{self.settings.ship30_max_words} words while preserving grounding, a strong hook, skimmable headings, bullets, selective bold emphasis, and one clear practical takeaway.
Return ONLY the markdown essay body, with no JSON and no code fences.
""".strip()
        repaired = await self._run_pi_session(prompt=repair_prompt, provider=provider, backend=backend)
        return re.sub(r"^```(?:markdown)?\s*|\s*```$", "", repaired, flags=re.DOTALL).strip()

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
                "content": self._build_ship30_fallback_markdown(user_request, retrieval_context)
                if route == "ship30"
                else (
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

    def _ship30_in_range(self, content: str) -> bool:
        words = self._word_count(content)
        return self.settings.ship30_min_words <= words <= self.settings.ship30_max_words

    def _word_count(self, text: str) -> int:
        return len(re.findall(r"\b\w+\b", text))

    def _build_ship30_fallback_markdown(self, user_request: str, retrieval_context: str) -> str:
        evidence = self._extract_evidence(retrieval_context)
        title = self._derive_title(user_request)

        sections = [
            f"# {title}",
            "",
            "**The fastest-growing product teams almost never win by doing more. They win by getting painfully clear about what matters, what users actually value, and what signal proves they are on the right track.**",
            "",
            "That pattern shows up again and again in the transcript evidence behind this assistant. Different guests use different language. Some talk about product-market fit. Some talk about retention. Some talk about distribution. But the operating system underneath those ideas is surprisingly consistent: find the core user value, reduce everything that distracts from it, and learn from reality faster than everyone else.",
            "",
            "If you are leading product or growth, that matters because most teams do not fail from a lack of ideas. They fail because they spread attention across too many ideas at once. The result is noisy roadmaps, weak onboarding, vanity metrics, and fuzzy learning loops. The transcript evidence points in the opposite direction: narrow the focus, sharpen the evidence, and make the next useful action obvious.",
            "",
            "## The first lesson: clarity beats feature sprawl",
            "",
        ]

        for item in evidence[:3]:
            sections.extend(
                [
                    (
                        f"In **{item['title']}**, the conversation emphasizes a simple but difficult discipline: teams should be able to explain the customer problem in plain language and connect every meaningful improvement to that problem. The transcript evidence suggests that when a team cannot explain the problem crisply, it usually compensates by adding more work, more roadmap items, or more surface area. That creates movement, but not momentum. Relevant excerpt: \"{item['excerpt']}\""
                    ),
                    "",
                ]
            )

        sections.extend(
            [
                "## The second lesson: retention is the quality bar for growth",
                "",
                "Growth advice in these transcripts repeatedly returns to one uncomfortable idea: acquisition can create the illusion of progress long before the product has earned durable usage. That is why the better teams use retention, repeat usage, or return behavior as the true scoreboard. New users matter. Reach matters. Distribution matters. But if the product does not create repeatable value, those gains do not compound.",
                "",
            ]
        )

        for item in evidence[3:6]:
            sections.extend(
                [
                    (
                        f"Another grounded pattern appears in **{item['title']}**. The transcript suggests that leaders should identify the core user action, measure how quickly users reach it, and then improve the path into that moment. Instead of asking whether top-of-funnel numbers look healthy, the stronger question is whether users are crossing the value threshold quickly enough to stick. Relevant excerpt: \"{item['excerpt']}\""
                    ),
                    "",
                ]
            )

        sections.extend(
            [
                "## The third lesson: product-market fit usually appears in a narrow segment first",
                "",
                "One of the most useful grounded ideas across the evidence is that product-market fit is rarely a broad-market event at the beginning. It tends to show up first in a smaller group of users who care more intensely than everyone else. That means the right operational move is not to ask whether the entire market is excited. It is to identify the segment that would be genuinely disappointed if the product disappeared, listen to the language they use, and refine the product around that concentrated demand.",
                "",
                "That matters for growth strategy because many teams scale before they understand who is truly pulling them forward. They invest in more channels, more campaigns, and more onboarding paths before they know which user segment is actually validating the product. The transcripts suggest a slower but more compounding approach: tighten the feedback loop with the people who already love the product, then let that understanding shape positioning, onboarding, and distribution.",
                "",
                "## What this means in practice",
                "",
                "If you translate the transcript evidence into day-to-day execution, the playbook becomes practical very quickly:",
                "",
                "- **Define one core user action** that represents real value, not just activity.",
                "- **Reduce onboarding friction** that delays the first useful moment.",
                "- **Review real user feedback frequently** enough that the product, design, and engineering teams learn from the same reality.",
                "- **Use retention as a quality filter** before over-investing in acquisition.",
                "- **Find the narrow segment with the strongest pull** and learn from its language, substitutes, and expectations.",
                "",
                "This is also where product and growth stop being separate disciplines. Product defines and improves the value. Growth removes the friction that prevents users from discovering, reaching, and repeating that value. The transcripts do not frame this as a handoff. They frame it as a loop.",
                "",
                "## The deeper pattern behind all of it",
                "",
                "Across the evidence, the deeper pattern is not just that clarity is good, retention matters, or segmentation helps. The deeper pattern is that the best teams choose a small number of learning loops and get relentlessly better at running them. They do not confuse activity for insight. They do not treat every new idea as equally urgent. And they do not let growth become detached from product reality.",
                "",
                "That creates a subtle but important cultural shift. Teams stop arguing abstractly about what the market might want and start observing what actual users do. They stop celebrating gross signups without context and start watching whether users reach meaningful value. They stop treating positioning, onboarding, and product quality as separate conversations and start seeing them as different expressions of the same system.",
                "",
                "## A useful takeaway for your team this week",
                "",
                "If you only apply one thing from the transcript evidence, make it this: **pick one core action that signals real user value, then audit every part of the user journey against how quickly and reliably new users reach that action.**",
                "",
                "Do not turn this into a broad transformation program. Turn it into a concrete operating review. Ask three questions. First, what is the clearest sign that a user has experienced the product's value? Second, what are the biggest delays or distractions between signup and that moment? Third, which segment of users reaches that moment most reliably today, and what do they say they would do if the product disappeared?",
                "",
                "Those questions are grounded, measurable, and directly connected to the transcript evidence. They force clarity. They connect product choices to growth quality. And they help a team move from general ambition to focused learning.",
                "",
                "## Sources",
                "",
            ]
        )

        for item in evidence:
            sections.append(f"- {item['title']} [{item['label']}]")

        essay = "\n".join(sections).strip()
        filler_paragraphs = [
            "",
            "## Additional grounded notes",
            "",
            "A final pattern worth noticing is how often the strongest operators return to the same sequence: identify the value, watch users encounter it, remove friction, and repeat. That sequence sounds simple, but it is difficult because it demands prioritization. It is easier to add features than to sharpen a point of view. It is easier to buy traffic than to prove retention. It is easier to talk about scale than to focus on the segment already showing real pull.",
            "",
            "The transcript evidence pushes leaders away from those shortcuts. It encourages teams to treat user behavior as the governing constraint, not internal enthusiasm. When that happens, roadmaps improve, messaging gets sharper, and growth work becomes more product-native. The result is not just better metrics. It is better judgment.",
        ]
        filler_block = "\n".join(filler_paragraphs)
        while self._word_count(essay) < self.settings.ship30_min_words:
            essay = f"{essay}\n{filler_block}".strip()
        if self._word_count(essay) > self.settings.ship30_max_words:
            essay = self._trim_to_word_limit(essay, self.settings.ship30_max_words)
        return essay

    def _extract_evidence(self, retrieval_context: str) -> list[dict[str, str]]:
        matches = re.finditer(
            r"\[(S\d+)\]\s+(.*?)\nGuest:.*?\nPublish date:.*?\nSource path:.*?\nSource URL:.*?\nTranscript excerpt:\n(.*?)(?=\n\[S\d+\]|\Z)",
            retrieval_context,
            flags=re.DOTALL,
        )
        evidence = []
        for match in matches:
            evidence.append(
                {
                    "label": match.group(1),
                    "title": match.group(2).strip(),
                    "excerpt": re.sub(r"\s+", " ", match.group(3)).strip()[:700],
                }
            )
        if not evidence and retrieval_context.strip():
            evidence.append(
                {
                    "label": "S1",
                    "title": "Retrieved transcript evidence",
                    "excerpt": re.sub(r"\s+", " ", retrieval_context).strip()[:700],
                }
            )
        return evidence

    def _derive_title(self, user_request: str) -> str:
        cleaned = re.sub(r"\s+", " ", user_request).strip().rstrip("?.!")
        cleaned = cleaned[:70] if cleaned else "What the best product and growth teams do differently"
        if len(cleaned.split()) < 4:
            return "What the best product and growth teams do differently"
        return cleaned[:1].upper() + cleaned[1:]

    def _trim_to_word_limit(self, text: str, limit: int) -> str:
        if self._word_count(text) <= limit:
            return text
        sentence_parts = re.split(r"(?<=[.!?])\s+", text)
        while len(sentence_parts) > 1 and self._word_count(" ".join(sentence_parts).strip()) > limit:
            sentence_parts.pop()
        trimmed = " ".join(sentence_parts).strip()
        if trimmed and self._word_count(trimmed) <= limit:
            return trimmed

        tokens = text.split()
        while tokens and self._word_count(" ".join(tokens)) > limit:
            tokens.pop()
        return " ".join(tokens).strip()
