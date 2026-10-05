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
from starlette.responses import Response

from backend.app.api.diagnostics import diagnostics_router
from backend.app.api.monitoring import monitoring_router
from backend.app.api.projects import project_router
from backend.app.core.config import Settings
from backend.app.core.logging import configure_logging
from backend.app.db.models import Job, WorkerStatus
from backend.app.db.session import check_schema, create_db
from backend.app.schemas.jobs import JobResponse
from backend.app.storage.local import LocalArtifactStore


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()  # type: ignore[call-arg]
    engine, sessions = create_db(settings)
    configure_logging()
    logger = logging.getLogger("modelmedic")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    app = FastAPI(title="ModelMedic", version="0.0.0", lifespan=lifespan)
    app.include_router(
        project_router(sessions, LocalArtifactStore(settings.artifact_root), settings)
    )
    app.include_router(
        monitoring_router(sessions, LocalArtifactStore(settings.artifact_root), settings)
    )

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
            response: Response = error(request, 403, "READ_ONLY_DEMO", "This demo is read-only.")
        else:
            try:
                response = await call_next(request)
            except Exception:
                logger.error("request_failed", extra={"request_id": request.state.request_id})
                response = error(
                    request, 500, "INTERNAL_ERROR", "The request could not be completed."
                )
        response.headers["X-Request-ID"] = request.state.request_id
        logger.info("request_completed", extra={"request_id": request.state.request_id})
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return error(request, exc.status_code, "REQUEST_ERROR", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error(request, 422, "INVALID_REQUEST", "Check the request format and identifiers.")

    app.include_router(diagnostics_router(sessions, settings))

    @app.get("/api/v1/health/live")
    def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/api/v1/health/ready")
    def ready() -> dict[str, str]:
        try:
            check_schema(engine)
        except (SQLAlchemyError, RuntimeError):
            raise HTTPException(503, "Database or schema is not ready.") from None
        return {"status": "ready", "database": "reachable", "schema": "compatible"}

    @app.get("/api/v1/health/worker")
    def worker_status() -> dict[str, Any]:
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

    return app
