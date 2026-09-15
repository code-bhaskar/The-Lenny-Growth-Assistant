from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.api.errors import ProviderUnavailableError
from app.core.config import get_settings

try:  # pragma: no cover - optional dependency
    from claude_agent_sdk import ClaudeAgentOptions, query
except Exception:  # pragma: no cover - optional dependency
    ClaudeAgentOptions = None
    query = None


@dataclass
class ClaudeSdkResult:
    text: str


class ClaudeAgentSdkAdapter:
    def __init__(self) -> None:
        self.settings = get_settings()

    def is_available(self) -> tuple[bool, str | None]:
        if not self.settings.enable_claude_agent_sdk:
            return False, "Claude Agent SDK disabled"
        if not self.settings.anthropic_api_key:
            return False, "ANTHROPIC_API_KEY not configured"
        if query is None or ClaudeAgentOptions is None:
            return False, "claude-agent-sdk not installed"
        return True, None

    def generate(self, *, system: str, prompt: str) -> ClaudeSdkResult:
        available, reason = self.is_available()
        if not available:
            raise ProviderUnavailableError(reason or "Claude Agent SDK unavailable")
        return asyncio.run(self._generate_async(system=system, prompt=prompt))

    async def _generate_async(self, *, system: str, prompt: str) -> ClaudeSdkResult:
        assert ClaudeAgentOptions is not None
        assert query is not None
        options = ClaudeAgentOptions(
            system_prompt=system,
            model=self.settings.claude_agent_sdk_model,
            permission_mode="default",
            max_turns=3,
        )
        chunks: list[str] = []
        async for message in query(prompt=prompt, options=options):
            text = getattr(message, "text", None)
            if text:
                chunks.append(text)
        return ClaudeSdkResult(text="\n".join(chunks).strip())
