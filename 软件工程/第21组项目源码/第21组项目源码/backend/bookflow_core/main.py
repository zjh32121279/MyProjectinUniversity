from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from bookflow_core.api import routers
from bookflow_core.ai.kernel.worker import start_ai_kernel_worker, stop_ai_kernel_worker
from bookflow_core.core.config import project_root
from bookflow_core.core.database import ensure_schema
from bookflow_core.core.exceptions import BookFlowError
from bookflow_core.services.overdue_scheduler import start_overdue_scheduler, stop_overdue_scheduler


def _status_for_error(code: str) -> int:
    if code in {"AUTH_INVALID_CREDENTIALS", "AUTH_INVALID_TOKEN", "AUTH_TOKEN_EXPIRED", "ADMIN_INACTIVE", "READER_AUTH_FAILED", "READER_AUTH_REQUIRED"}:
        return 401
    if code in {"AI_ENGINE_UNAVAILABLE", "SERVICE_UNAVAILABLE", "READER_REGISTER_UNAVAILABLE", "VERIFICATION_CODE_UNAVAILABLE", "RESET_PASSWORD_UNAVAILABLE", "READER_AI_UNAVAILABLE", "NOTIFICATION_SETTINGS_UNAVAILABLE"}:
        return 503
    if code in {"AUTH_FORBIDDEN", "READER_FORBIDDEN", "AI_PERMISSION_DENIED", "AI_FORBIDDEN_OPERATION", "AI_REQUIRES_SUPER_AUTHORIZATION", "BORROW_RENEW_NOT_ALLOWED", "RESERVATION_CANCEL_NOT_ALLOWED"}:
        return 403
    if code in {"BOOK_NOT_FOUND", "COPY_NOT_FOUND", "READER_NOT_FOUND", "RESERVATION_NOT_FOUND", "RULE_NOT_FOUND", "AI_TOOL_NOT_FOUND", "AI_RUN_NOT_FOUND", "SNAPSHOT_NOT_FOUND", "RESOURCE_NOT_FOUND", "NOTIFICATION_NOT_FOUND"}:
        return 404
    return 400


def create_app() -> FastAPI:
    ensure_schema()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        start_overdue_scheduler()
        start_ai_kernel_worker()
        try:
            yield
        finally:
            stop_ai_kernel_worker()
            stop_overdue_scheduler()

    app = FastAPI(title="BookFlow Core", version="1.0.0", lifespan=lifespan)
    uploads_dir = project_root() / "data" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|\[::1\]):\d+$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for router in routers:
        app.include_router(router)

    @app.exception_handler(BookFlowError)
    async def bookflow_error_handler(request: Request, exc: BookFlowError):
        return JSONResponse(
            status_code=_status_for_error(exc.code),
            content={
                "success": False,
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "error": {"code": exc.code, "message": exc.message, "details": exc.details},
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Request validation failed.", "details": {"errors": exc.errors()}}})

    return app

app = create_app()
