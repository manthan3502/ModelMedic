from datetime import UTC, datetime
from hashlib import sha256
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError

from backend.app.db.models import Dataset, Job, ModelArtifact, MonitoringRun, RunFeatureResult
from backend.app.domain.jobs import OwnershipLost
from backend.app.jobs.monitoring import analysis_result
from backend.app.jobs.worker import run_once
from backend.tests.integration.test_setup import setup_client as setup_client
from backend.tests.integration.test_training import trained

pytestmark = pytest.mark.integration


def established(setup_client):
    client, _, _, _ = setup_client
    project_id, p, _ = trained(setup_client)
    response = client.post(
        f"/api/v1/projects/{project_id}/establish", json={"snapshot_id": p["baseline"]["id"]}
    )
    assert response.status_code == 200
    return project_id, p["baseline"]["id"]


def new_run(client, project_id, name="Synthetic current", date="2026-10-04"):
    response = client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"name": name, "monitoring_date": date, "notes": "Synthetic only"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def current_csv(rows=100, header="number,category,extra", row=lambda i: f"{i + 100},new,ignored"):
    return (header + "\n" + "".join(row(i) + "\n" for i in range(rows))).encode()


def uploaded(setup_client, project_id, content=None):
    client, queue, store, settings = setup_client
    run_id = new_run(client, project_id)
    response = client.post(
        f"/api/v1/runs/{run_id}/upload",
        content=content or current_csv(),
        headers={"Content-Type": "text/csv", "X-Filename": "../../secret.csv"},
    )
    assert response.status_code == 202
    assert run_once(queue, uuid4(), 1, store, settings)
    return run_id, client.get(f"/api/v1/runs/{run_id}").json()


def test_mode_a_lifecycle_stages_refs_frozen_and_atomic_publication(setup_client):
    client, queue, store, settings = setup_client
    project_id, snapshot_id = established(setup_client)
    run_id, r = uploaded(setup_client, project_id)
    assert r["state"] == "READY" and r["mode"] == "A"
    assert r["baseline_snapshot_id"] == snapshot_id and r["row_count"] == 100
    report = r["dataset"]["validation_report"]
    assert report["ignored_extra_columns"] == ["extra"] and report["new_categories"][0][
        "categories"
    ] == ["new"]
    assert report["coercions"][0]["observed_count"] == 100
    with queue.sessions() as session:
        artifact = session.scalar(select(ModelArtifact))
        original_hash = sha256(store.get(artifact.storage_key)).hexdigest()
    for endpoint in (
        "summary",
        "features",
        "predictions",
        "confidence",
        "metrics",
        "calibration",
        "errors",
        "slices",
    ):
        assert client.get(f"/api/v1/runs/{run_id}/{endpoint}").status_code == 409
    assert client.post(f"/api/v1/runs/{run_id}/analyze").status_code == 202
    assert client.post(f"/api/v1/runs/{run_id}/analyze").status_code == 409
    with patch.object(queue, "stage", wraps=queue.stage) as stage:
        assert run_once(queue, uuid4(), 1, store, settings)
    assert [c.args[1] for c in stage.call_args_list] == [
        "VALIDATING",
        "PREDICTING",
        "DATA_DRIFT",
        "MISSINGNESS",
        "PREDICTION_DRIFT",
        "CONFIDENCE",
        "PERSISTING",
    ]
    r = client.get(f"/api/v1/runs/{run_id}").json()
    assert r["state"] == "ANALYZED" and r["job"]["stage"] == "COMPLETE"
    results = client.get(f"/api/v1/runs/{run_id}/summary").json()
    assert results["features"][0]["distribution"]["baseline_n"] == 200
    assert results["predictions"]["baseline_n"] == 40
    assert results["confidence"]["baseline_n"] == 40
    assert results["baseline_snapshot_id"] == snapshot_id
    assert client.get(f"/api/v1/runs/{run_id}/features/f000").status_code == 200
    assert client.get(f"/api/v1/runs/{run_id}/features/raw-header").status_code == 404
    for endpoint in ("metrics", "calibration", "errors", "slices"):
        data = client.get(f"/api/v1/runs/{run_id}/{endpoint}").json()
        assert data["status"] == "UNAVAILABLE" and "ground-truth" in data["reason"]
    assert client.post(f"/api/v1/runs/{run_id}/analyze").status_code == 409
    assert (
        client.post(
            f"/api/v1/runs/{run_id}/upload",
            content=current_csv(),
            headers={"Content-Type": "text/csv"},
        ).status_code
        == 409
    )
    with queue.sessions() as session:
        run = session.get(MonitoringRun, UUID(run_id))
        assert sha256(store.get(run.result_object_key)).hexdigest() == r["result_sha256"]
        assert sha256(store.get(artifact.storage_key)).hexdigest() == original_hash
        assert len(list(session.scalars(select(RunFeatureResult)))) == 2
    assert client.get(f"/api/v1/runs/{run_id}/summary").json() == results
    with queue.sessions() as session:
        existing = session.scalar(select(RunFeatureResult))
        values = {c.name: getattr(existing, c.name) for c in RunFeatureResult.__table__.columns}
    values["feature_id"] = "f099"
    with pytest.raises(DBAPIError), queue.sessions.begin() as session:
        session.add(RunFeatureResult(**values))
    for model, changes in [
        (MonitoringRun, {"results": {}}),
        (MonitoringRun, {"baseline_snapshot_id": uuid4()}),
        (RunFeatureResult, {"evidence": {}}),
    ]:
        with pytest.raises(DBAPIError), queue.sessions.begin() as session:
            session.execute(update(model).values(**changes))
    assert client.delete(f"/api/v1/runs/{run_id}").status_code == 204
    with queue.sessions() as session:
        assert session.scalar(select(RunFeatureResult)) is None
        assert session.scalar(select(Dataset).where(Dataset.role == "CURRENT")) is None
    assert (
        client.get(f"/api/v1/projects/{project_id}").json()["baseline"]["status"] == "ESTABLISHED"
    )


@pytest.mark.parametrize(
    "content,message",
    [
        (current_csv(49), "at least 50"),
        (current_csv(header="category", row=lambda _: "new"), "features are missing"),
        (current_csv(row=lambda _: "NA,new,ignored"), "numeric"),
        (
            current_csv(
                header="number,category,target", row=lambda i: f"1,a,{'class0' if i else ''}"
            ),
            "absent",
        ),
        (
            current_csv(header="number,category,target", row=lambda _: "1,a,unknown"),
            "Unknown target",
        ),
        (current_csv(header="number,category,__mm_bad"), "reserved"),
    ],
)
def test_current_validation_blocks_without_silent_mode_fallback(setup_client, content, message):
    project_id, _ = established(setup_client)
    _, r = uploaded(setup_client, project_id, content)
    assert r["state"] == "VALIDATION_FAILED" and r["mode"] is None
    assert message in r["dataset"]["validation_report"]["errors"][0]


def test_mode_b_recognized_but_not_analyzed_and_categorical_not_reinferred(setup_client):
    client, _, _, _ = setup_client
    project_id, _ = established(setup_client)
    run_id, r = uploaded(
        setup_client,
        project_id,
        current_csv(header="number,category,target", row=lambda _: "1,001, class0 "),
    )
    assert r["mode"] == "B" and r["state"] == "READY"
    assert r["dataset"]["validation_report"]["new_categories"][0]["categories"] == ["001"]
    assert client.post(f"/api/v1/runs/{run_id}/analyze").status_code == 409


def test_monitoring_finalization_fenced_failure_no_partial_results(setup_client):
    client, queue, store, settings = setup_client
    project_id, _ = established(setup_client)
    run_id, _ = uploaded(setup_client, project_id)
    client.post(f"/api/v1/runs/{run_id}/analyze")
    job = queue.claim()
    persist, prefix, failed = analysis_result(queue, job, store, settings)
    assert not failed
    assert client.get(f"/api/v1/runs/{run_id}/summary").status_code == 409
    with queue.sessions.begin() as session:
        session.execute(update(Job).where(Job.id == job.id).values(owner_token=uuid4()))
    with pytest.raises(OwnershipLost):
        queue.finalize(job, result=persist)
    with queue.sessions() as session:
        assert session.get(MonitoringRun, UUID(run_id)).results is None
        assert session.scalar(select(RunFeatureResult)) is None
    store.delete_prefix(prefix)


def test_integrity_failure_failed_job_exposes_no_results(setup_client):
    client, queue, store, settings = setup_client
    project_id, _ = established(setup_client)
    run_id, _ = uploaded(setup_client, project_id)
    with queue.sessions.begin() as session:
        session.scalar(select(ModelArtifact)).sha256 = "0" * 64
    client.post(f"/api/v1/runs/{run_id}/analyze")
    run_once(queue, uuid4(), 1, store, settings)
    r = client.get(f"/api/v1/runs/{run_id}").json()
    assert r["job"]["state"] == "FAILED" and r["state"] == "READY"
    assert client.get(f"/api/v1/runs/{run_id}/summary").status_code == 409
    with queue.sessions() as session:
        assert session.scalar(select(RunFeatureResult)) is None


def test_result_storage_failure_publishes_no_scientific_rows(setup_client):
    client, queue, store, settings = setup_client
    project_id, _ = established(setup_client)
    run_id, _ = uploaded(setup_client, project_id)
    client.post(f"/api/v1/runs/{run_id}/analyze")
    with patch.object(type(store), "put", side_effect=OSError("controlled storage failure")):
        run_once(queue, uuid4(), 1, store, settings)
    run = client.get(f"/api/v1/runs/{run_id}").json()
    assert run["job"]["state"] == "FAILED" and run["state"] == "READY"
    assert client.get(f"/api/v1/runs/{run_id}/summary").status_code == 409
    with queue.sessions() as session:
        assert session.scalar(select(RunFeatureResult)) is None


def test_history_order_stream_limit_and_recoverable_delete(setup_client):
    client, queue, store, settings = setup_client
    project_id, _ = established(setup_client)
    ids = [
        new_run(client, project_id, str(i), date)
        for i, date in enumerate(["2026-01-01", "2026-02-01", "2026-01-01"])
    ]
    with queue.sessions.begin() as session:
        session.execute(update(MonitoringRun).values(created_at=datetime(2026, 1, 1, tzinfo=UTC)))
    history = client.get(f"/api/v1/projects/{project_id}/runs").json()
    assert [r["id"] for r in history] == [ids[1], *sorted([ids[0], ids[2]], reverse=True)]
    # Real streaming body beyond the default configured cap is rejected and never published.
    response = client.post(
        f"/api/v1/runs/{ids[0]}/upload",
        content=iter([b"x" * (settings.upload_max_bytes // 2 + 1)] * 2),
        headers={"Content-Type": "text/csv"},
    )
    assert response.status_code == 413
    assert client.get(f"/api/v1/runs/{ids[0]}").json()["dataset"] is None
    with patch.object(type(store), "delete_prefix", side_effect=OSError("controlled")):
        assert client.delete(f"/api/v1/runs/{ids[0]}").status_code == 503
    assert client.get(f"/api/v1/runs/{ids[0]}").json()["deletion_pending"]
    assert client.delete(f"/api/v1/runs/{ids[0]}").status_code == 204
