"""Fenced BASELINE_TRAIN publication using the existing PostgreSQL queue."""

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.db.models import BaselineSnapshot, Dataset, Job, ModelArtifact, Project
from backend.app.domain.datasets import validate_configuration
from backend.app.domain.jobs import OwnershipLost
from backend.app.jobs.artifacts import dump, environment, load_trusted
from backend.app.science.baseline import (
    ARTIFACT_VERSION,
    METHODOLOGY_VERSION,
    TrainingError,
    fingerprint,
    train,
)
from backend.app.services.queue import Queue
from backend.app.storage.base import ArtifactStore


def training_result(
    queue: Queue, job: Job, store: ArtifactStore, settings: Settings
) -> tuple[Callable[[Session], None], str, bool]:
    queue.stage(job, "VALIDATING")
    snapshot_id = uuid4()
    prefix = f"projects/{job.project_id}/snapshots/{snapshot_id}"
    with queue.sessions.begin() as session:
        owned = session.scalar(
            select(Job)
            .where(
                Job.id == job.id,
                Job.owner_token == job.owner_token,
                Job.attempt == job.attempt,
                Job.state == "RUNNING",
                Job.lease_expires_at > func.clock_timestamp(),
            )
            .with_for_update()
        )
        project = session.get(Project, job.project_id)
        dataset = session.get(Dataset, job.params["dataset_id"])
        if (
            not owned
            or not project
            or project.state != "DRAFT"
            or not dataset
            or not dataset.canonical_sha256
            or fingerprint(dataset.canonical_sha256, project.configuration)
            != job.params["fingerprint"]
        ):
            raise OwnershipLost
        config = dict(project.configuration)
        session.add(
            BaselineSnapshot(
                id=snapshot_id,
                project_id=project.id,
                dataset_id=dataset.id,
                status="TRAINING",
                config_fingerprint=job.params["fingerprint"],
                configuration=config,
                artifact_prefix=prefix,
                methodology_version=METHODOLOGY_VERSION,
                code_version=settings.code_version,
            )
        )
    error = None
    results: dict[str, Any] = {}
    manifest: dict[str, Any] = {}
    digest = ""
    try:
        if not re.fullmatch(r"[0-9a-f]{40}", settings.code_version):
            raise TrainingError(
                "Build provenance is unavailable. Rebuild with MM_CODE_VERSION set to the Git SHA "
                "using the documented startup commands, then retry training."
            )
        assert dataset.profile and dataset.canonical_object_key
        validate_configuration(dataset.profile, config, settings)
        content = store.get(dataset.canonical_object_key)
        if sha256(content).hexdigest() != dataset.canonical_sha256:
            raise TrainingError(
                "Canonical dataset integrity check failed. Upload and validate the baseline again."
            )
        frame = pd.read_parquet(BytesIO(content))
        names = {c["feature_id"]: c["name"] for c in dataset.profile["columns"]}
        types = {names[f["feature_id"]]: f["type"] for f in config["features"]}
        target = names[config["target_id"]]
        y = frame[target].map(lambda x: str(x).strip())
        pipeline, results, reference, membership = train(
            frame[list(types)],
            y,
            np.asarray(frame["__mm_row_id"]),
            config,
            types,
            lambda stage: queue.stage(job, stage),
        )
        queue.stage(job, "PERSISTING")
        payload = dump(pipeline)
        digest = sha256(payload).hexdigest()
        manifest = {
            "artifact_version": ARTIFACT_VERSION,
            "methodology_version": METHODOLOGY_VERSION,
            "code_version": settings.code_version,
            "code_dirty": settings.code_dirty,
            "code_source_sha256": sha256(
                b"".join(
                    p.relative_to(Path("backend")).as_posix().encode() + p.read_bytes()
                    for p in sorted(Path("backend/app").rglob("*.py"))
                )
            ).hexdigest(),
            "project_id": str(project.id),
            "snapshot_id": str(snapshot_id),
            "target": target,
            "positive_class": config["positive_class"],
            "feature_names": list(types),
            "feature_types": types,
            "baseline_class_list": results["class_order"],
            "class_order": results["class_order"],
            "classifier": config["classifier"],
            "class_weighting": config["weighting"],
            "random_seed": 42,
            "artifact_sha256": digest,
            "canonical_sha256": dataset.canonical_sha256,
            "canonical_schema_version": dataset.canonical_schema_version,
            "configuration_fingerprint": job.params["fingerprint"],
            "created_at": datetime.now(UTC).isoformat(),
            **environment(),
        }
        store.put(prefix + "/pipeline.joblib", payload)
        # Verify reload before publication; no API process imports or loads joblib.
        loaded = load_trusted(store, prefix + "/pipeline.joblib", digest, manifest)
        raw_reference = reference[list(types)]
        if not np.array_equal(
            loaded.predict_proba(raw_reference), pipeline.predict_proba(raw_reference)
        ):
            raise TrainingError("Artifact reload verification failed. No baseline was established.")
        objects = {
            "manifest.json": json.dumps(manifest, sort_keys=True).encode(),
            "results.json": json.dumps(results, allow_nan=False, sort_keys=True).encode(),
            "heldout.parquet": reference.to_parquet(index=False),
            "split.parquet": membership.to_parquet(index=False),
        }
        for name, data in objects.items():
            store.put(prefix + "/" + name, data)
        results["manifest"] = manifest
        results["artifact_hashes"] = {
            name: sha256(data).hexdigest() for name, data in objects.items()
        }
        results["features"] = [
            {**c, "frozen_type": types[c["name"]]}
            for c in dataset.profile["columns"]
            if c["name"] in types
        ]
    except OwnershipLost:
        store.delete_prefix(prefix)
        raise
    except Exception as exc:
        store.delete_prefix(prefix)
        error = (
            str(exc)
            if isinstance(exc, TrainingError)
            else (
                "Baseline training failed. Your dataset and configuration remain safe. "
                "Review the data and retry training."
            )
        )

    def persist(session: Session) -> None:
        current = session.scalar(
            select(Project).where(Project.id == job.project_id).with_for_update()
        )
        if (
            not current
            or current.state != "DRAFT"
            or current.deletion_pending
            or fingerprint(dataset.canonical_sha256 or "", current.configuration)
            != job.params["fingerprint"]
        ):
            raise OwnershipLost
        snapshot = session.get(BaselineSnapshot, snapshot_id)
        if not snapshot or snapshot.status != "TRAINING":
            raise OwnershipLost
        snapshot.status = "FAILED" if error else "TRAINED"
        snapshot.error_message = error
        if error:
            current_job = session.get(Job, job.id)
            assert current_job
            current_job.error_message = error
        else:
            snapshot.results = results
            snapshot.development_count = results["development_count"]
            snapshot.heldout_count = results["heldout_count"]
            snapshot.split_seed = 42
            snapshot.split_membership_object_key = prefix + "/split.parquet"
            snapshot.heldout_reference_object_key = prefix + "/heldout.parquet"
            session.add(
                ModelArtifact(
                    project_id=current.id,
                    snapshot_id=snapshot.id,
                    storage_key=prefix + "/pipeline.joblib",
                    sha256=digest,
                    environment_manifest=manifest,
                )
            )

    return persist, prefix, error is not None
