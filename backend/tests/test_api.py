from __future__ import annotations

from app.agent.pi_agent import AgentResult, PiAgentService
from app.agent.providers import ProviderRegistry


def availability_ready(self, key: str):
    return True, None


def stub_generate(self, *, conversation, retrieval_context, user_request, provider_name=None, force_artifact_type=None):
    lowered = user_request.lower()
    if force_artifact_type == "html" or "html" in lowered:
        return (
            AgentResult(
                route="artifact",
                answer="Created a grounded HTML artifact.",
                artifact={
                    "title": "Grounded HTML Artifact",
                    "type": "html",
                    "content": "<html><body><h1>Growth loop review</h1><script>alert(1)</script><button onclick='evil()'>Click</button><p>Retention is the scoreboard.</p></body></html>",
                },
                provider="ollama",
                model="qwen2.5:3b",
            ),
            None,
        )
    if force_artifact_type == "markdown" or "ship 30" in lowered or "essay" in lowered:
        return (
            AgentResult(
                route="ship30" if "ship 30" in lowered or "essay" in lowered else "artifact",
                answer="Drafted a grounded long-form essay in the artifact pane.",
                artifact={
                    "title": "Grounded Ship 30 Essay",
                    "type": "markdown",
                    "content": "# Why clarity compounds\n\n**Hook.** Teams grow faster when they choose fewer, sharper bets.\n\n## What the guests agree on\n- Brian Chesky emphasizes clarity over feature sprawl.\n- Andrew Chen ties growth quality to retention.\n- Lenny focuses on a narrow PMF segment first.\n\n## Practical takeaway\nAudit onboarding around one core action.\n",
                },
                provider="ollama",
                model="qwen2.5:3b",
            ),
            None,
        )
    return (
        AgentResult(
            route="qa",
            answer="The transcripts point to a consistent pattern: focus on one core action, use retention as the quality bar, and tighten feedback loops between PM, design, and engineering.",
            artifact=None,
            provider="ollama",
            model="qwen2.5:3b",
        ),
        None,
    )


def create_session(client, title="New chat"):
    response = client.post(
        "/api/sessions",
        json={"title": title, "user_metadata": {"user_name": "Evaluator", "user_role": "PM"}},
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_health_endpoint(client, monkeypatch):
    monkeypatch.setattr(ProviderRegistry, "availability", availability_ready)

    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["database"] == "ready"
    assert payload["knowledge_base"] == "ready"
    assert payload["agent_layer"] == "ready"


def test_post_message_and_list_messages(client, monkeypatch):
    monkeypatch.setattr(ProviderRegistry, "availability", availability_ready)
    monkeypatch.setattr(PiAgentService, "generate", stub_generate)

    session_id = create_session(client, "Growth diagnostics")
    message_response = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "What do the transcripts say about product-market fit and retention?"},
    )
    assert message_response.status_code == 200
    payload = message_response.json()
    assert payload["role"] == "assistant"
    assert payload["metadata"]["route"] == "qa"
    assert len(payload["citations"]) >= 2

    messages_response = client.get(f"/api/sessions/{session_id}/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


def test_ship30_message_creates_markdown_artifact(client, monkeypatch):
    monkeypatch.setattr(ProviderRegistry, "availability", availability_ready)
    monkeypatch.setattr(PiAgentService, "generate", stub_generate)

    session_id = create_session(client)
    response = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "Write a Ship 30 style essay about growth loops and product clarity."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["route"] == "ship30"
    assert payload["artifacts"][0]["type"] == "markdown"
    assert "<h1>Why clarity compounds</h1>" in payload["artifacts"][0]["sanitized_content"]


def test_create_and_fetch_html_artifact(client, monkeypatch):
    monkeypatch.setattr(ProviderRegistry, "availability", availability_ready)
    monkeypatch.setattr(PiAgentService, "generate", stub_generate)

    session_id = create_session(client)
    artifact_response = client.post(
        "/api/artifacts",
        json={
            "session_id": session_id,
            "instruction": "Create an HTML/CSS artifact summarizing retention advice.",
            "type": "html",
        },
    )
    assert artifact_response.status_code == 200
    artifact = artifact_response.json()
    assert artifact["type"] == "html"
    assert "<script>" not in artifact["sanitized_content"]
    assert "onclick" not in artifact["sanitized_content"]

    fetch_response = client.get(f"/api/artifacts/{artifact['id']}")
    assert fetch_response.status_code == 200
    assert fetch_response.json()["id"] == artifact["id"]


def test_session_isolation(client, monkeypatch):
    monkeypatch.setattr(ProviderRegistry, "availability", availability_ready)
    monkeypatch.setattr(PiAgentService, "generate", stub_generate)

    first = create_session(client, "Session A")
    second = create_session(client, "Session B")

    client.post(f"/api/sessions/{first}/messages", json={"content": "What do the transcripts say about PMF?"})
    client.post(f"/api/sessions/{second}/messages", json={"content": "What do the transcripts say about growth loops?"})

    first_messages = client.get(f"/api/sessions/{first}/messages").json()
    second_messages = client.get(f"/api/sessions/{second}/messages").json()
    assert len(first_messages) == 2
    assert len(second_messages) == 2
    assert first_messages[0]["content"] != second_messages[0]["content"]


def test_weak_retrieval_refuses_to_hallucinate(client, monkeypatch):
    monkeypatch.setattr(ProviderRegistry, "availability", availability_ready)
    monkeypatch.setattr(PiAgentService, "generate", stub_generate)

    session_id = create_session(client)
    response = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "What do the transcripts say about black holes near Andromeda?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["retrieval_summary"]["status"] in {"empty", "weak_match"}
    assert "couldn't find enough grounded transcript evidence" in payload["content"].lower()
