from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.api.errors import ProviderUnavailableError
from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.agent.claude_sdk_adapter import ClaudeAgentSdkAdapter

logger = get_logger(__name__)


@dataclass
class CompletionResult:
    text: str
    provider: str
    model: str


class LLMProvider(Protocol):
    key: str
    label: str

    def is_available(self) -> tuple[bool, str | None]: ...

    def generate(self, *, system: str, prompt: str) -> CompletionResult: ...


class OllamaProvider:
    key = "ollama"
    label = "Ollama (local)"

    def __init__(self) -> None:
        self.settings = get_settings()

    def is_available(self) -> tuple[bool, str | None]:
        try:
            response = requests.get(f"{self.settings.ollama_base_url}/api/tags", timeout=5)
            if response.status_code != 200:
                return False, f"Unexpected Ollama status {response.status_code}"
            return True, None
        except requests.RequestException as exc:
            return False, str(exc)

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def generate(self, *, system: str, prompt: str) -> CompletionResult:
        available, reason = self.is_available()
        if not available:
            raise ProviderUnavailableError(
                f"Ollama is unavailable at {self.settings.ollama_base_url}. {reason or ''}".strip()
            )

        payload = {
            "model": self.settings.ollama_model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": 0.2},
        }
        response = requests.post(
            f"{self.settings.ollama_base_url}/api/generate",
            json=payload,
            timeout=self.settings.ollama_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        return CompletionResult(
            text=(data.get("response") or "").strip(),
            provider=self.key,
            model=self.settings.ollama_model,
        )


class AnthropicProvider:
    key = "anthropic"
    label = "Anthropic Claude"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.sdk_adapter = ClaudeAgentSdkAdapter()

    def is_available(self) -> tuple[bool, str | None]:
        if self.settings.enable_claude_agent_sdk:
            return self.sdk_adapter.is_available()
        if not self.settings.anthropic_api_key:
            return False, "ANTHROPIC_API_KEY not configured"
        return True, None

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def generate(self, *, system: str, prompt: str) -> CompletionResult:
        available, reason = self.is_available()
        if not available:
            raise ProviderUnavailableError(reason or "Anthropic provider unavailable")

        if self.settings.enable_claude_agent_sdk:
            sdk_result = self.sdk_adapter.generate(system=system, prompt=prompt)
            return CompletionResult(
                text=sdk_result.text,
                provider=self.key,
                model=self.settings.claude_agent_sdk_model,
            )

        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.settings.anthropic_api_key or "",
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.settings.anthropic_model,
                "max_tokens": 1600,
                "temperature": 0.2,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=self.settings.request_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        text_parts = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        return CompletionResult(
            text="\n".join(text_parts).strip(),
            provider=self.key,
            model=self.settings.anthropic_model,
        )


class ProviderRegistry:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.providers = {
            "ollama": OllamaProvider(),
            "anthropic": AnthropicProvider(),
        }

    def get(self, provider_name: str | None) -> LLMProvider:
        selected = provider_name or self.settings.llm_provider
        provider = self.providers.get(selected)
        if not provider:
            raise ProviderUnavailableError(f"Unknown provider '{selected}'")
        return provider

    def resolve(self, provider_name: str | None) -> tuple[LLMProvider, str | None]:
        preferred = provider_name or self.settings.llm_provider
        provider = self.get(preferred)
        available, reason = provider.is_available()
        if available:
            return provider, None

        for fallback_key, fallback_provider in self.providers.items():
            if fallback_key == preferred:
                continue
            fallback_available, fallback_reason = fallback_provider.is_available()
            if fallback_available:
                return fallback_provider, f"Preferred provider '{preferred}' unavailable: {reason}. Fell back to '{fallback_key}'."

        combined_reason = reason or "No providers available"
        raise ProviderUnavailableError(combined_reason)

    def describe(self) -> list[dict[str, str | bool | None]]:
        selected = self.settings.llm_provider
        description = []
        for key, provider in self.providers.items():
            available, reason = provider.is_available()
            model = None
            if key == "ollama":
                model = self.settings.ollama_model
            elif key == "anthropic":
                model = self.settings.anthropic_model
            description.append(
                {
                    "key": key,
                    "label": provider.label,
                    "selected": key == selected,
                    "available": available,
                    "reason": reason,
                    "model": model,
                }
            )
        return description
