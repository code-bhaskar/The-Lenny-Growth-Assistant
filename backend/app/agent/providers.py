from __future__ import annotations

from dataclasses import dataclass

import requests

from app.api.errors import ProviderUnavailableError
from app.core.config import get_settings


@dataclass
class ProviderConfig:
    key: str
    label: str
    model: str
    base_url: str | None = None
    api_key_env: str | None = None
    api_key: str | None = None
    api_mode: str = "openai-completions"
    context_window: int = 32768
    max_tokens: int = 4000
    reasoning: bool = False


class ProviderRegistry:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _ollama_config(self) -> ProviderConfig:
        return ProviderConfig(
            key="ollama",
            label="Ollama",
            model=self.settings.ollama_model,
            base_url=f"{self.settings.ollama_base_url.rstrip('/')}/v1",
            api_key="ollama",
            context_window=self.settings.ollama_context_window,
            max_tokens=self.settings.pi_agent_max_tokens,
            reasoning=False,
        )

    def _anthropic_config(self) -> ProviderConfig:
        return ProviderConfig(
            key="anthropic",
            label="Anthropic Claude",
            model=self.settings.anthropic_model,
            base_url=self.settings.anthropic_base_url,
            api_key_env="ANTHROPIC_API_KEY",
            context_window=200000,
            max_tokens=self.settings.pi_agent_max_tokens,
            reasoning=True,
        )

    def get(self, name: str | None = None) -> ProviderConfig:
        selected = name or self.settings.llm_provider
        if selected == "ollama":
            return self._ollama_config()
        if selected == "anthropic":
            return self._anthropic_config()
        raise ProviderUnavailableError(f"Unknown provider '{selected}'")

    def availability(self, key: str) -> tuple[bool, str | None]:
        if self.settings.pi_agent_backend == "in_process":
            return True, "Pi in_process deterministic backend"
        if key == "ollama":
            try:
                response = requests.get(f"{self.settings.ollama_base_url.rstrip('/')}/api/tags", timeout=5)
                if response.status_code == 200:
                    return True, None
                return False, f"Unexpected Ollama status {response.status_code}"
            except requests.RequestException as exc:
                return False, str(exc)
        if key == "anthropic":
            if not self.settings.anthropic_api_key:
                return False, "ANTHROPIC_API_KEY not configured"
            return True, None
        return False, "Unknown provider"

    def resolve(self, preferred: str | None = None) -> tuple[ProviderConfig, str | None]:
        selected = preferred or self.settings.llm_provider
        available, reason = self.availability(selected)
        if available:
            return self.get(selected), None
        fallback = "anthropic" if selected == "ollama" else "ollama"
        fallback_available, fallback_reason = self.availability(fallback)
        if fallback_available:
            return self.get(fallback), (
                f"Preferred provider '{selected}' unavailable: {reason}. Fell back to '{fallback}'."
            )
        raise ProviderUnavailableError(reason or fallback_reason or "No providers available")

    def describe(self) -> list[dict[str, str | bool | None]]:
        selected = self.settings.llm_provider
        items: list[dict[str, str | bool | None]] = []
        for key in ("ollama", "anthropic"):
            config = self.get(key)
            available, reason = self.availability(key)
            items.append(
                {
                    "key": key,
                    "label": config.label,
                    "selected": key == selected,
                    "available": available,
                    "model": config.model,
                    "reason": reason,
                }
            )
        return items
