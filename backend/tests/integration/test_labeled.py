import json
from hashlib import sha256
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError

from backend.app.db.models import (
    BaselineSnapshot,
    Job,
    ModelArtifact,
    MonitoringRun,
    RunCalibrationResult,
    RunErrorResult,
    RunMetric,
    RunReport,
)
from backend.app.domain.jobs import OwnershipLost
from backend.app.jobs.monitoring import analysis_result
from backend.app.jobs.worker import run_once
from backend.tests.integration.test_monitoring import uploaded
from backend.tests.integration.test_setup import choice, validated
from backend.tests.integration.test_setup import setup_client as setup_client

pytestmark = pytest.mark.integration


def labeled_baseline(setup_client, classes=2):
    client, queue, store, settings = setup_client
    content = (
        "number,category,target,excluded_id\n"
        + "".join(
            f"{i},category{i % 3},class{i % classes},synthetic-private-{i}\n"
            for i in range(classes * 150)
        )
    ).encode()
    project_id, p = validated(setup_client, content)
    config = choice(p, positive_class="class0" if classes == 2 else None)
    assert (
        client.put(f"/api/v1/projects/{project_id}/configuration", json=config).status_code == 200
    )
    assert client.post(f"/api/v1/projects/{project_id}/train").status_code == 202
    assert run_once(queue, uuid4(), 1, store, settings)
    p = client.get(f"/api/v1/projects/{project_id}").json()
    assert p["job"]["state"] == "SUCCEEDED", p["job"]
    snapshot = p["baseline"]
    assert (
        client.post(
            f"/api/v1/projects/{project_id}/establish", json={"snapshot_id": snapshot["id"]}
        ).status_code
        == 200
    )
    return project_id, snapshot


def labeled_current(classes=2, absent=False):
    return (
        "number,category,target,excluded_id\n"
        + "".join(
            f"{i + 1000},<script>untrusted</script>, class{1 if absent else i % classes} ,"
            f"synthetic-secret-{i}\n"
            for i in range(120)
        )
    ).encode()


@pytest.mark.parametrize("classes,absent", [(2, False), (3, False), (2, True), (3, True)])
def test_mode_b_complete_atomic_lifecycle_privacy_and_immutability(setup_client, classes, absent):
    client, queue, store, settings = setup_client
    project_id, snapshot = labeled_baseline(setup_client, classes)
    baseline_before = json.dumps(snapshot["results"], sort_keys=True)
    with queue.sessions() as session:
        model = session.scalar(select(ModelArtifact))
        model_hash = sha256(store.get(model.storage_key)).hexdigest()
    run_id, run = uploaded(setup_client, project_id, labeled_current(classes, absent))
    assert run["mode"] == "B" and run["state"] == "READY"
    assert run["dataset"]["validation_report"]["ignored_extra_columns"] == ["excluded_id"]
    for endpoint in ("summary", "metrics", "calibration", "errors", "errors/examples?view=fp"):
        assert client.get(f"/api/v1/runs/{run_id}/{endpoint}").status_code == 409
    assert client.post(f"/api/v1/runs/{run_id}/analyze").status_code == 202
    assert client.post(f"/api/v1/runs/{run_id}/analyze").status_code == 409
    with patch.object(queue, "stage", wraps=queue.stage) as stages:
        assert run_once(queue, uuid4(), 1, store, settings)
    assert [c.args[1] for c in stages.call_args_list] == [
        "VALIDATING",
        "PREDICTING",
        "DATA_DRIFT",
        "MISSINGNESS",
        "PREDICTION_DRIFT",
        "CONFIDENCE",
        "PERFORMANCE",
        "CALIBRATION",
        "PERSISTING",
    ]
    run = client.get(f"/api/v1/runs/{run_id}").json()
    assert run["state"] == "ANALYZED" and run["job"]["stage"] == "COMPLETE"
    result = client.get(f"/api/v1/runs/{run_id}/summary").json()
    assert result["mode"] == "B"
    assert result["calibration"]["baseline"] == snapshot["results"]["calibration"]
    assert client.get(f"/api/v1/runs/{run_id}/metrics").json() == result["performance"]
    assert client.get(f"/api/v1/runs/{run_id}/calibration").json() == result["calibration"]
    assert client.get(f"/api/v1/runs/{run_id}/errors").json() == result["errors"]
    assert client.get(f"/api/v1/runs/{run_id}/slices").json()["status"] == "AVAILABLE"
    assert len(result["performance"]["absent_classes"]) == (classes - 1 if absent else 0)
    assert "uncertainty intervals" in result["performance"]["limitation"]
    view = "fp" if classes == 2 else result["errors"]["current"]["common_pairs"][0]["view"]
    examples = client.get(f"/api/v1/runs/{run_id}/errors/examples?view={view}").json()
    assert examples["features"] == ["number", "category"]
    assert len(examples["rows"]) <= 50
    assert "excluded_id" not in json.dumps(examples) and "synthetic-secret" not in json.dumps(
        examples
    )
    assert all(set(r["features"]) == {"number", "category"} for r in examples["rows"])
    assert all(isinstance(r["row_id"], int) for r in examples["rows"])
    with queue.sessions() as session:
        frozen_run = session.get(MonitoringRun, UUID(run_id))
        assert json.loads(store.get(frozen_run.result_object_key)) == result
        assert sha256(store.get(frozen_run.result_object_key)).hexdigest() == run["result_sha256"]
        assert sha256(store.get(model.storage_key)).hexdigest() == model_hash
        assert session.scalar(select(RunMetric)) and session.scalar(select(RunCalibrationResult))
        evidence = session.scalar(select(RunErrorResult)).evidence
        assert "synthetic-secret" not in json.dumps(evidence) and "<script>" not in json.dumps(
            evidence
        )
    assert client.get(f"/api/v1/runs/{run_id}/summary").json() == result
    assert (
        json.dumps(
            client.get(f"/api/v1/projects/{project_id}").json()["baseline"]["results"],
            sort_keys=True,
        )
        == baseline_before
    )
    for cls in (RunMetric, RunCalibrationResult, RunErrorResult):
        with queue.sessions() as session:
            entry = session.scalar(select(cls))
            original = {c.name: getattr(entry, c.name) for c in cls.__table__.columns}
        with pytest.raises(DBAPIError), queue.sessions.begin() as session:
            session.execute(update(cls).values(**original))
        with pytest.raises(DBAPIError), queue.sessions.begin() as session:
            session.add(cls(**original))
    assert client.post(f"/api/v1/runs/{run_id}/analyze").status_code == 409
    assert client.delete(f"/api/v1/runs/{run_id}").status_code == 204
    with queue.sessions() as session:
        for cls in (RunMetric, RunCalibrationResult, RunErrorResult):
            assert session.scalar(select(cls)) is None
        assert session.get(BaselineSnapshot, UUID(snapshot["id"])).status == "ESTABLISHED"


def test_mode_b_fenced_finalization_rolls_back_every_labeled_table(setup_client):
    client, queue, store, settings = setup_client
    project_id, _ = labeled_baseline(setup_client)
    run_id, _ = uploaded(setup_client, project_id, labeled_current())
    client.post(f"/api/v1/runs/{run_id}/analyze")
    job = queue.claim()
    publish, prefix, failed = analysis_result(queue, job, store, settings)
    assert not failed
    assert client.get(f"/api/v1/runs/{run_id}/metrics").status_code == 409
    with queue.sessions.begin() as session:
        session.execute(update(Job).where(Job.id == job.id).values(owner_token=uuid4()))
    with pytest.raises(OwnershipLost):
        queue.finalize(job, result=publish)
    with queue.sessions() as session:
        assert session.get(MonitoringRun, UUID(run_id)).results is None
        for cls in (RunMetric, RunCalibrationResult, RunErrorResult, RunReport):
            assert session.scalar(select(cls)) is None
    store.delete_prefix(prefix)


def test_mode_b_historical_result_integrity_failure_exposes_nothing(setup_client):
    client, queue, store, settings = setup_client
    project_id, snapshot = labeled_baseline(setup_client)
    run_id, _ = uploaded(setup_client, project_id, labeled_current())
    # Corrupt only this disposable fixture's private artifact, not a user baseline.
    with queue.sessions() as session:
        prefix = session.get(BaselineSnapshot, UUID(snapshot["id"])).artifact_prefix
    store.delete(prefix + "/results.json")
    store.put(prefix + "/results.json", b"{}")
    client.post(f"/api/v1/runs/{run_id}/analyze")
    assert run_once(queue, uuid4(), 1, store, settings)
    run = client.get(f"/api/v1/runs/{run_id}").json()
    assert run["job"]["state"] == "FAILED" and run["state"] == "READY"
    for endpoint in ("summary", "metrics", "calibration", "errors"):
        assert client.get(f"/api/v1/runs/{run_id}/{endpoint}").status_code == 409
    with queue.sessions() as session:
        assert session.scalar(select(RunMetric)) is None


def test_error_example_source_hash_and_view_guard(setup_client):
    client, queue, store, settings = setup_client
    project_id, _ = labeled_baseline(setup_client)
    run_id, _ = uploaded(setup_client, project_id, labeled_current())
    client.post(f"/api/v1/runs/{run_id}/analyze")
    run_once(queue, uuid4(), 1, store, settings)
    assert (
        client.get(f"/api/v1/runs/{run_id}/errors/examples?view=../../private").status_code == 404
    )
    from backend.app.db.models import Dataset

    with queue.sessions() as session:
        run = session.get(MonitoringRun, UUID(run_id))
        dataset = session.get(Dataset, run.dataset_id)
    store.delete(dataset.canonical_object_key)
    store.put(dataset.canonical_object_key, b"corrupt")
    assert client.get(f"/api/v1/runs/{run_id}/errors/examples?view=fp").status_code == 409
