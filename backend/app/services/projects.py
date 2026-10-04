from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.db.models import Dataset, Job, Project
from backend.app.domain.datasets import preprocessing_summary


def get_project(session: Session, project_id: UUID, *, lock: bool = False) -> Project:
    statement = select(Project).where(Project.id == project_id)
    if lock:
        statement = statement.with_for_update()
    project = session.scalar(statement)
    if project is None:
        raise HTTPException(404, "Project not found.")
    return project


def mutable(session: Session, project: Project) -> None:
    if project.state != "DRAFT" or project.deletion_pending:
        raise HTTPException(409, "This project is not mutable.")
    if session.scalar(
        select(Job.id).where(Job.project_id == project.id, Job.state.in_(["QUEUED", "RUNNING"]))
    ):
        raise HTTPException(409, "Wait for the active job to finish before changing this project.")


def latest_dataset(session: Session, project_id: UUID) -> Dataset | None:
    return session.scalar(
        select(Dataset)
        .where(Dataset.project_id == project_id, Dataset.role == "BASELINE")
        .order_by(Dataset.created_at.desc(), Dataset.id.desc())
        .limit(1)
    )


def project_view(session: Session, project: Project, settings: Settings) -> dict[str, Any]:
    dataset = latest_dataset(session, project.id)
    job = session.scalar(
        select(Job)
        .where(Job.project_id == project.id)
        .order_by(Job.created_at.desc(), Job.id.desc())
        .limit(1)
    )
    config = project.configuration
    complete = bool(config.get("classifier") and config.get("weighting"))
    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "state": project.state,
        "deletion_pending": project.deletion_pending,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
        "configuration": config,
        "limits": {
            "upload_max_bytes": settings.upload_max_bytes,
            "max_rows": settings.max_rows,
            "max_columns": settings.max_columns,
            "max_features": settings.max_features,
            "max_categories": settings.max_categories,
            "max_encoded_columns": settings.max_encoded_columns,
        },
        "dataset": (
            {
                "id": str(dataset.id),
                "status": dataset.status,
                "profile": dataset.profile,
                "validation_report": dataset.validation_report,
                "canonical_sha256": dataset.canonical_sha256,
                "canonical_schema_version": dataset.canonical_schema_version,
            }
            if dataset
            else None
        ),
        "job": (
            {
                "id": str(job.id),
                "state": job.state,
                "stage": job.stage,
                "error_message": job.error_message,
            }
            if job
            else None
        ),
        "preprocessing": preprocessing_summary(config) if config else None,
        "confirmation": (
            {
                "ready": True,
                "training_available": False,
                "split": "Stratified 80/20",
                "cv": "5-fold Development CV",
                "seed": 42,
                "guardrail": (
                    "Actual held-out support must be at least 20 rows per class, "
                    "checked after the split during training. No split or model has been fitted."
                ),
            }
            if complete
            else None
        ),
    }
