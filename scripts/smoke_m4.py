"""Real labeled worker lifecycle, historical reference, absent classes and privacy."""

import json
from hashlib import sha256
from urllib.request import Request, urlopen
from uuid import UUID

from sqlalchemy import select

from backend.app.core.config import Settings
from backend.app.db.models import ModelArtifact, MonitoringRun, Project, RunMetric
from backend.app.db.session import create_db
from backend.app.storage.local import LocalArtifactStore
from scripts.smoke_m1 import BASE, call
from scripts.smoke_m2 import wait
from scripts.smoke_m3 import run_call, wait_run


def establish(classes, name="M4 synthetic acceptance"):
    p = call(method="POST", body={"name": name})
    project_id = p["id"]
    path = "/" + project_id
    content = (
        "amount,segment,target,excluded_id\n"
        + "".join(
            f"{k * 300 + i},group{k},class{k},synthetic-id-{k}-{i}\n"
            for k in range(classes)
            for i in range(150)
        )
    ).encode()
    with urlopen(
        Request(BASE + path + "/baseline", data=content, headers={"Content-Type": "text/csv"}),
        timeout=10,
    ) as response:
        assert response.status == 202
    p = wait(path, lambda p: p["dataset"]["status"] == "READY")
    call(
        path + "/configuration",
        "PUT",
        {
            "dataset_id": p["dataset"]["id"],
            "target_id": "f002",
            "positive_class": "class0" if classes == 2 else None,
            "features": [
                {"feature_id": "f000", "type": "numeric"},
                {"feature_id": "f001", "type": "categorical"},
            ],
            "classifier": "logistic_regression" if classes == 2 else "random_forest",
            "weighting": "standard" if classes == 2 else "balanced",
        },
    )
    call(path + "/train", "POST")
    p = wait(path, lambda p: p["job"]["state"] == "SUCCEEDED")
    call(path + "/establish", "POST", {"snapshot_id": p["baseline"]["id"]})
    return project_id, p["baseline"]


def analyze(project_id, classes, absent):
    run = call(
        "/" + project_id + "/runs",
        "POST",
        {
            "name": "Labeled synthetic current",
            "monitoring_date": "2026-10-05",
            "notes": "Absent-class fixture" if absent else "Complete class support fixture",
        },
    )
    run_id = run["id"]
    current = (
        "amount,segment,target,excluded_id\n"
        + "".join(
            f"{1000 + i},new,class{1 if absent else i % classes},synthetic-secret-{i}\n"
            for i in range(120)
        )
    ).encode()
    run_call(f"/runs/{run_id}/upload", "POST", csv=iter([current[:70], current[70:]]))
    run = wait_run(run_id, "READY")
    assert run["mode"] == "B" and run["dataset"]["validation_report"]["ignored_extra_columns"] == [
        "excluded_id"
    ]
    run_call(f"/runs/{run_id}/analyze", "POST")
    wait_run(run_id, "ANALYZED")
    return run_id


def main():
    settings = Settings()
    engine, sessions = create_db(settings)
    store = LocalArtifactStore(settings.artifact_root)
    for classes in (2, 3):
        project_id, baseline = establish(classes)
        run_ids = []
        try:
            with sessions() as session:
                artifact = session.scalar(
                    select(ModelArtifact).where(ModelArtifact.snapshot_id == UUID(baseline["id"]))
                )
            before = sha256(store.get(artifact.storage_key)).hexdigest()
            for absent in (False, True):
                run_id = analyze(project_id, classes, absent)
                run_ids.append(run_id)
                results = run_call(f"/runs/{run_id}/summary")
                assert results["mode"] == "B"
                performance = run_call(f"/runs/{run_id}/metrics")
                calibration = run_call(f"/runs/{run_id}/calibration")
                errors = run_call(f"/runs/{run_id}/errors")
                assert (
                    performance == results["performance"] and calibration == results["calibration"]
                )
                assert errors == results["errors"]
                assert calibration["baseline"] == baseline["results"]["calibration"]
                assert performance["baseline_n"] == classes * 30 and performance["current_n"] == 120
                assert len(performance["absent_classes"]) == (classes - 1 if absent else 0)
                assert errors["class_order"] == [f"class{i}" for i in range(classes)]
                metrics = {m["metric_name"]: m for m in performance["metrics"]}
                assert all(
                    m["baseline_support"] == classes * 30 and m["current_support"] == 120
                    for m in metrics.values()
                )
                if absent:
                    assert (
                        metrics["balanced_accuracy"]["current_value"] is None
                        and metrics["balanced_accuracy"]["reason"]
                    )
                    assert metrics["log_loss"]["note"] and metrics["brier"]["note"]
                    assert all(c["reason"] for c in calibration["current"]["classes"])
                else:
                    assert all(
                        sum(b["count"] for b in c["bins"]) == 120
                        for c in calibration["current"]["classes"]
                    )
                view = "fn" if classes == 2 else errors["current"]["common_pairs"][0]["view"]
                examples = run_call(f"/runs/{run_id}/errors/examples?view={view}")
                assert examples["features"] == ["amount", "segment"] and len(examples["rows"]) <= 50
                assert "synthetic-secret" not in json.dumps(examples)
                assert run_call(f"/runs/{run_id}/slices")["status"] == "AVAILABLE"
                with sessions() as session:
                    stored = session.get(MonitoringRun, UUID(run_id))
                    assert json.loads(store.get(stored.result_object_key)) == results
                    assert (
                        sha256(store.get(stored.result_object_key)).hexdigest()
                        == stored.result_sha256
                    )
                    assert session.scalar(select(RunMetric).where(RunMetric.run_id == stored.id))
                assert sha256(store.get(artifact.storage_key)).hexdigest() == before
                assert call("/" + project_id)["baseline"]["results"] == baseline["results"]
                assert run_call(f"/runs/{run_id}/summary") == results
                print(
                    f"PASS: {classes} classes / Mode B / absent={absent} / metrics / calibration / "
                    "errors / privacy / immutable",
                    flush=True,
                )
        finally:
            for run_id in run_ids:
                run_call(f"/runs/{run_id}", "DELETE")
            with sessions.begin() as session:
                project = session.get(Project, UUID(project_id))
                assert project.name == "M4 synthetic acceptance"
                session.delete(project)
            store.delete_prefix(f"projects/{project_id}")
    engine.dispose()
    print("PASS: M4 synthetic verification projects and artifact prefixes cleaned", flush=True)


if __name__ == "__main__":
    main()
