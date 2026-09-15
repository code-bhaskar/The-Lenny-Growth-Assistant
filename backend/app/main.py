from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

import requests
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.errors import AppError, app_error_handler, unhandled_error_handler
from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger, info, warning
from app.db.session import init_db, get_session_factory
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
                f"{settings.ollama_base_url.rstrip('/')}/api/pull",
                json={"name": settings.ollama_model, "stream": False},
                timeout=600,
            )
        except Exception as exc:  # pragma: no cover
            warning(logger, "ollama_auto_pull_failed", error=str(exc))
    if settings.ingest_on_startup:
        db = get_session_factory()()
        try:
            TranscriptIngestionService().ingest(db)
        except Exception as exc:  # pragma: no cover
            warning(logger, "startup_ingestion_failed", error=str(exc))
            db.rollback()
        finally:
            db.close()
    yield


app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    info(
        logger,
        "request_completed",
        request_id=request_id,
        endpoint=request.url.path,
        method=request.method,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response


@app.get("/")
def root() -> JSONResponse:
    return JSONResponse({"name": settings.app_name, "docs": "/docs", "health": "/health"})


app.include_router(router)
