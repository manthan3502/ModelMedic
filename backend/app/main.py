import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from backend.app.api.diagnostics import diagnostics_router
from backend.app.api.monitoring import monitoring_router
from backend.app.api.projects import project_router
from backend.app.core.config import Settings
from backend.app.core.frontend import is_frontend_read, mount_frontend
from backend.app.core.logging import configure_logging
from backend.app.db.models import Job, WorkerStatus
from backend.app.db.session import check_schema, create_db
from backend.app.schemas.jobs import JobResponse
from backend.app.services.demo import (
    DEMO_MESSAGE,
    PUBLIC_READS,
    authorize_read,
    registry,
    validate_seed_scope,
)
from backend.app.storage.factory import artifact_store


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()  # type: ignore[call-arg]
    engine, sessions = create_db(settings)
    configure_logging()
    logger = logging.getLogger("modelmedic")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    store = artifact_store(settings)
    app = FastAPI(
        title="ModelMedic",
        version="0.0.0",
        lifespan=lifespan,
        docs_url=None if settings.environment == "deployment" else "/docs",
        redoc_url=None if settings.environment == "deployment" else "/redoc",
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
    app.include_router(project_router(sessions, store, settings))
    app.include_router(monitoring_router(sessions, store, settings))

    def error(request: Request, status: int, code: str, message: str) -> JSONResponse:
        return JSONResponse(
            status_code=status,
            content={
                "code": code,
                "message": message,
                "details": [],
                "request_id": request.state.request_id,
            },
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.request_id = str(uuid4())
        if settings.deployment_mode == "demo" and request.method != "GET":
            response: Response = error(request, 403, "READ_ONLY_DEMO", DEMO_MESSAGE)
        else:
            try:
                if settings.deployment_mode == "demo" and not is_frontend_read(
                    request.url.path, settings.frontend_root
                ):
                    authorize_read(request.url.path, store)
                    if request.url.path.rstrip("/") not in PUBLIC_READS:
                        with sessions() as session:
                            validate_seed_scope(session, registry(store))
                response = await call_next(request)
            except HTTPException as exc:
                response = error(request, exc.status_code, "DEMO_READ_DENIED", str(exc.detail))
            except Exception:
                logger.error("request_failed", extra={"request_id": request.state.request_id})
                response = error(
                    request, 500, "INTERNAL_ERROR", "The request could not be completed."
                )
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        logger.info("request_completed", extra={"request_id": request.state.request_id})
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return error(request, exc.status_code, "REQUEST_ERROR", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error(request, 422, "INVALID_REQUEST", "Check the request format and identifiers.")

    app.include_router(diagnostics_router(sessions, settings))

    @app.get("/api/v1/runtime")
    def runtime() -> dict[str, Any]:
        return {
            "deployment_mode": "DEMO_MODE" if settings.deployment_mode == "demo" else "FULL_MODE",
            "read_only": settings.deployment_mode == "demo",
            "mutation_explanation": DEMO_MESSAGE,
        }

    @app.get("/api/v1/health/live")
    def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/api/v1/health/ready")
    def ready() -> dict[str, str]:
        try:
            check_schema(engine)
            if settings.deployment_mode == "demo":
                with sessions() as session:
                    validate_seed_scope(session, registry(store))
        except (SQLAlchemyError, RuntimeError):
            raise HTTPException(503, "Database or schema is not ready.") from None
        return {"status": "ready", "database": "reachable", "schema": "compatible"}

    @app.get("/api/v1/health/worker")
    def worker_status() -> dict[str, Any]:
        if settings.deployment_mode == "demo":
            return {"recent": False, "status": "NOT_REQUIRED", "heartbeat_at": None}
        with sessions() as session:
            worker = session.scalar(select(WorkerStatus).order_by(WorkerStatus.heartbeat_at.desc()))
            now = session.scalar(select(func.now()))
            recent = (
                worker is not None
                and now is not None
                and (now - worker.heartbeat_at).total_seconds() < settings.lease_seconds
            )
            return {
                "recent": recent,
                "status": worker.status if worker else "UNAVAILABLE",
                "heartbeat_at": worker.heartbeat_at.isoformat() if worker else None,
            }

    @app.get("/api/v1/jobs/{job_id}", response_model=JobResponse)
    def get_job(job_id: UUID) -> JobResponse:
        with sessions() as session:
            job = session.get(Job, job_id)
            if job is None:
                raise HTTPException(404, "Job not found.")
            return JobResponse.model_validate(job)

    if settings.frontend_root:
        mount_frontend(app, settings.frontend_root)
    return app
