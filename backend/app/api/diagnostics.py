from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import Settings
from backend.app.db.models import Job, MonitoringRun, RunReport, SliceAnalysis
from backend.app.science.monitoring import MODE_A_LIMITATION
from backend.app.science.slices import SLICE_LIMITATION, SLICE_METHODOLOGY_VERSION
from backend.app.services.monitoring import get_run
from backend.app.services.projects import get_project
from backend.app.services.report_store import save_report
from backend.app.services.slices import eligible_features, slice_view
from backend.app.services.trends import project_trends


class SliceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feature_id: str = Field(pattern=r"^f[0-9]{3}$")


def saved_run(session: Session, run_id: UUID, lock: bool = False) -> MonitoringRun:
    run = get_run(session, run_id, lock)
    if run.state != "ANALYZED" or not run.results or run.deletion_pending:
        raise HTTPException(409, "This derived analysis requires saved monitoring results.")
    return run


def diagnostics_router(sessions: sessionmaker[Session], settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/runs/{run_id}/slices")
    def slices(run_id: UUID) -> dict[str, Any]:
        with sessions() as session:
            run = saved_run(session, run_id)
            if run.mode == "A":
                return {"status": "UNAVAILABLE", "reason": MODE_A_LIMITATION}
            analyses = session.scalars(
                select(SliceAnalysis)
                .where(SliceAnalysis.run_id == run.id)
                .order_by(SliceAnalysis.created_at, SliceAnalysis.id)
            )
            return {
                "status": "AVAILABLE",
                "eligible_features": eligible_features(run),
                "analyses": [slice_view(session, a) for a in analyses],
                "limitation": SLICE_LIMITATION,
            }

    @router.post("/runs/{run_id}/slices", status_code=202)
    def create_slice(run_id: UUID, body: SliceRequest) -> dict[str, Any]:
        with sessions.begin() as session:
            run = saved_run(session, run_id, True)
            if run.mode != "B":
                raise HTTPException(409, MODE_A_LIMITATION)
            feature = next(
                (f for f in eligible_features(run) if f["feature_id"] == body.feature_id), None
            )
            if not feature:
                raise HTTPException(
                    422, "Only included frozen categorical model features are eligible."
                )
            existing = session.scalar(
                select(SliceAnalysis).where(
                    SliceAnalysis.run_id == run.id,
                    SliceAnalysis.feature_id == body.feature_id,
                    SliceAnalysis.methodology_version == SLICE_METHODOLOGY_VERSION,
                )
            )
            if existing:
                return slice_view(session, existing)
            analysis = SliceAnalysis(
                run_id=run.id,
                feature_id=body.feature_id,
                feature_name=feature["name"],
                methodology_version=SLICE_METHODOLOGY_VERSION,
            )
            session.add(analysis)
            session.flush()
            session.add(
                Job(
                    job_type="SLICE_ANALYZE",
                    target_type="SLICE",
                    target_id=analysis.id,
                    project_id=run.project_id,
                    params={"run_id": str(run.id)},
                )
            )
            session.flush()
            return slice_view(session, analysis)

    @router.get("/runs/{run_id}/slices/{slice_id}")
    def slice_detail(run_id: UUID, slice_id: UUID) -> dict[str, Any]:
        with sessions() as session:
            run = saved_run(session, run_id)
            analysis = session.get(SliceAnalysis, slice_id)
            if not analysis or analysis.run_id != run.id:
                raise HTTPException(404, "Slice analysis not found for this run.")
            return slice_view(session, analysis)

    @router.get("/projects/{project_id}/trends")
    def trends(
        project_id: UUID,
        group: str = "confidence",
        signal: str = "median",
        feature_id: str | None = None,
        class_label: str | None = None,
    ) -> dict[str, Any]:
        with sessions() as session:
            get_project(session, project_id)
            return project_trends(session, project_id, group, signal, feature_id, class_label)

    @router.get("/runs/{run_id}/report")
    def report(run_id: UUID) -> dict[str, Any]:
        with sessions.begin() as session:
            run = saved_run(session, run_id, True)
            stored = session.get(RunReport, run.id)
            if not stored and settings.deployment_mode == "demo":
                raise HTTPException(
                    409, "A stored report is not available in this read-only environment."
                )
            stored = stored or save_report(session, run, settings.code_version)
            analyses = session.scalars(
                select(SliceAnalysis)
                .where(SliceAnalysis.run_id == run.id, SliceAnalysis.status == "READY")
                .order_by(SliceAnalysis.created_at, SliceAnalysis.id)
            )
            return {
                "report": stored.payload,
                "slice_analyses": [slice_view(session, a) for a in analyses],
            }

    return router
