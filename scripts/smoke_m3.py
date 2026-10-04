"""Binary and multiclass Mode A through the real Compose API/proxy/worker/storage."""

import json
import time
from hashlib import sha256
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID

from sqlalchemy import select

from backend.app.core.config import Settings
from backend.app.db.models import ModelArtifact, MonitoringRun, Project
from backend.app.db.session import create_db
from backend.app.storage.local import LocalArtifactStore
from scripts.smoke_m1 import BASE, call
from scripts.smoke_m2 import wait

ROOT = BASE.rsplit("/projects", 1)[0]


def run_call(path, method="GET", body=None, csv=None):
    data = csv if csv is not None else json.dumps(body).encode() if body is not None else None
    request = Request(
        ROOT + path,
        data=data,
        method=method,
        headers={"Content-Type": "text/csv" if csv is not None else "application/json"},
    )
    with urlopen(request, timeout=10) as response:
        return json.load(response) if response.status != 204 else None


def wait_run(run_id, state):
    for _ in range(240):
        run = run_call("/runs/" + run_id)
        assert not run["job"] or run["job"]["state"] != "FAILED", run["job"]
        assert run["state"] != "VALIDATION_FAILED", run["dataset"]
        if run["state"] == state:
            return run
        time.sleep(0.25)
    raise AssertionError("Monitoring worker did not finish within the smoke deadline")


def main():
    settings = Settings()
    engine, sessions = create_db(settings)
    store = LocalArtifactStore(settings.artifact_root)
    for classes in (2, 3):
        p = call(method="POST", body={"name": "M3 synthetic acceptance"})
        project_id, run_id = p["id"], None
        path = "/" + project_id
        try:
            csv = (
                "amount,segment,target\n"
                + "".join(
                    f"{k * 300 + i},group{k},class{k}\n" for k in range(classes) for i in range(150)
                )
            ).encode()
            with urlopen(
                Request(
                    BASE + path + "/baseline",
                    data=iter([csv[:100], csv[100:]]),
                    headers={"Content-Type": "text/csv"},
                ),
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
            snapshot_id = p["baseline"]["id"]
            call(path + "/establish", "POST", {"snapshot_id": snapshot_id})
            run = call(
                path + "/runs",
                "POST",
                {
                    "name": "Unlabeled synthetic current",
                    "monitoring_date": "2026-10-04",
                    "notes": "Acceptance fixture only",
                },
            )
            run_id = run["id"]
            current = (
                "amount,segment,extra\n"
                + "".join(f"{'' if i % 10 == 0 else 1000 + i},new,ignored\n" for i in range(90))
            ).encode()
            run_call(f"/runs/{run_id}/upload", "POST", csv=iter([current[:64], current[64:]]))
            run = wait_run(run_id, "READY")
            assert run["mode"] == "A" and run["baseline_snapshot_id"] == snapshot_id
            assert run["dataset"]["validation_report"]["ignored_extra_columns"] == ["extra"]
            with sessions() as session:
                artifact = session.scalar(
                    select(ModelArtifact).where(ModelArtifact.snapshot_id == UUID(snapshot_id))
                )
                before = sha256(store.get(artifact.storage_key)).hexdigest()
            run_call(f"/runs/{run_id}/analyze", "POST")
            run = wait_run(run_id, "ANALYZED")
            results = run_call(f"/runs/{run_id}/summary")
            assert results["features"][0]["distribution"]["baseline_n"] == classes * 150
            assert results["features"][0]["distribution"]["current_n"] == 81
            assert results["predictions"]["baseline_n"] == classes * 30
            assert results["confidence"]["current_n"] == 90
            assert results["predictions"]["class_order"] == [f"class{i}" for i in range(classes)]
            assert results["features"][0]["distribution"]["status"] == "DETECTED"
            for endpoint in ("features", "features/f000", "predictions", "confidence"):
                assert run_call(f"/runs/{run_id}/{endpoint}")
            for endpoint in ("metrics", "calibration", "errors", "slices"):
                unavailable = run_call(f"/runs/{run_id}/{endpoint}")
                assert unavailable["status"] == "UNAVAILABLE"
                assert "ground-truth labels were not provided" in unavailable["reason"]
            with sessions() as session:
                stored_run = session.get(MonitoringRun, UUID(run_id))
                assert json.loads(store.get(stored_run.result_object_key)) == results
                assert (
                    sha256(store.get(stored_run.result_object_key)).hexdigest()
                    == run["result_sha256"]
                )
                assert sha256(store.get(artifact.storage_key)).hexdigest() == before
            assert run_call(f"/runs/{run_id}/summary") == results
            try:
                run_call(f"/runs/{run_id}/analyze", "POST")
            except HTTPError as exc:
                assert exc.code == 409
            else:
                raise AssertionError("Analyzed immutable run accepted another analysis")
            print(
                f"PASS: {classes} classes / Mode A / raw data / frozen inference / "
                "features / prediction / confidence / unavailable labels / immutable reload",
                flush=True,
            )
        finally:
            if run_id:
                run_call(f"/runs/{run_id}", "DELETE")
            # Only the exact synthetic acceptance project, including its private baseline artifacts.
            with sessions.begin() as session:
                project = session.get(Project, UUID(project_id))
                if project:
                    session.delete(project)
            store.delete_prefix(f"projects/{project_id}")
    engine.dispose()
    print("PASS: M3 synthetic smoke data and artifacts cleaned", flush=True)


if __name__ == "__main__":
    main()
