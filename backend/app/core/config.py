from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
DATA_DIR = REPO_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
ARTIFACT_DIR = REPO_ROOT / "artifacts"
LOG_DIR = REPO_ROOT / "logs"
SKILLS_DIR = REPO_ROOT / "skills"
INGESTION_DIR = REPO_ROOT / "ingestion"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "The Lenny Growth Assistant"
    env: Literal["development", "test", "production"] = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@db:5432/lenny_growth"
    )
    allow_sqlite_for_tests: bool = True

    llm_provider: Literal["ollama", "anthropic"] = "ollama"
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:3b"
    ollama_timeout_seconds: int = 120
    ollama_auto_pull: bool = False
    ollama_context_window: int = 32768

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-sonnet-latest"
    anthropic_base_url: str = "https://api.anthropic.com"

    pi_agent_backend: Literal["node", "in_process"] = "node"
    pi_agent_thinking_level: str = "medium"
    pi_agent_temperature: float = 0.2
    pi_agent_max_tokens: int = 4000

    ingest_on_startup: bool = False
    transcript_repo_url: str = (
        "https://codeload.github.com/ChatPRD/lennys-podcast-transcripts/zip/refs/heads/main"
    )
    transcript_cache_dir: Path = RAW_DATA_DIR / "lennys-podcast-transcripts"
    transcript_fixture_dir: Path = DATA_DIR / "samples"
    max_chunks_per_answer: int = 6
    retrieval_score_threshold: float = 0.08
    retrieval_chunk_size: int = 1800
    retrieval_chunk_overlap: int = 250

    frontend_origin: str = "http://localhost:3000"
    artifact_max_chars: int = 40000
    default_user_name: str = "Evaluator"
    request_timeout_seconds: int = 180

    def ensure_directories(self) -> None:
        for directory in [DATA_DIR, RAW_DATA_DIR, ARTIFACT_DIR, LOG_DIR, SKILLS_DIR, INGESTION_DIR]:
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
