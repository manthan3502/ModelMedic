import hashlib
from collections.abc import Callable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.db.models import Dataset, Job, Project
from backend.app.domain.datasets import SCHEMA_VERSION, DatasetError, validate_csv
from backend.app.domain.jobs import OwnershipLost
from backend.app.services.projects import latest_dataset
from backend.app.services.queue import Queue
from backend.app.storage.base import ArtifactStore


def validation_result(
    queue: Queue, job: Job, store: ArtifactStore, settings: Settings
) -> tuple[Callable[[Session], None], str | None]:
    with queue.sessions() as session:
        dataset = session.get(Dataset, job.target_id)
        if dataset is None:
            raise OwnershipLost
        key = dataset.original_object_key
        project_id = dataset.project_id
        original_hash = dataset.original_sha256
    profile: dict[str, Any] | None = None
    errors: list[str] = []
    canonical_key = None
    try:
        queue.stage(job, "READING_FILE")
        original = store.get(key)
        if hashlib.sha256(original).hexdigest() != original_hash:
            raise DatasetError("Uploaded file integrity check failed. Re-upload the source CSV.")
        canonical, profile = validate_csv(original, settings, lambda stage: queue.stage(job, stage))
        canonical_key = (
            f"projects/{project_id}/datasets/{job.target_id}/"
            f"attempt-{job.owner_token}/canonical.parquet"
        )
        store.put(canonical_key, canonical)
    except DatasetError as exc:
        errors = [exc.message]

    def persist(session: Session) -> None:
        project = session.scalar(select(Project).where(Project.id == project_id).with_for_update())
        dataset = session.get(Dataset, job.target_id)
        latest = latest_dataset(session, project_id)
        if (
            not project
            or project.state != "DRAFT"
            or project.deletion_pending
            or not dataset
            or not latest
            or latest.id != dataset.id
        ):
            raise OwnershipLost
        dataset.status = "VALIDATION_FAILED" if errors else "READY"
        dataset.validation_report = {
            "errors": errors,
            "warnings": [flag for c in profile["columns"] for flag in c["flags"]]
            if profile
            else [],
        }
        dataset.profile = profile
        dataset.canonical_object_key = canonical_key
        dataset.canonical_sha256 = profile["canonical_sha256"] if profile else None
        dataset.canonical_schema_version = SCHEMA_VERSION if profile else None
        now = session.scalar(select(func.now()))
        assert now is not None
        project.updated_at = now

    return persist, canonical_key
