"""
Shared error handling.

Two surfaces, one vocabulary:
- HTTP endpoints get a consistent JSON envelope via app-level exception
  handlers (registered in main.create_app).
- The WebSocket service can't use those handlers — Starlette doesn't run
  exception handlers for WS routes — so it catches these same AppError types
  itself and emits its {"type": "error"} protocol frame. Same exceptions,
  different transport.
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


class AppError(Exception):
    """Base for expected, domain-level errors. Carries an HTTP status and a
    client-safe message (never leak internals through this)."""
    status_code = 500
    error_type = "internal_error"

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404
    error_type = "not_found"


class ValidationError(AppError):
    status_code = 400
    error_type = "validation_error"


def error_body(error_type: str, message: str) -> dict:
    """The single error shape every surface returns."""
    return {"error": {"type": error_type, "message": message}}


def register_exception_handlers(app: FastAPI) -> None:
    """Wire consistent error responses onto all HTTP routes (including those
    from included routers)."""

    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.error_type, exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_request_validation(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=error_body("validation_error", "Invalid request payload"),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception):
        # Anything unplanned: log the detail server-side, return a generic body.
        print(f"[ERROR] Unhandled exception on {request.url.path}: {exc!r}")
        return JSONResponse(
            status_code=500,
            content=error_body("internal_error", "An unexpected error occurred"),
        )