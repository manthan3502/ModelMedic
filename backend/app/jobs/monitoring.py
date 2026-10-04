"""Worker-only frozen inference and fenced atomic monitoring publication."""

import json
import re
from collections.abc import Callable
from hashlib import sha256
from io import BytesIO
from typing import Any
from uuid import UUID

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.db.models import (
    BaselineSnapshot,
    Dataset,
    Job,
    ModelArtifact,
    MonitoringRun,
    Project,
    RunFeatureResult,
)
from backend.app.domain.datasets import SCHEMA_VERSION, DatasetError
from backend.app.domain.jobs import OwnershipLost
from backend.app.domain.monitoring import frozen_features, validate_current
from backend.app.jobs.artifacts import load_trusted
from backend.app.science.baseline import fingerprint
from backend.app.science.monitoring import METHODOLOGY_VERSION, analyze_mode_a
from backend.app.services.queue import Queue
from backend.app.storage.base import ArtifactStore


def checked(store: ArtifactStore, key: str | None, digest: str | None) -> bytes:
    if not key or not digest:
        raise DatasetError(
            "A required immutable reference is unavailable. Analysis was not published."
        )
    payload = store.get(key)
    if sha256(payload).hexdigest() != digest:
        raise DatasetError(
            "An immutable reference failed integrity verification. Analysis was not published."
        )
    return payload


def context(session: Session, job: Job) -> tuple[MonitoringRun, Dataset, BaselineSnapshot, Dataset]:
    run = session.get(MonitoringRun, job.target_id)
    dataset = session.get(Dataset, UUID(job.params["dataset_id"]))
    snapshot = session.get(BaselineSnapshot, UUID(job.params["snapshot_id"]))
    if (
        not run
        or run.deletion_pending
        or run.state == "ANALYZED"
        or not dataset
        or not snapshot
        or run.dataset_id != dataset.id
        or run.baseline_snapshot_id != snapshot.id
        or snapshot.status != "ESTABLISHED"
        or snapshot.project_id != run.project_id
        or dataset.project_id != run.project_id
        or dataset.role != "CURRENT"
    ):
        raise OwnershipLost
    baseline = session.get(Dataset, snapshot.dataset_id)
    if not baseline or not baseline.profile:
        raise OwnershipLost
    return run, dataset, snapshot, baseline


def validation_result(
    queue: Queue, job: Job, store: ArtifactStore, settings: Settings
) -> tuple[Callable[[Session], None], str | None]:
    with queue.sessions() as session:
        run, dataset, snapshot, baseline = context(session, job)
    report: dict[str, Any] = {"errors": [], "warnings": []}
    profile = None
    key = None
    try:
        queue.stage(job, "VALIDATING")
        original = checked(store, dataset.original_object_key, dataset.original_sha256)
        baseline_bytes = checked(store, baseline.canonical_object_key, baseline.canonical_sha256)
        assert baseline.profile
        canonical, profile, report = validate_current(
            original, settings, baseline_bytes, baseline.profile, snapshot.configuration
        )
        queue.stage(job, "BUILDING_TYPED_COPY")
        key = f"projects/{run.project_id}/runs/{run.id}/attempt-{job.owner_token}/canonical.parquet"
        store.put(key, canonical)
    except DatasetError as exc:
        report = {"errors": [exc.message], "warnings": []}

    def persist(session: Session) -> None:
        current = session.scalar(
            select(MonitoringRun).where(MonitoringRun.id == run.id).with_for_update()
        )
        context(session, job)
        assert current
        data = session.get(Dataset, dataset.id)
        assert data
        data.status = current.state = "VALIDATION_FAILED" if report["errors"] else "READY"
        data.validation_report, data.profile = report, profile
        data.canonical_object_key = key
        data.canonical_sha256 = profile["canonical_sha256"] if profile else None
        data.canonical_schema_version = SCHEMA_VERSION if profile else None
        current.mode = report.get("mode")
        current.row_count = profile["row_count"] if profile else None

    return persist, key


def analysis_result(
    queue: Queue, job: Job, store: ArtifactStore, settings: Settings
) -> tuple[Callable[[Session], None], str, bool]:
    queue.stage(job, "VALIDATING")
    with queue.sessions() as session:
        run, dataset, snapshot, baseline = context(session, job)
        artifact = session.scalar(
            select(ModelArtifact).where(ModelArtifact.snapshot_id == snapshot.id)
        )
    prefix = f"projects/{run.project_id}/runs/{run.id}/attempt-{job.owner_token}"
    error = None
    results: dict[str, Any] = {}
    digest = ""
    try:
        if run.state != "READY" or run.mode != "A" or dataset.status != "READY":
            raise DatasetError("Analysis requires successfully validated Mode A data.")
        if not re.fullmatch(r"[0-9a-f]{40}", settings.code_version):
            raise DatasetError(
                "Build provenance is unavailable. Rebuild with the documented Git SHA."
            )
        assert baseline.profile and snapshot.results and artifact
        config = snapshot.configuration
        manifest = artifact.environment_manifest
        if (
            fingerprint(baseline.canonical_sha256 or "", config) != snapshot.config_fingerprint
            or manifest["snapshot_id"] != str(snapshot.id)
            or manifest["project_id"] != str(run.project_id)
            or manifest["configuration_fingerprint"] != snapshot.config_fingerprint
            or manifest["canonical_sha256"] != baseline.canonical_sha256
            or manifest["canonical_schema_version"] != SCHEMA_VERSION
            or manifest["class_order"] != config["class_order"]
        ):
            raise DatasetError("Frozen baseline manifest does not match this run's snapshot.")
        manifest_bytes = checked(
            store,
            snapshot.artifact_prefix + "/manifest.json" if snapshot.artifact_prefix else None,
            snapshot.results["artifact_hashes"]["manifest.json"],
        )
        if json.loads(manifest_bytes) != manifest:
            raise DatasetError(
                "Stored model manifest does not match its trusted database metadata."
            )
        if dataset.canonical_schema_version != SCHEMA_VERSION:
            raise DatasetError("Current canonical schema is incompatible with this worker.")
        baseline_bytes = checked(store, baseline.canonical_object_key, baseline.canonical_sha256)
        current_bytes = checked(store, dataset.canonical_object_key, dataset.canonical_sha256)
        reference_bytes = checked(
            store,
            snapshot.heldout_reference_object_key,
            snapshot.results["artifact_hashes"]["heldout.parquet"],
        )
        # Revalidate original source against the same snapshot; no semantic re-inference.
        canonical, _, report = validate_current(
            checked(store, dataset.original_object_key, dataset.original_sha256),
            settings,
            baseline_bytes,
            baseline.profile,
            config,
        )
        if report["mode"] != "A" or sha256(canonical).hexdigest() != dataset.canonical_sha256:
            raise DatasetError("Validated current data changed. Analysis was not published.")
        pipeline = load_trusted(store, artifact.storage_key, artifact.sha256, manifest)
        features = frozen_features(baseline.profile, config)
        if manifest["feature_types"] != {f["name"]: f["type"] for f in features}:
            raise DatasetError("Frozen feature semantics do not match the model manifest.")
        results = analyze_mode_a(
            pd.read_parquet(BytesIO(baseline_bytes)),
            pd.read_parquet(BytesIO(current_bytes)),
            pd.read_parquet(BytesIO(reference_bytes)),
            features,
            pipeline,
            config["class_order"],
            snapshot.results["importance"],
            lambda s: queue.stage(job, s),
        )
        results.update(
            {
                "baseline_snapshot_id": str(snapshot.id),
                "code_version": settings.code_version,
                "code_dirty": settings.code_dirty,
                "canonical_sha256": dataset.canonical_sha256,
                "baseline_canonical_sha256": baseline.canonical_sha256,
                "reference_sha256": snapshot.results["artifact_hashes"]["heldout.parquet"],
                "model_sha256": artifact.sha256,
                "validation": report,
            }
        )
        queue.stage(job, "PERSISTING")
        payload = json.dumps(results, allow_nan=False, sort_keys=True).encode()
        digest = sha256(payload).hexdigest()
        store.put(prefix + "/results.json", payload)
    except OwnershipLost:
        store.delete_prefix(prefix)
        raise
    except Exception as exc:
        store.delete_prefix(prefix)
        error = (
            exc.message
            if isinstance(exc, DatasetError)
            else (
                "Monitoring analysis failed. No final results were published. "
                "Review the data and retry."
            )
        )

    def persist(session: Session) -> None:
        current = session.scalar(
            select(MonitoringRun).where(MonitoringRun.id == run.id).with_for_update()
        )
        context(session, job)
        assert current
        if current.state != "READY":
            raise OwnershipLost
        if error:
            owned = session.get(Job, job.id)
            assert owned
            owned.error_message = error
            return
        for f in results["features"]:
            d, m = f["distribution"], f["missingness"]
            session.add(
                RunFeatureResult(
                    run_id=current.id,
                    feature_id=f["feature_id"],
                    feature_name=f["name"],
                    feature_type=f["type"],
                    distribution_status=d["status"],
                    missingness_status=m["status"],
                    raw_p_value=d["raw_p"],
                    adjusted_p_value=d["adjusted_p"],
                    missing_p_value=m["raw_p"],
                    missing_adjusted_p_value=m["adjusted_p"],
                    baseline_valid_n=d["baseline_n"],
                    current_valid_n=d["current_n"],
                    evidence=f,
                )
            )
        session.flush()  # Insert feature evidence while READY, before sealing the run.
        current.results = results
        current.result_object_key, current.result_sha256 = prefix + "/results.json", digest
        current.methodology_version, current.code_version = (
            METHODOLOGY_VERSION,
            settings.code_version,
        )
        current.analyzed_at = session.scalar(select(func.now()))
        current.state = "ANALYZED"
        project = session.get(Project, current.project_id)
        assert project
        project.state = "MONITORING"
        now = session.scalar(select(func.now()))
        assert now is not None
        project.updated_at = now

    return persist, prefix, error is not None
