"""Leased additive slice inference and atomic publication; core runs never change."""

import json
import re
from collections.abc import Callable
from io import BytesIO
from typing import Any

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
    SliceAnalysis,
    SliceResult,
)
from backend.app.domain.datasets import SCHEMA_VERSION, DatasetError
from backend.app.domain.jobs import OwnershipLost
from backend.app.domain.monitoring import frozen_features
from backend.app.jobs.artifacts import load_trusted
from backend.app.jobs.monitoring import checked
from backend.app.science.baseline import fingerprint
from backend.app.science.monitoring import predict_probabilities
from backend.app.science.slices import SLICE_LIMITATION, SLICE_METHODOLOGY_VERSION, analyze_slices
from backend.app.services.queue import Queue
from backend.app.storage.base import ArtifactStore


def slice_result(
    queue: Queue, job: Job, store: ArtifactStore, settings: Settings
) -> tuple[Callable[[Session], None], bool]:
    queue.stage(job, "VALIDATING")
    with queue.sessions() as session:
        analysis = session.get(SliceAnalysis, job.target_id)
        if not analysis or analysis.status != "PENDING":
            raise OwnershipLost
        run = session.get(MonitoringRun, analysis.run_id)
        if (
            not run
            or run.deletion_pending
            or run.state != "ANALYZED"
            or run.mode != "B"
            or not run.results
        ):
            raise OwnershipLost
        snapshot = session.get(BaselineSnapshot, run.baseline_snapshot_id)
        dataset = session.get(Dataset, run.dataset_id)
        assert snapshot and snapshot.results and dataset
        baseline = session.get(Dataset, snapshot.dataset_id)
        artifact = session.scalar(
            select(ModelArtifact).where(ModelArtifact.snapshot_id == snapshot.id)
        )
    rows: list[dict[str, Any]] = []
    error = None
    try:
        assert baseline and baseline.profile and artifact
        if not re.fullmatch(r"[0-9a-f]{40}", settings.code_version):
            raise DatasetError(
                "Build provenance is unavailable. Rebuild with the documented Git SHA."
            )
        config = snapshot.configuration
        features = frozen_features(baseline.profile, config)
        feature = next(
            (
                f
                for f in features
                if f["feature_id"] == analysis.feature_id and f["type"] == "categorical"
            ),
            None,
        )
        if not feature or analysis.methodology_version != SLICE_METHODOLOGY_VERSION:
            raise DatasetError(
                "Only included frozen categorical features support this slice methodology."
            )
        manifest = artifact.environment_manifest
        if (
            snapshot.status != "ESTABLISHED"
            or snapshot.project_id != run.project_id
            or fingerprint(baseline.canonical_sha256 or "", config) != snapshot.config_fingerprint
            or manifest["snapshot_id"] != str(snapshot.id)
            or manifest["project_id"] != str(run.project_id)
            or manifest["canonical_sha256"] != baseline.canonical_sha256
            or manifest["canonical_schema_version"] != SCHEMA_VERSION
            or manifest["configuration_fingerprint"] != snapshot.config_fingerprint
            or manifest["class_order"] != config["class_order"]
            or manifest["feature_types"] != {f["name"]: f["type"] for f in features}
            or dataset.canonical_schema_version != SCHEMA_VERSION
            or dataset.project_id != run.project_id
            or dataset.role != "CURRENT"
            or dataset.canonical_sha256 != run.results["canonical_sha256"]
            or artifact.sha256 != manifest["artifact_sha256"]
            or artifact.sha256 != run.results["model_sha256"]
        ):
            raise DatasetError("The frozen slice source or model metadata is incompatible.")
        assert snapshot.artifact_prefix
        if (
            json.loads(
                checked(
                    store,
                    snapshot.artifact_prefix + "/manifest.json",
                    snapshot.results["artifact_hashes"]["manifest.json"],
                )
            )
            != manifest
        ):
            raise DatasetError("The trusted model manifest failed verification.")
        frame = pd.read_parquet(
            BytesIO(checked(store, dataset.canonical_object_key, dataset.canonical_sha256))
        )
        pipeline = load_trusted(store, artifact.storage_key, artifact.sha256, manifest)
        target = next(
            c["name"] for c in baseline.profile["columns"] if c["feature_id"] == config["target_id"]
        )
        if frame[target].isna().any():
            raise DatasetError("Complete valid labels are required for slices.")
        y = frame[target].map(lambda v: v.strip()).to_numpy()
        if not set(y).issubset(config["class_order"]):
            raise DatasetError("Slice labels are outside the frozen class list.")
        queue.stage(job, "PREDICTING")
        predicted, probabilities = predict_probabilities(pipeline, frame, config["class_order"])
        queue.stage(job, "SLICES")
        rows = analyze_slices(
            frame[feature["name"]],
            y,
            predicted,
            probabilities,
            config["class_order"],
            config["positive_class"],
            snapshot.results["metrics"],
        )
        overall = rows[0]["metrics"]
        if any(
            overall[m["metric_name"]]["value"] != m["current_value"]
            for m in run.results["performance"]["metrics"]
        ):
            raise DatasetError(
                "Frozen inference does not match the saved overall run. No slices were published."
            )
        queue.stage(job, "PERSISTING")
    except OwnershipLost:
        raise
    except Exception as exc:
        error = (
            exc.message
            if isinstance(exc, DatasetError)
            else "Slice analysis could not finish. The saved run remains unchanged."
        )

    def publish(session: Session) -> None:
        current_run = session.scalar(
            select(MonitoringRun).where(MonitoringRun.id == run.id).with_for_update()
        )
        current = session.get(SliceAnalysis, analysis.id)
        if (
            not current_run
            or current_run.deletion_pending
            or current_run.state != "ANALYZED"
            or not current
            or current.status != "PENDING"
            or current.run_id != run.id
        ):
            raise OwnershipLost
        if error:
            current.status = "FAILED"
            saved_job = session.get(Job, job.id)
            assert saved_job
            saved_job.error_message = error
        else:
            for row in rows:
                session.add(SliceResult(slice_analysis_id=current.id, **row))
            session.flush()
            current.status, current.limitation, current.code_version = (
                "READY",
                SLICE_LIMITATION,
                settings.code_version,
            )
            current.published_at = session.scalar(select(func.now()))

    return publish, error is not None
