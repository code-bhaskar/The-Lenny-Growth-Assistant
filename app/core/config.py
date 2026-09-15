from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
ARTIFACT_DIR = BASE_DIR / "artifacts"
LOG_DIR = BASE_DIR / "logs"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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
    ollama_embedding_model: str = "nomic-embed-text"

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-sonnet-latest"

    enable_claude_agent_sdk: bool = False
    claude_agent_sdk_model: str = "claude-sonnet-4-5"

    ingest_on_startup: bool = False
    transcript_repo_url: str = (
        "https://codeload.github.com/ChatPRD/lennys-podcast-transcripts/zip/refs/heads/main"
    )
    transcript_cache_dir: Path = RAW_DATA_DIR / "lennys-podcast-transcripts"
    transcript_fixture_dir: Path = DATA_DIR / "samples"
    processed_index_path: Path = PROCESSED_DATA_DIR / "tfidf_index.joblib"
    processed_manifest_path: Path = PROCESSED_DATA_DIR / "chunks.json"
    max_chunks_per_answer: int = 6
    retrieval_score_threshold: float = 0.08
    retrieval_chunk_size: int = 1800
    retrieval_chunk_overlap: int = 250

    frontend_origin: str = "http://localhost:8000"
    artifact_max_chars: int = 40000

    default_user_name: str = "Evaluator"
    request_timeout_seconds: int = 180

    def ensure_directories(self) -> None:
        for directory in [DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, ARTIFACT_DIR, LOG_DIR]:
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
