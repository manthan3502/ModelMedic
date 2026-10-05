import json
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.db.models import Job, MonitoringRun, Project, RunReport
from backend.app.main import create_app
from backend.app.services.demo import REGISTRY_KEY, VERSIONS
from backend.tests.integration.test_diagnostics import analyzed
from backend.tests.integration.test_labeled import labeled_baseline
from backend.tests.integration.test_setup import setup_client as setup_client

pytestmark = pytest.mark.integration


def test_demo_reads_only_seed_and_never_creates_results(setup_client):
    full, queue, store, settings = setup_client
    project_id, _ = labeled_baseline(setup_client)
    run_id = analyzed(setup_client, project_id)
    hidden = full.post("/api/v1/projects", json={"name": "Not a public demo project"}).json()
    report = full.get(f"/api/v1/runs/{run_id}/report").json()
    summary = full.get(f"/api/v1/runs/{run_id}/summary").json()
    with queue.sessions() as session:
        jobs = list(session.scalars(select(Job).where(Job.project_id == UUID(project_id))))
        before = [session.scalar(select(func.count()).select_from(t)) for t in (Job, RunReport)]
    store.put(
        REGISTRY_KEY,
        json.dumps(
            {
                "versions": VERSIONS,
                "synthetic_only": True,
                "projects": [project_id],
                "runs": [run_id],
                "slices": [],
                "jobs": [str(j.id) for j in jobs],
            }
        ).encode(),
    )
    with TestClient(create_app(settings.model_copy(update={"deployment_mode": "demo"}))) as demo:
        assert [p["id"] for p in demo.get("/api/v1/projects").json()] == [project_id]
        assert demo.get(f"/api/v1/projects/{hidden['id']}").status_code == 404
        assert demo.get(f"/api/v1/runs/{run_id}/summary").json() == summary
        assert demo.get(f"/api/v1/runs/{run_id}/report").json() == report
        assert demo.get("/api/v1/health/ready").status_code == 200
        for path in (
            "/projects",
            f"/projects/{project_id}/train",
            f"/projects/{project_id}/runs",
            f"/runs/{run_id}/upload",
            f"/runs/{run_id}/analyze",
            f"/runs/{run_id}/slices",
            f"/runs/{run_id}",
        ):
            assert demo.post("/api/v1" + path, json={}).status_code == 403
            assert demo.delete("/api/v1" + path).status_code == 403
    with queue.sessions() as session:
        assert before == [
            session.scalar(select(func.count()).select_from(t)) for t in (Job, RunReport)
        ]
        session.delete(session.get(RunReport, UUID(run_id)))
        session.commit()
    with TestClient(create_app(settings.model_copy(update={"deployment_mode": "demo"}))) as demo:
        assert demo.get(f"/api/v1/runs/{run_id}/report").status_code == 409
        # A draft added later in Full Mode must never leak through project history.
        extra = full.post(
            f"/api/v1/projects/{project_id}/runs",
            json={"name": "Unpublished private draft", "monitoring_date": "2026-10-05"},
        )
        assert extra.status_code == 201
        assert demo.get(f"/api/v1/projects/{project_id}/runs").status_code == 503
        assert demo.get("/api/v1/health/ready").status_code == 503
        with queue.sessions.begin() as session:
            session.get(MonitoringRun, UUID(extra.json()["id"])).deletion_pending = True
        # Failed cleanup must not make an unpublished row disappear from the scope check.
        assert demo.get(f"/api/v1/projects/{project_id}/runs").status_code == 503
        assert demo.get(f"/api/v1/projects/{project_id}").status_code == 503
    with queue.sessions() as session:
        assert session.get(RunReport, UUID(run_id)) is None
        assert session.get(MonitoringRun, UUID(run_id)).state == "ANALYZED"
        assert session.get(Project, UUID(project_id)).state != "DRAFT"
