import hashlib
import logging
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from backend.app.core.config import Settings
from backend.app.db.models import BaselineSnapshot, Dataset, Job, Project
from backend.app.domain.datasets import DatasetError, validate_configuration
from backend.app.schemas.projects import Configuration, ProjectCreate
from backend.app.science.baseline import fingerprint
from backend.app.services.demo import registry
from backend.app.services.projects import (
    get_project,
    latest_dataset,
    latest_snapshot,
    mutable,
    project_view,
)
from backend.app.storage.base import ArtifactStore


class EstablishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    snapshot_id: UUID


def project_router(
    sessions: sessionmaker[Session], store: ArtifactStore, settings: Settings
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects")

    @router.post("", status_code=201)
    def create(body: ProjectCreate) -> dict[str, Any]:
        with sessions.begin() as session:
            project = Project(**body.model_dump())
            session.add(project)
            session.flush()
            return project_view(session, project, settings)

    @router.get("")
    def list_projects() -> list[dict[str, Any]]:
        allowed = registry(store)["projects"] if settings.deployment_mode == "demo" else None
        with sessions() as session:
            return [
                project_view(session, p, settings)
                for p in session.scalars(
                    select(Project).order_by(Project.created_at.desc(), Project.id)
                )
                if allowed is None or str(p.id) in allowed
            ]

    @router.get("/{project_id}")
    def fetch(project_id: UUID) -> dict[str, Any]:
        with sessions() as session:
            return project_view(session, get_project(session, project_id), settings)

    def discard(session: Session, project: Project, confirmed: bool) -> None:
        snapshots = list(
            session.scalars(
                select(BaselineSnapshot).where(BaselineSnapshot.project_id == project.id)
            )
        )
        if any(s.status == "TRAINED" for s in snapshots) and not confirmed:
            raise HTTPException(
                409, "Confirm discarding draft training results before changing this dependency."
            )
        prefixes = [s.artifact_prefix for s in snapshots if s.artifact_prefix]

        # Invalidate in PostgreSQL first. A failed transaction must never remove a valid model.
        def cleanup(committed: Session) -> None:
            for prefix in prefixes:
                try:
                    store.delete_prefix(prefix)
                except OSError:
                    # The database commit already succeeded. Never roll back the caller's
                    # newly published upload because old, unreferenced object cleanup failed.
                    logging.getLogger("modelmedic").warning("draft_artifact_cleanup_deferred")

        if prefixes:
            event.listen(session, "after_commit", cleanup, once=True)
        for snapshot in snapshots:
            session.delete(snapshot)
        session.flush()

    def check_upload(project_id: UUID) -> None:
        with sessions() as session:
            mutable(session, get_project(session, project_id))

    def accept(
        project_id: UUID,
        dataset_id: UUID,
        temporary: Path,
        size: int,
        sha256: str,
        discard_results: bool,
    ) -> dict[str, Any]:
        key = f"projects/{project_id}/datasets/{dataset_id}/original.csv"
        published = False
        try:
            with sessions.begin() as session:
                project = get_project(session, project_id, lock=True)
                mutable(session, project)
                discard(session, project, discard_results)
                store.put_file(key, temporary)
                published = True
                session.add(
                    Dataset(
                        id=dataset_id,
                        project_id=project_id,
                        role="BASELINE",
                        original_object_key=key,
                        original_sha256=sha256,
                        uploaded_bytes=size,
                    )
                )
                session.add(
                    Job(
                        job_type="DATASET_VALIDATE",
                        target_type="DATASET",
                        target_id=dataset_id,
                        project_id=project_id,
                    )
                )
                project.configuration = {}
                session.flush()
                return project_view(session, project, settings)
        except BaseException:
            if published:
                store.delete(key)
            raise

    @router.post("/{project_id}/baseline", status_code=202)
    async def upload(
        project_id: UUID, request: Request, discard_results: bool = False
    ) -> dict[str, Any]:
        if request.headers.get("content-type", "").split(";")[0] not in {
            "text/csv",
            "application/octet-stream",
        }:
            raise HTTPException(
                415, "Send a UTF-8 CSV as the request body with Content-Type text/csv."
            )
        await run_in_threadpool(check_upload, project_id)
        directory = settings.artifact_root / ".uploads"
        directory.mkdir(parents=True, exist_ok=True)
        # No client filename/path is read. Chunk counting is authoritative.
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as handle:
            temporary = Path(handle.name)
            size = 0
            digest = hashlib.sha256()
            try:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > settings.upload_max_bytes:
                        raise HTTPException(
                            413, "CSV exceeds the configured byte limit. Use a smaller file."
                        )
                    await run_in_threadpool(handle.write, chunk)
                    digest.update(chunk)
                handle.close()
                if size == 0:
                    raise HTTPException(422, "Choose a non-empty CSV file.")
                return await run_in_threadpool(
                    accept,
                    project_id,
                    uuid4(),
                    temporary,
                    size,
                    digest.hexdigest(),
                    discard_results,
                )
            finally:
                handle.close()
                temporary.unlink(missing_ok=True)

    @router.put("/{project_id}/configuration")
    def configure(
        project_id: UUID, body: Configuration, discard_results: bool = False
    ) -> dict[str, Any]:
        with sessions.begin() as session:
            project = get_project(session, project_id, lock=True)
            mutable(session, project)
            dataset = latest_dataset(session, project_id)
            if (
                not dataset
                or dataset.id != body.dataset_id
                or dataset.status != "READY"
                or not dataset.profile
            ):
                raise HTTPException(
                    409, "Configure only the current successfully validated baseline dataset."
                )
            try:
                configuration = validate_configuration(
                    dataset.profile, body.model_dump(mode="json"), settings
                )
            except DatasetError as exc:
                raise HTTPException(422, exc.message) from None
            if configuration != project.configuration:
                discard(session, project, discard_results)
                project.configuration = configuration
            session.flush()
            return project_view(session, project, settings)

    @router.delete("/{project_id}", status_code=204)
    def delete(project_id: UUID) -> None:
        with sessions.begin() as session:
            project = get_project(session, project_id, lock=True)
            # Retry a failed external deletion while continuing to reject every other mutation.
            if project.deletion_pending:
                if project.state != "DRAFT":
                    raise HTTPException(409, "Only draft projects can be deleted here.")
            else:
                mutable(session, project)
                project.deletion_pending = True
        try:
            store.delete_prefix(f"projects/{project_id}")
        except OSError:
            raise HTTPException(
                503, "Artifact deletion failed. Retry project deletion; other changes are blocked."
            ) from None
        with sessions.begin() as session:
            session.delete(get_project(session, project_id, lock=True))

    @router.post("/{project_id}/train", status_code=202)
    def start_training(project_id: UUID, discard_results: bool = False) -> dict[str, Any]:
        with sessions.begin() as session:
            project = get_project(session, project_id, lock=True)
            mutable(session, project)
            dataset = latest_dataset(session, project_id)
            config = project.configuration
            if (
                not dataset
                or dataset.status != "READY"
                or not dataset.profile
                or not dataset.canonical_sha256
                or config.get("dataset_id") != str(dataset.id)
                or not config.get("classifier")
                or not config.get("weighting")
            ):
                raise HTTPException(409, "Complete baseline setup before training.")
            try:
                validate_configuration(dataset.profile, config, settings)
            except DatasetError as exc:
                raise HTTPException(422, exc.message) from None
            discard(session, project, discard_results)
            session.add(
                Job(
                    job_type="BASELINE_TRAIN",
                    target_type="PROJECT",
                    target_id=project_id,
                    project_id=project_id,
                    params={
                        "dataset_id": str(dataset.id),
                        "fingerprint": fingerprint(dataset.canonical_sha256, config),
                    },
                )
            )
            session.flush()
            return project_view(session, project, settings)

    @router.post("/{project_id}/establish")
    def establish(project_id: UUID, body: EstablishRequest) -> dict[str, Any]:
        with sessions.begin() as session:
            project = get_project(session, project_id, lock=True)
            mutable(session, project)
            snapshot = latest_snapshot(session, project_id)
            dataset = latest_dataset(session, project_id)
            if (
                not snapshot
                or snapshot.id != body.snapshot_id
                or snapshot.status != "TRAINED"
                or not dataset
                or dataset.id != snapshot.dataset_id
                or not dataset.canonical_sha256
                or snapshot.config_fingerprint
                != fingerprint(dataset.canonical_sha256, project.configuration)
            ):
                raise HTTPException(
                    409,
                    "Only the trained result matching the current draft can be "
                    "established. Train the current configuration first.",
                )
            snapshot.status = "ESTABLISHED"
            snapshot.established_at = session.scalar(select(func.now()))
            project.state = "BASELINE_READY"
            session.flush()
            return project_view(session, project, settings)

    @router.get("/{project_id}/baseline/{section}")
    def baseline_result(project_id: UUID, section: str) -> Any:
        with sessions() as session:
            get_project(session, project_id)
            snapshot = latest_snapshot(session, project_id)
            if (
                not snapshot
                or snapshot.status not in {"TRAINED", "ESTABLISHED"}
                or not snapshot.results
            ):
                raise HTTPException(409, "A trained baseline result is not available.")
            if section == "summary":
                return snapshot.results
            if section not in {"metrics", "calibration", "importance"}:
                raise HTTPException(404, "Baseline section not found.")
            return snapshot.results[section]

    return router
