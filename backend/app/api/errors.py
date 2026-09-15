from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 400
    error = "application_error"

    def __init__(self, detail: str, *, status_code: int | None = None, error: str | None = None):
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        if error is not None:
            self.error = error
        super().__init__(detail)


class NotFoundError(AppError):
    status_code = 404
    error = "not_found"


class ProviderUnavailableError(AppError):
    status_code = 503
    error = "provider_unavailable"


class ValidationAppError(AppError):
    status_code = 422
    error = "validation_error"


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error, "detail": exc.detail, "request_id": request_id},
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "detail": str(exc), "request_id": request_id},
    )
