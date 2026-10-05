"""Explicit read surface and private registry for pipeline-generated synthetic seeds.

The registry is operator-owned, never accepted from an HTTP client. A missing or
incompatible registry closes dataset reads; health and runtime remain inspectable.
"""

import json
import re
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.app.db.models import BaselineSnapshot, Job, MonitoringRun, Project, SliceAnalysis
from backend.app.domain.datasets import SCHEMA_VERSION
from backend.app.science.baseline import ARTIFACT_VERSION
from backend.app.science.baseline import METHODOLOGY_VERSION as BASELINE_VERSION
from backend.app.science.monitoring import METHODOLOGY_VERSION as MONITORING_VERSION
from backend.app.science.slices import SLICE_METHODOLOGY_VERSION
from backend.app.services.reporting import REPORT_TEMPLATE_VERSION
from backend.app.storage.base import ArtifactStore

REGISTRY_KEY = "demo/seed.json"
DEMO_MESSAGE = (
    "This action is disabled in the public portfolio demo. "
    "Run ModelMedic locally to upload your own data."
)
VERSIONS = {
    "seed": "synthetic-v1",
    "canonical": SCHEMA_VERSION,
    "baseline": BASELINE_VERSION,
    "pipeline": ARTIFACT_VERSION,
    "monitoring": MONITORING_VERSION,
    "slices": SLICE_METHODOLOGY_VERSION,
    "report": REPORT_TEMPLATE_VERSION,
}
PUBLIC_READS = {
    "/api/v1/runtime",
    "/api/v1/health/live",
    "/api/v1/health/ready",
    "/api/v1/health/worker",
}
# New endpoints are denied until explicitly reviewed and listed here.
SCOPED_READS = (
    (r"/api/v1/projects", None),
    (r"/api/v1/projects/([^/]+)", "projects"),
    (r"/api/v1/projects/([^/]+)/baseline/(summary|metrics|calibration|importance)", "projects"),
    (r"/api/v1/projects/([^/]+)/(runs|trends)", "projects"),
    (r"/api/v1/runs/([^/]+)", "runs"),
    (
        r"/api/v1/runs/([^/]+)/(summary|features|predictions|confidence|metrics|calibration|errors|slices|report|presentation)",
        "runs",
    ),
    (r"/api/v1/runs/([^/]+)/features/f[0-9]+", "runs"),
    (r"/api/v1/runs/([^/]+)/errors/examples", "runs"),
    (r"/api/v1/runs/([^/]+)/slices/([^/]+)", "runs"),
    (r"/api/v1/jobs/([^/]+)", "jobs"),
)


def registry(store: ArtifactStore) -> dict[str, Any]:
    try:
        data: dict[str, Any] = json.loads(store.get(REGISTRY_KEY))
        if data["versions"] != VERSIONS or data["synthetic_only"] is not True:
            raise ValueError("Incompatible demo seed")
        for key in ("projects", "runs", "jobs", "slices"):
            if not isinstance(data[key], list):
                raise ValueError("Invalid demo registry")
            for value in data[key]:
                if str(UUID(value)) != value:
                    raise ValueError("Invalid seed identifier")
        if not data["projects"] or not data["runs"]:
            raise ValueError("Empty demo registry")
        return data
    except (OSError, ValueError, KeyError, TypeError):
        raise HTTPException(
            503,
            "The synthetic demo seed is unavailable or incompatible. Regenerate it in Full Mode.",
        ) from None


def authorize_read(path: str, store: ArtifactStore) -> None:
    path = path.rstrip("/")
    if path in PUBLIC_READS:
        return
    for pattern, scope in SCOPED_READS:
        match = re.fullmatch(pattern, path)
        if match:
            data = registry(store)
            if scope and match[1] not in data[scope]:
                raise HTTPException(404, "This resource is not part of the synthetic demo.")
            if "/slices/" in path and match[2] not in data["slices"]:
                raise HTTPException(404, "This slice is not part of the synthetic demo.")
            return
    raise HTTPException(403, "This read route is not enabled in the public portfolio demo.")


def validate_seed_scope(session: Session, data: dict[str, Any]) -> None:
    """Reject a seed project modified later in Full Mode, rather than leak new rows."""
    project_ids = [UUID(p) for p in data["projects"]]
    run_ids = [UUID(r) for r in data["runs"]]
    checks = {
        "projects": select(Project.id).where(
            Project.id.in_(project_ids), Project.deletion_pending.is_(False)
        ),
        "runs": select(MonitoringRun.id).where(MonitoringRun.project_id.in_(project_ids)),
        "jobs": select(Job.id).where(Job.project_id.in_(project_ids)),
        "slices": select(SliceAnalysis.id).where(SliceAnalysis.run_id.in_(run_ids)),
    }
    for key, statement in checks.items():
        if {str(v) for v in session.scalars(statement)} != set(data[key]):
            raise HTTPException(503, "The demo seed scope changed. Regenerate it in Full Mode.")
    if session.scalar(
        select(MonitoringRun.id)
        .where(
            MonitoringRun.id.in_(run_ids),
            or_(MonitoringRun.state != "ANALYZED", MonitoringRun.deletion_pending.is_(True)),
        )
        .limit(1)
    ):
        raise HTTPException(503, "The demo analysis is unavailable. Regenerate it in Full Mode.")
    established = set(
        session.scalars(
            select(BaselineSnapshot.project_id).where(
                BaselineSnapshot.project_id.in_(project_ids),
                BaselineSnapshot.status == "ESTABLISHED",
            )
        )
    )
    if established != set(project_ids):
        raise HTTPException(503, "The demo baseline is unavailable. Regenerate it in Full Mode.")
