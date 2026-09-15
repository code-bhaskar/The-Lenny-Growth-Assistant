from __future__ import annotations

from contextlib import asynccontextmanager

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.errors import AppError, app_error_handler, unhandled_error_handler
from app.api.routes import router
from app.core.config import BASE_DIR, get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import init_db
from app.services.knowledge import TranscriptIngestionService

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging(settings.log_level)
    init_db()
    if settings.ollama_auto_pull and settings.llm_provider == "ollama":
        try:
            requests.post(
                f"{settings.ollama_base_url}/api/pull",
                json={"name": settings.ollama_model, "stream": False},
                timeout=600,
            )
        except Exception as exc:  # pragma: no cover - startup safeguard
            logger.warning("ollama_auto_pull_failed", extra={"error": str(exc)})
    if settings.ingest_on_startup:
        try:
            TranscriptIngestionService().build_index()
        except Exception as exc:  # pragma: no cover - startup safeguard
            logger.warning("startup_ingestion_failed", extra={"error": str(exc)})
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
