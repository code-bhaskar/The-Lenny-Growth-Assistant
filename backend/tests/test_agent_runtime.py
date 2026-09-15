from __future__ import annotations

import re

from app.agent.pi_agent import AgentResult, PiAgentService
from app.agent.providers import ProviderConfig, ProviderRegistry


def test_ship30_fallback_builder_respects_word_range(monkeypatch):
    monkeypatch.setenv("ENV", "test")
    from app.core.config import get_settings

    get_settings.cache_clear()
    service = PiAgentService()
    retrieval_context = """
[S1] Building product taste at Airbnb
Guest: Brian Chesky
Publish date: 2024-01-10
Source path: episodes/brian-chesky/transcript.md
Source URL: https://youtube.com/watch?v=demo-brian-chesky
Transcript excerpt:
Clarity beats feature sprawl and product taste compounds into trust.

[S2] Growth loops and retention systems
Guest: Andrew Chen
Publish date: 2023-11-21
Source path: episodes/andrew-chen/transcript.md
Source URL: https://youtube.com/watch?v=demo-andrew-chen
Transcript excerpt:
Retention is the scoreboard for growth quality and product-native distribution compounds.

[S3] Finding product-market fit signals
Guest: Lenny Rachitsky
Publish date: 2024-05-02
Source path: episodes/lenny-rachitsky/transcript.md
Source URL: https://youtube.com/watch?v=demo-lenny-pmf
Transcript excerpt:
Product-market fit appears first in a narrow segment that would be very disappointed if the product disappeared.
""".strip()
    essay = service._build_ship30_fallback_markdown(
        "Write a Ship 30 style essay about product-market fit and retention.",
        retrieval_context,
    )
    words = len(re.findall(r"\b\w+\b", essay))
    assert service.settings.ship30_min_words <= words <= service.settings.ship30_max_words


def test_generate_falls_back_to_in_process_backend(monkeypatch):
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("PI_AGENT_BACKEND", "node")
    monkeypatch.setenv("PI_AGENT_ENABLE_BACKEND_FALLBACK", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()

    def fake_resolve(self, preferred=None):
        return (
            ProviderConfig(
                key="ollama",
                label="Ollama",
                model="qwen2.5:3b",
                base_url="http://localhost:11434/v1",
                api_key="ollama",
            ),
            None,
        )

    async def fake_generate_async(self, *, provider, backend, conversation, retrieval_context, user_request, force_artifact_type):
        if backend == "node":
            raise RuntimeError("node bridge failed")
        return AgentResult(
            route="qa",
            answer="Recovered on in_process backend.",
            artifact=None,
            provider=provider.key,
            model=provider.model,
            runtime_backend=backend,
        )

    monkeypatch.setattr(ProviderRegistry, "resolve", fake_resolve)
    monkeypatch.setattr(PiAgentService, "_generate_async", fake_generate_async)

    service = PiAgentService()
    result, fallback_note = service.generate(
        conversation="USER: hi",
        retrieval_context="[S1] Example\nTranscript excerpt:\nRetention matters.",
        user_request="What matters?",
        provider_name="ollama",
    )
    assert fallback_note is None
    assert result.answer == "Recovered on in_process backend."
    assert result.runtime_backend == "in_process"
