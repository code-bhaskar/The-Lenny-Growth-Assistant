from __future__ import annotations

import argparse
import json
import re

import requests


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--frontend-base", default="http://127.0.0.1:3000")
    parser.add_argument("--provider", default="ollama")
    args = parser.parse_args()

    session = requests.Session()

    health = session.get(f"{args.api_base}/health", timeout=15)
    health.raise_for_status()
    print("health", health.json())

    frontend = session.get(args.frontend_base, timeout=15)
    frontend.raise_for_status()
    assert "The Lenny Growth Assistant" in frontend.text

    session_resp = session.post(
        f"{args.api_base}/api/sessions",
        json={"title": "Validation Session", "user_metadata": {"user_name": "Validator"}},
        timeout=15,
    )
    session_resp.raise_for_status()
    session_id = session_resp.json()["id"]
    print("session_id", session_id)

    message_resp = session.post(
        f"{args.api_base}/api/sessions/{session_id}/messages",
        json={
            "content": "What do the transcripts say about product-market fit and retention?",
            "provider": args.provider,
        },
        timeout=180,
    )
    message_resp.raise_for_status()
    message_payload = message_resp.json()
    assert message_payload["role"] == "assistant"
    assert message_payload["citations"], "expected grounded citations"
    print("message_ok", json.dumps(message_payload["metadata"], indent=2))

    artifact_resp = session.post(
        f"{args.api_base}/api/artifacts",
        json={
            "session_id": session_id,
            "instruction": "Write a Ship 30 style essay about product-market fit and retention as a markdown artifact.",
            "type": "markdown",
            "provider": args.provider,
        },
        timeout=180,
    )
    artifact_resp.raise_for_status()
    artifact = artifact_resp.json()
    assert artifact["type"] == "markdown"
    words = word_count(artifact["content"])
    assert 1100 <= words <= 1400, f"artifact word count out of range: {words}"
    print("artifact_word_count", words)

    fetch_artifact = session.get(f"{args.api_base}/api/artifacts/{artifact['id']}", timeout=15)
    fetch_artifact.raise_for_status()
    assert fetch_artifact.json()["id"] == artifact["id"]

    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
