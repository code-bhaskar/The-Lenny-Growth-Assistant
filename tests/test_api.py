from __future__ import annotations

from types import SimpleNamespace

from app.services.agent.providers import CompletionResult, OllamaProvider, ProviderRegistry


def stub_generate(self, *, system: str, prompt: str):
    lowered = prompt.lower()
    if "artifact type=\"markdown\"" in lowered or "ship 30" in lowered or "essay" in lowered:
        return CompletionResult(
            text=(
                "<answer>Drafted a grounded essay using retrieved episodes.</answer>"
                "<artifact type=\"markdown\" title=\"Grounded Ship 30 Essay\">\n"
                "# Why clarity compounds\n\n"
                "**Hook.** Teams grow faster when they choose fewer, sharper bets.\n\n"
                "## What the guests agree on\n"
                "- Brian Chesky emphasizes clarity over feature sprawl.\n"
                "- Andrew Chen ties growth quality to retention.\n"
                "- Lenny focuses on a narrow PMF segment first.\n\n"
                "## Practical takeaway\n"
                "Audit your onboarding around one core action and remove anything that delays it.\n\n"
                "## Sources\n"
                "- Building product taste at Airbnb [S1]\n"
                "- Growth loops and retention systems [S2]\n"
                "- Finding product-market fit signals [S3]\n"
                "</artifact>"
            ),
            provider="ollama",
            model="stub-ollama",
        )
    if "generate a html artifact" in lowered or 'type="html"' in lowered:
        return CompletionResult(
            text=(
                "<answer>Created a sandboxed HTML artifact.</answer>"
                "<artifact type=\"html\" title=\"Grounded HTML Artifact\">\n"
                "<html><body><h1>Growth loop review</h1><script>alert(1)</script>"
                "<button onclick=\"evil()\">Click</button><p>Retention is the scoreboard.</p></body></html>"
                "</artifact>"
            ),
            provider="ollama",
            model="stub-ollama",
        )
    return CompletionResult(
        text=(
            "The transcripts suggest a pattern: focus on one core action, keep retention as the quality gate, "
            "and tighten the feedback loop between PM, design, and engineering. [S1] [S2] [S3]"
        ),
        provider="ollama",
        model="stub-ollama",
    )


def stub_available(self):
    return True, None


def test_health_endpoint(client, monkeypatch):
    monkeypatch.setattr(OllamaProvider, "is_available", stub_available)

    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["database"] == "ready"
    assert payload["knowledge_base"] == "ready"
    assert payload["llm_provider"] == "ready"


def test_create_session_and_grounded_chat(client, monkeypatch):
    monkeypatch.setattr(OllamaProvider, "is_available", stub_available)
    monkeypatch.setattr(OllamaProvider, "generate", stub_generate)

    session_response = client.post(
        "/api/sessions",
        json={"title": "Growth diagnostics", "user": {"user_name": "Ava", "user_role": "PMM"}},
    )
    assert session_response.status_code == 200
    session_id = session_response.json()["id"]

    chat_response = client.post(
        "/api/chat",
        json={
            "session_id": session_id,
            "content": "What do the transcripts say about finding product-market fit and retention?",
        },
    )
    assert chat_response.status_code == 200
    payload = chat_response.json()
    assert payload["provider"] == "ollama"
    assert payload["message"]["role"] == "assistant"
    assert len(payload["message"]["citations"]) >= 2
    assert payload["retrieval_summary"]["status"] == "grounded"

    session_detail = client.get(f"/api/sessions/{session_id}")
    assert session_detail.status_code == 200
    messages = session_detail.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


def test_ship30_request_returns_markdown_artifact(client, monkeypatch):
    monkeypatch.setattr(OllamaProvider, "is_available", stub_available)
    monkeypatch.setattr(OllamaProvider, "generate", stub_generate)

    session_id = client.post("/api/sessions", json={"user": {"user_name": "Evaluator"}}).json()["id"]
    response = client.post(
        "/api/chat",
        json={
            "session_id": session_id,
            "content": "Write a Ship 30 style essay about what Lenny's guests say on growth loops and product clarity.",
        },
    )
    assert response.status_code == 200
    message = response.json()["message"]
    assert message["artifact"]["artifact_type"] == "markdown"
    assert "Why clarity compounds" in message["artifact"]["raw_content"]
    assert "<h1>Why clarity compounds</h1>" in message["artifact"]["sanitized_content"]


def test_html_artifact_is_sanitized(client, monkeypatch):
    monkeypatch.setattr(OllamaProvider, "is_available", stub_available)
    monkeypatch.setattr(OllamaProvider, "generate", stub_generate)

    session_id = client.post("/api/sessions", json={"user": {"user_name": "Evaluator"}}).json()["id"]
    response = client.post(
        "/api/chat",
        json={
            "session_id": session_id,
            "content": "Create an HTML/CSS artifact that summarizes retention advice.",
        },
    )
    assert response.status_code == 200
    artifact = response.json()["message"]["artifact"]
    assert artifact["artifact_type"] == "html"
    assert "<script>" not in artifact["sanitized_content"]
    assert "onclick" not in artifact["sanitized_content"]
    assert "Content-Security-Policy" in artifact["sanitized_content"]


def test_provider_fallback_when_anthropic_unavailable(client, monkeypatch):
    monkeypatch.setattr(OllamaProvider, "is_available", stub_available)
    monkeypatch.setattr(OllamaProvider, "generate", stub_generate)

    def fake_resolve(self, provider_name):
        return self.providers["ollama"], "Preferred provider 'anthropic' unavailable: missing key. Fell back to 'ollama'."

    monkeypatch.setattr(ProviderRegistry, "resolve", fake_resolve)

    session_id = client.post("/api/sessions", json={"user": {"user_name": "Evaluator"}}).json()["id"]
    response = client.post(
        "/api/chat",
        json={
            "session_id": session_id,
            "provider": "anthropic",
            "content": "What do the transcripts suggest about growth loops?",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "ollama"
    assert "Fell back to 'ollama'" in payload["message"]["content"]


def test_weak_retrieval_refuses_to_hallucinate(client, monkeypatch):
    monkeypatch.setattr(OllamaProvider, "is_available", stub_available)
    monkeypatch.setattr(OllamaProvider, "generate", stub_generate)

    session_id = client.post("/api/sessions", json={"user": {"user_name": "Evaluator"}}).json()["id"]
    response = client.post(
        "/api/chat",
        json={"session_id": session_id, "content": "What do the transcripts say about black holes near Andromeda?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval_summary"]["status"] in {"empty", "weak_match"}
    assert "couldn't find enough grounded evidence" in payload["message"]["content"].lower()
