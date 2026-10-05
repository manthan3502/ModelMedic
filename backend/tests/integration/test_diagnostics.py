import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from hashlib import sha256
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError

from backend.app.db.models import Dataset, Job, MonitoringRun, RunReport, SliceAnalysis, SliceResult
from backend.app.domain.jobs import OwnershipLost
from backend.app.jobs.slices import slice_result
from backend.app.jobs.worker import run_once
from backend.app.services.reporting import REPORT_LIMITATIONS
from backend.app.services.trends import METHODOLOGY_CAUTION
from backend.tests.integration.test_labeled import labeled_baseline, labeled_current
from backend.tests.integration.test_monitoring import current_csv, uploaded
from backend.tests.integration.test_setup import setup_client as setup_client

pytestmark = pytest.mark.integration


def analyzed(setup_client, project_id, content=None):
    client, queue, store, settings = setup_client
    run_id, _ = uploaded(setup_client, project_id, content or labeled_current())
    assert client.post(f"/api/v1/runs/{run_id}/analyze").status_code == 202
    assert run_once(queue, uuid4(), 1, store, settings)
    assert client.get(f"/api/v1/runs/{run_id}").json()["state"] == "ANALYZED"
    return run_id


def request_slice(client, run_id, feature="f001"):
    return client.post(f"/api/v1/runs/{run_id}/slices", json={"feature_id": feature})


def sliced_current():
    categories = [""] * 10 + ["null"] * 29 + [" raw "] * 31 + ["raw"] * 50
    return (
        "number,category,target,excluded_id\n"
        + "".join(
            f"{i + 1000},{c},class{i % 2},synthetic-secret-{i}\n" for i, c in enumerate(categories)
        )
    ).encode()


def test_slice_job_idempotence_concurrency_thresholds_additive_immutability_and_cascade(
    setup_client,
):
    client, queue, store, settings = setup_client
    project_id, snapshot = labeled_baseline(setup_client)
    run_id = analyzed(setup_client, project_id, sliced_current())
    summary = client.get(f"/api/v1/runs/{run_id}/summary").json()
    report = client.get(f"/api/v1/runs/{run_id}/report").json()["report"]
    with queue.sessions() as session:
        saved = session.get(MonitoringRun, UUID(run_id))
        object_before = store.get(saved.result_object_key)
    assert request_slice(client, run_id, "f000").status_code == 422
    assert request_slice(client, run_id, "f002").status_code == 422
    assert request_slice(client, run_id, "f003").status_code == 422
    with ThreadPoolExecutor(max_workers=4) as pool:
        requests = list(pool.map(lambda _: request_slice(client, run_id), range(4)))
    assert all(r.status_code == 202 for r in requests)
    assert len({r.json()["id"] for r in requests}) == 1
    analysis_id = requests[0].json()["id"]
    assert requests[0].json()["rows"] == []
    assert client.delete(f"/api/v1/runs/{run_id}").status_code == 409
    with queue.sessions() as session:
        assert (
            session.scalar(
                select(func.count()).select_from(Job).where(Job.job_type == "SLICE_ANALYZE")
            )
            == 1
        )
    with patch.object(queue, "stage", wraps=queue.stage) as stages:
        assert run_once(queue, uuid4(), 1, store, settings)
    assert [c.args[1] for c in stages.call_args_list] == [
        "VALIDATING",
        "PREDICTING",
        "SLICES",
        "PERSISTING",
    ]
    ready = request_slice(client, run_id).json()
    assert ready["id"] == analysis_id and ready["status"] == "READY"
    assert ready["job"]["state"] == "SUCCEEDED"
    assert [r["slice_value"] for r in ready["rows"]] == [None, None, " raw ", "null", "raw"]
    for r in ready["rows"]:
        assert sum(r["class_support"].values()) == r["row_count"]
        if r["row_count"] < 30:
            assert (
                r["metrics"] == {}
                and r["reason"] == "Insufficient sample size for stable slice analysis."
            )
    assert ready["rows"][0]["row_count"] == 120
    assert "This is not a fairness audit." in ready["limitation"]
    with queue.sessions() as session:
        assert session.scalar(select(func.count()).select_from(SliceAnalysis)) == 1
        result = session.scalar(select(SliceResult))
        binding = result.slice_analysis_id, result.slice_key
    for cls, fields in [(SliceAnalysis, {"status": "PENDING"}), (SliceResult, {"row_count": 999})]:
        with pytest.raises(DBAPIError), queue.sessions.begin() as session:
            session.execute(update(cls).values(**fields))
    with pytest.raises(DBAPIError), queue.sessions.begin() as session:
        session.add(
            SliceResult(
                slice_analysis_id=binding[0],
                slice_key="new",
                slice_value="new",
                is_overall=False,
                row_count=30,
                class_support={},
                metrics={},
                status="AVAILABLE",
            )
        )
    assert client.get(f"/api/v1/runs/{run_id}/summary").json() == summary
    assert store.get(saved.result_object_key) == object_before
    assert sha256(object_before).hexdigest() == saved.result_sha256
    assert client.get(f"/api/v1/runs/{run_id}/report").json()["report"] == report
    assert client.get(f"/api/v1/runs/{run_id}/report").json()["slice_analyses"][0] == ready
    assert (
        client.get(f"/api/v1/projects/{project_id}").json()["baseline"]["results"]
        == snapshot["results"]
    )
    assert client.delete(f"/api/v1/runs/{run_id}").status_code == 204
    with queue.sessions() as session:
        for cls in (SliceAnalysis, SliceResult, RunReport):
            assert session.scalar(select(cls)) is None
        assert session.scalar(select(Job).where(Job.job_type == "SLICE_ANALYZE")) is None


def test_slice_mode_guard_and_pending_results(setup_client):
    client, _, _, _ = setup_client
    project_id, _ = labeled_baseline(setup_client)
    run_id, _ = uploaded(setup_client, project_id, current_csv())
    assert request_slice(client, run_id).status_code == 409
    client.post(f"/api/v1/runs/{run_id}/analyze")
    _, queue, store, settings = setup_client
    run_once(queue, uuid4(), 1, store, settings)
    assert client.get(f"/api/v1/runs/{run_id}/slices").json()["status"] == "UNAVAILABLE"
    assert request_slice(client, run_id).status_code == 409
    assert client.get(f"/api/v1/runs/{run_id}/report").status_code == 200


def test_slice_fenced_finalization_rolls_back_and_core_report_stays_unchanged(setup_client):
    client, queue, store, settings = setup_client
    project_id, _ = labeled_baseline(setup_client)
    run_id = analyzed(setup_client, project_id)
    before = client.get(f"/api/v1/runs/{run_id}/report").json()
    request_slice(client, run_id)
    job = queue.claim()
    publish, failed = slice_result(queue, job, store, settings)
    assert not failed
    with queue.sessions.begin() as session:
        session.execute(update(Job).where(Job.id == job.id).values(owner_token=uuid4()))
    with pytest.raises(OwnershipLost):
        queue.finalize(job, result=publish)
    with queue.sessions() as session:
        assert session.scalar(select(SliceResult)) is None
        assert session.scalar(select(SliceAnalysis)).status == "PENDING"
    assert client.get(f"/api/v1/runs/{run_id}/report").json() == before


def test_slice_source_hash_guard_publishes_no_rows(setup_client):
    client, queue, store, settings = setup_client
    project_id, _ = labeled_baseline(setup_client)
    run_id = analyzed(setup_client, project_id)
    with queue.sessions() as session:
        saved = session.get(MonitoringRun, UUID(run_id))
        dataset = session.get(Dataset, saved.dataset_id)
    store.delete(dataset.canonical_object_key)
    store.put(dataset.canonical_object_key, b"corrupt synthetic test only")
    request_slice(client, run_id)
    assert run_once(queue, uuid4(), 1, store, settings)
    response = client.get(f"/api/v1/runs/{run_id}/slices").json()["analyses"][0]
    assert response["status"] == "FAILED" and response["rows"] == []
    assert request_slice(client, run_id).json() == response
    assert client.get(f"/api/v1/runs/{run_id}").json()["state"] == "ANALYZED"


def test_report_finalization_versions_database_immutability_and_template_change(setup_client):
    client, queue, _, _ = setup_client
    project_id, _ = labeled_baseline(setup_client)
    run_id = analyzed(setup_client, project_id)
    with queue.sessions() as session:
        stored = session.get(RunReport, UUID(run_id))
        assert stored and stored.report_template_version == "report-v1"
        old_payload = copy.deepcopy(stored.payload)
        assert stored.generated_at.isoformat() == old_payload["generated_at"]
        assert stored.methodology_version == old_payload["methodology_version"]
        assert stored.code_version == old_payload["code_version"]
    with (
        patch("backend.app.services.reporting.REPORT_TEMPLATE_VERSION", "future-template"),
        patch(
            "backend.app.services.report_store.build_report",
            side_effect=AssertionError("Historical report must not regenerate"),
        ),
    ):
        assert client.get(f"/api/v1/runs/{run_id}/report").json()["report"] == old_payload
    with pytest.raises(DBAPIError), queue.sessions.begin() as session:
        session.execute(update(RunReport).values(payload={"changed": True}))
    assert all(p in old_payload["sections"][-1]["paragraphs"] for p in REPORT_LIMITATIONS)
    assert client.get(f"/api/v1/runs/{run_id}/report").json()["report"] == old_payload


def test_older_analyzed_run_creates_report_once_from_saved_facts(setup_client):
    client, queue, _, _ = setup_client
    project_id, _ = labeled_baseline(setup_client)
    run_id = analyzed(setup_client, project_id)
    summary = client.get(f"/api/v1/runs/{run_id}/summary").json()
    # Disposable fixture emulates an analyzed pre-M5 run, which has no report row.
    with queue.sessions.begin() as session:
        session.delete(session.get(RunReport, UUID(run_id)))
    from backend.app.services.report_store import build_report

    with patch("backend.app.services.report_store.build_report", wraps=build_report) as render:
        first = client.get(f"/api/v1/runs/{run_id}/report").json()
        second = client.get(f"/api/v1/runs/{run_id}/report").json()
        assert render.call_count == 1 and first == second
    assert client.get(f"/api/v1/runs/{run_id}/summary").json() == summary


def test_trends_persisted_order_gaps_selectors_methodology_and_feature_template(setup_client):
    client, queue, _, _ = setup_client
    project_id, _ = labeled_baseline(setup_client)
    b = analyzed(setup_client, project_id)
    a = analyzed(setup_client, project_id, current_csv())
    # Ordering/version fixture clones stored facts without refitting or modifying published runs.
    with queue.sessions.begin() as session:
        source = session.get(MonitoringRun, UUID(b))
        fields = {
            c.name: copy.deepcopy(getattr(source, c.name)) for c in MonitoringRun.__table__.columns
        }
        fields.update(
            id=UUID(int=1),
            name="Earlier synthetic B",
            monitoring_date=date(2026, 10, 3),
            created_at=datetime(2026, 10, 5, tzinfo=UTC),
            methodology_version="synthetic-version-caution",
        )
        session.add(MonitoringRun(**fields))
        fields = {**fields, "id": UUID(int=2), "name": "Same-time synthetic B"}
        session.add(MonitoringRun(**fields))
    base = f"/api/v1/projects/{project_id}/trends"
    trend = client.get(base + "?group=performance&signal=balanced_accuracy").json()
    assert [p["run_id"] for p in trend["points"]] == [str(UUID(int=1)), str(UUID(int=2)), b, a]
    assert trend["points"][-1]["value"] is None and trend["points"][-1]["reason"]
    assert trend["points"][-2]["value"] is not None
    assert trend["warning"] == METHODOLOGY_CAUTION
    assert trend["reference"]["n"] == 60
    for group, signals in trend["options"].items():
        for signal in signals:
            suffix = (
                "&feature_id=" + ("f001" if signal == "js" else "f000")
                if group == "data"
                else "&class_label=class0"
                if group == "predictions"
                else ""
            )
            response = client.get(base + f"?group={group}&signal={signal}" + suffix)
            assert response.status_code == 200, response.text
            selected = response.json()
            assert selected["group"] == group and selected["signal"] == signal
            if signal in {"ks", "js"}:
                assert selected["reference"] is None
    for params in (
        "group=data&signal=ks&feature_id=f001",
        "group=data&signal=js&feature_id=f000",
        "group=data&signal=missing_percent&feature_id=f003",
        "group=predictions&signal=class_share&class_label=unknown",
        "group=performance&signal=health_score",
    ):
        assert client.get(base + "?" + params).status_code == 422
    feature = client.get(f"/api/v1/runs/{b}/features/f000").json()
    summary = client.get(f"/api/v1/runs/{b}/summary").json()
    assert {k: v for k, v in feature.items() if k != "interpretation"} == summary["features"][0]
    assert "all valid baseline rows" in feature["interpretation"]["measured"]
    assert (
        feature["interpretation"]["cannot_conclude"]
        == "ModelMedic does not claim this feature change caused any change in performance."
    )
