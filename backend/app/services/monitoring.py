from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import Dataset, Job, MonitoringRun


def get_run(session: Session, run_id: UUID, lock: bool = False) -> MonitoringRun:
    query = select(MonitoringRun).where(MonitoringRun.id == run_id)
    run = session.scalar(query.with_for_update() if lock else query)
    if run is None:
        raise HTTPException(404, "Monitoring run not found.")
    return run


def active_job(session: Session, run: MonitoringRun) -> Job | None:
    return session.scalar(
        select(Job).where(
            Job.target_type == "RUN",
            Job.target_id == run.id,
            Job.state.in_(["QUEUED", "RUNNING"]),
        )
    )


def mutable_run(session: Session, run: MonitoringRun) -> None:
    if run.state == "ANALYZED" or run.deletion_pending:
        raise HTTPException(409, "Analyzed runs are immutable. Create a new monitoring run.")
    if active_job(session, run):
        raise HTTPException(409, "Wait for the active monitoring job to finish.")


def run_view(session: Session, run: MonitoringRun) -> dict[str, Any]:
    dataset = session.get(Dataset, run.dataset_id) if run.dataset_id else None
    job = session.scalar(
        select(Job)
        .where(Job.target_type == "RUN", Job.target_id == run.id)
        .order_by(Job.created_at.desc(), Job.id.desc())
        .limit(1)
    )
    return {
        "id": str(run.id),
        "project_id": str(run.project_id),
        "name": run.name,
        "monitoring_date": run.monitoring_date.isoformat(),
        "notes": run.notes,
        "created_at": run.created_at.isoformat(),
        "state": run.state,
        "mode": run.mode,
        "baseline_snapshot_id": str(run.baseline_snapshot_id),
        "row_count": run.row_count,
        "deletion_pending": run.deletion_pending,
        "analyzed_at": run.analyzed_at.isoformat() if run.analyzed_at else None,
        "methodology_version": run.methodology_version,
        "code_version": run.code_version,
        "result_sha256": run.result_sha256,
        "dataset": {
            "id": str(dataset.id),
            "status": dataset.status,
            "validation_report": dataset.validation_report,
            "canonical_sha256": dataset.canonical_sha256,
            "canonical_schema_version": dataset.canonical_schema_version,
        }
        if dataset
        else None,
        "job": {
            "id": str(job.id),
            "state": job.state,
            "stage": job.stage,
            "error_message": job.error_message,
            "started_at": job.started_at.isoformat() if job.started_at else None,
        }
        if job
        else None,
        "summary": {
            "counts": run.results["counts"],
            "tested_features": run.results["tested_features"],
            "median_confidence": run.results["confidence"]["current_median"],
        }
        if run.state == "ANALYZED" and run.results
        else None,
    }
