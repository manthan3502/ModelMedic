import hashlib
import tempfile
from datetime import date
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from backend.app.core.config import Settings
from backend.app.db.models import BaselineSnapshot, Dataset, Job, MonitoringRun, SliceAnalysis
from backend.app.science.monitoring import MODE_A_LIMITATION
from backend.app.services.examples import error_examples
from backend.app.services.monitoring import active_job, get_run, mutable_run, run_view
from backend.app.services.presentation import interpretations
from backend.app.services.projects import get_project
from backend.app.services.reporting import diagnostic
from backend.app.storage.base import ArtifactStore


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    monitoring_date: date
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Run name is required.")
        return value.strip()


def monitoring_router(
    sessions: sessionmaker[Session], store: ArtifactStore, settings: Settings
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.post("/projects/{project_id}/runs", status_code=201)
    def create(project_id: UUID, body: RunCreate) -> dict[str, Any]:
        with sessions.begin() as session:
            project = get_project(session, project_id, lock=True)
            snapshot = session.scalar(
                select(BaselineSnapshot).where(
                    BaselineSnapshot.project_id == project_id,
                    BaselineSnapshot.status == "ESTABLISHED",
                )
            )
            if (
                not snapshot
                or project.deletion_pending
                or project.state not in {"BASELINE_READY", "MONITORING"}
            ):
                raise HTTPException(409, "Establish the baseline before creating a monitoring run.")
            run = MonitoringRun(
                project_id=project_id, baseline_snapshot_id=snapshot.id, **body.model_dump()
            )
            session.add(run)
            now = session.scalar(select(func.now()))
            assert now is not None
            project.updated_at = now
            session.flush()
            return run_view(session, run)

    @router.get("/projects/{project_id}/runs")
    def history(project_id: UUID) -> list[dict[str, Any]]:
        with sessions() as session:
            get_project(session, project_id)
            return [
                run_view(session, r)
                for r in session.scalars(
                    select(MonitoringRun)
                    .where(MonitoringRun.project_id == project_id)
                    .order_by(
                        MonitoringRun.monitoring_date.desc(),
                        MonitoringRun.created_at.desc(),
                        MonitoringRun.id.desc(),
                    )
                )
            ]

    @router.get("/runs/{run_id}")
    def fetch(run_id: UUID) -> dict[str, Any]:
        with sessions() as session:
            return run_view(session, get_run(session, run_id))

    def check_upload(run_id: UUID) -> None:
        with sessions() as session:
            mutable_run(session, get_run(session, run_id))

    def accept(run_id: UUID, temporary: Path, size: int, digest: str) -> dict[str, Any]:
        dataset_id = uuid4()
        key = ""
        try:
            with sessions.begin() as session:
                run = get_run(session, run_id, True)
                mutable_run(session, run)
                key = f"projects/{run.project_id}/runs/{run.id}/datasets/{dataset_id}/original.csv"
                store.put_file(key, temporary)
                session.add(
                    Dataset(
                        id=dataset_id,
                        project_id=run.project_id,
                        role="CURRENT",
                        original_object_key=key,
                        original_sha256=digest,
                        uploaded_bytes=size,
                    )
                )
                session.flush()
                run.dataset_id, run.state, run.mode, run.row_count = (
                    dataset_id,
                    "UPLOADED",
                    None,
                    None,
                )
                session.add(
                    Job(
                        job_type="DATASET_VALIDATE",
                        target_type="RUN",
                        target_id=run.id,
                        project_id=run.project_id,
                        params={
                            "dataset_id": str(dataset_id),
                            "snapshot_id": str(run.baseline_snapshot_id),
                        },
                    )
                )
                session.flush()
                return run_view(session, run)
        except BaseException:
            if key and store.exists(key):
                store.delete(key)
            raise

    @router.post("/runs/{run_id}/upload", status_code=202)
    async def upload(run_id: UUID, request: Request) -> dict[str, Any]:
        if request.headers.get("content-type", "").split(";")[0] not in {
            "text/csv",
            "application/octet-stream",
        }:
            raise HTTPException(415, "Send a UTF-8 CSV with Content-Type text/csv.")
        await run_in_threadpool(check_upload, run_id)
        directory = settings.artifact_root / ".uploads"
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as handle:
            temporary = Path(handle.name)
            size, digest = 0, hashlib.sha256()
            try:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > settings.upload_max_bytes:
                        raise HTTPException(413, "CSV exceeds the configured byte limit.")
                    handle.write(chunk)
                    digest.update(chunk)
                handle.close()
                return await run_in_threadpool(accept, run_id, temporary, size, digest.hexdigest())
            finally:
                handle.close()
                temporary.unlink(missing_ok=True)

    @router.post("/runs/{run_id}/analyze", status_code=202)
    def analyze(run_id: UUID) -> dict[str, Any]:
        with sessions.begin() as session:
            run = get_run(session, run_id, True)
            mutable_run(session, run)
            if run.state != "READY":
                raise HTTPException(409, "Upload and successfully validate the current CSV first.")
            if run.mode not in {"A", "B"}:
                raise HTTPException(409, "A valid monitoring mode is required.")
            session.add(
                Job(
                    job_type="MONITORING_ANALYZE",
                    target_type="RUN",
                    target_id=run.id,
                    project_id=run.project_id,
                    params={
                        "dataset_id": str(run.dataset_id),
                        "snapshot_id": str(run.baseline_snapshot_id),
                    },
                )
            )
            session.flush()
            return run_view(session, run)

    def results(session: Session, run_id: UUID) -> dict[str, Any]:
        run = get_run(session, run_id)
        if run.state != "ANALYZED" or not run.results:
            raise HTTPException(409, "Results become available only after analysis is saved.")
        return run.results

    @router.get("/runs/{run_id}/summary")
    def summary(run_id: UUID) -> dict[str, Any]:
        with sessions() as session:
            return results(session, run_id)

    @router.get("/runs/{run_id}/features")
    def features(run_id: UUID) -> list[dict[str, Any]]:
        with sessions() as session:
            return list(results(session, run_id)["features"])

    @router.get("/runs/{run_id}/features/{feature_id}")
    def feature(run_id: UUID, feature_id: str) -> dict[str, Any]:
        with sessions() as session:
            found = next(
                (f for f in results(session, run_id)["features"] if f["feature_id"] == feature_id),
                None,
            )
            if not found:
                raise HTTPException(404, "Frozen feature not found.")
            return {
                **found,
                "interpretation": diagnostic(found, results(session, run_id)["data_reference"]),
            }

    @router.get("/runs/{run_id}/presentation")
    def presentation(run_id: UUID) -> dict[str, dict[str, str]]:
        with sessions() as session:
            return interpretations(results(session, run_id))

    @router.get("/runs/{run_id}/predictions")
    def predictions(run_id: UUID) -> dict[str, Any]:
        with sessions() as session:
            return dict(results(session, run_id)["predictions"])

    @router.get("/runs/{run_id}/confidence")
    def confidence(run_id: UUID) -> dict[str, Any]:
        with sessions() as session:
            return dict(results(session, run_id)["confidence"])

    @router.get("/runs/{run_id}/metrics")
    def metrics(run_id: UUID) -> dict[str, Any]:
        with sessions() as session:
            data = results(session, run_id)
            return (
                dict(data["performance"])
                if data["mode"] == "B"
                else {"status": "UNAVAILABLE", "reason": MODE_A_LIMITATION}
            )

    @router.get("/runs/{run_id}/calibration")
    def calibration(run_id: UUID) -> dict[str, Any]:
        with sessions() as session:
            data = results(session, run_id)
            return (
                dict(data["calibration"])
                if data["mode"] == "B"
                else {"status": "UNAVAILABLE", "reason": MODE_A_LIMITATION}
            )

    @router.get("/runs/{run_id}/errors")
    def errors(run_id: UUID) -> dict[str, Any]:
        with sessions() as session:
            data = results(session, run_id)
            return (
                dict(data["errors"])
                if data["mode"] == "B"
                else {"status": "UNAVAILABLE", "reason": MODE_A_LIMITATION}
            )

    @router.get("/runs/{run_id}/errors/examples")
    def examples(run_id: UUID, view: str = "fp") -> dict[str, Any]:
        with sessions() as session:
            data = results(session, run_id)
            if data["mode"] != "B":
                return {"status": "UNAVAILABLE", "reason": MODE_A_LIMITATION}
            return error_examples(session, get_run(session, run_id), store, view)

    @router.delete("/runs/{run_id}", status_code=204)
    def delete(run_id: UUID) -> None:
        with sessions.begin() as session:
            run = get_run(session, run_id, True)
            if active_job(session, run):
                raise HTTPException(409, "Wait for the active job before deleting this run.")
            run.deletion_pending = True
            prefix = f"projects/{run.project_id}/runs/{run.id}"
        try:
            store.delete_prefix(prefix)
        except OSError:
            raise HTTPException(503, "Run deletion is pending. Retry to finish cleanup.") from None
        with sessions.begin() as session:
            run = get_run(session, run_id, True)
            datasets = list(
                session.scalars(
                    select(Dataset).where(
                        Dataset.project_id == run.project_id,
                        Dataset.role == "CURRENT",
                        Dataset.original_object_key.startswith(prefix + "/"),
                    )
                )
            )
            for job in session.scalars(
                select(Job).where(
                    or_(
                        (Job.target_type == "RUN") & (Job.target_id == run_id),
                        (Job.target_type == "SLICE")
                        & Job.target_id.in_(
                            select(SliceAnalysis.id).where(SliceAnalysis.run_id == run_id)
                        ),
                    )
                )
            ):
                session.delete(job)
            session.delete(run)
            session.flush()
            for dataset in datasets:
                session.delete(dataset)

    return router
