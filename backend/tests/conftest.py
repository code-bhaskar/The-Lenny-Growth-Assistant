from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch, tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'app.db'}")
    monkeypatch.setenv("TRANSCRIPT_CACHE_DIR", str(tmp_path / 'missing-transcripts'))
    monkeypatch.setenv("TRANSCRIPT_FIXTURE_DIR", str(repo_root / 'data' / 'samples'))
    monkeypatch.setenv("INGEST_ON_STARTUP", "true")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:3000")
    monkeypatch.setenv("PI_AGENT_BACKEND", "in_process")

    from app.core.config import get_settings
    from app.db import session as db_session

    get_settings.cache_clear()
    db_session._engine = None
    db_session._SessionLocal = None

    import app.main as main_module

    importlib.reload(main_module)

    with TestClient(main_module.app) as test_client:
        yield test_client
