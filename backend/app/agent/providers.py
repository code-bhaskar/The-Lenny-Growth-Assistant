from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

from app.api.errors import ProviderUnavailableError
from app.core.config import get_settings
from app.core.logging import get_logger, info, warning

logger = get_logger(__name__)


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
            return self._ollama_availability()
        if key == "anthropic":
            if not self.settings.anthropic_api_key:
                return False, "ANTHROPIC_API_KEY not configured"
            return True, None
        return False, "Unknown provider"

    def ensure_ollama_ready(self) -> tuple[bool, str | None]:
        if self.settings.pi_agent_backend == "in_process":
            return True, "Pi in_process deterministic backend"

        available, reason = self._ollama_availability()
        if available:
            return True, reason

        if "model" in (reason or "").lower() and self.settings.ollama_auto_pull:
            pull_ok, pull_reason = self._pull_ollama_model()
            if pull_ok:
                return self._ollama_availability()
            return False, pull_reason

        return False, reason

    def resolve(self, preferred: str | None = None) -> tuple[ProviderConfig, str | None]:
        selected = preferred or self.settings.llm_provider
        if selected == "ollama":
            available, reason = self.ensure_ollama_ready()
        else:
            available, reason = self.availability(selected)
        if available:
            return self.get(selected), None

        fallback = "anthropic" if selected == "ollama" else "ollama"
        if fallback == "ollama":
            fallback_available, fallback_reason = self.ensure_ollama_ready()
        else:
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
            available, reason = (
                self.ensure_ollama_ready() if key == "ollama" else self.availability(key)
            )
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

    def _ollama_availability(self) -> tuple[bool, str | None]:
        try:
            response = requests.get(
                f"{self.settings.ollama_base_url.rstrip('/')}/api/tags",
                timeout=self.settings.ollama_health_timeout_seconds,
            )
            if response.status_code != 200:
                return False, f"Unexpected Ollama status {response.status_code}"
            tags = response.json().get("models", [])
            model_names = {item.get("name") for item in tags if item.get("name")}
            if self.settings.ollama_model not in model_names:
                return False, f"Configured Ollama model '{self.settings.ollama_model}' is not pulled"
            return True, None
        except requests.RequestException as exc:
            return False, str(exc)

    def _pull_ollama_model(self) -> tuple[bool, str | None]:
        last_reason: str | None = None
        for attempt in range(1, self.settings.ollama_startup_retries + 1):
            try:
                info(
                    logger,
                    "ollama_model_pull_attempt",
                    attempt=attempt,
                    model=self.settings.ollama_model,
                )
                response = requests.post(
                    f"{self.settings.ollama_base_url.rstrip('/')}/api/pull",
                    json={"name": self.settings.ollama_model, "stream": False},
                    timeout=max(self.settings.ollama_timeout_seconds, 60),
                )
                if response.status_code == 200:
                    return True, None
                last_reason = f"pull failed with status {response.status_code}"
            except requests.RequestException as exc:
                last_reason = str(exc)
            if attempt < self.settings.ollama_startup_retries:
                time.sleep(self.settings.ollama_startup_backoff_seconds)
        warning(logger, "ollama_model_pull_failed", model=self.settings.ollama_model, reason=last_reason)
        return False, last_reason
