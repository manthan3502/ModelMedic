"""Real Compose M2 flow through the frontend hostname/proxy, worker and PostgreSQL."""

import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID

from sqlalchemy import select

from backend.app.core.config import Settings
from backend.app.db.models import BaselineSnapshot, ModelArtifact, Project
from backend.app.db.session import create_db
from backend.app.storage.local import LocalArtifactStore
from scripts.smoke_m1 import BASE, call


def wait(path, predicate):
    for _ in range(240):
        project = call(path)
        assert project["job"]["state"] != "FAILED", project["job"]
        if predicate(project):
            return project
        time.sleep(0.5)
    raise AssertionError("Worker did not complete within the smoke-test deadline")


def expect_conflict(path, method, body=None):
    try:
        call(path, method, body)
    except HTTPError as exc:
        assert exc.code == 409
    else:
        raise AssertionError("Established baseline mutation was accepted")


def main():
    settings = Settings()
    engine, sessions = create_db(settings)
    store = LocalArtifactStore(settings.artifact_root)
    for classes in (2, 3):
        for classifier in ("logistic_regression", "random_forest", "gradient_boosting"):
            for weighting in ("standard", "balanced"):
                p = call(method="POST", body={"name": "M2 synthetic acceptance"})
                path = "/" + p["id"]
                try:
                    csv = (
                        "amount,segment,target\n"
                        + "".join(
                            f"{i % 31},group{i % 4},class{i % classes}\n"
                            for i in range(classes * 150)
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
                    config = {
                        "dataset_id": p["dataset"]["id"],
                        "target_id": "f002",
                        "positive_class": "class0" if classes == 2 else None,
                        "features": [
                            {"feature_id": "f000", "type": "numeric"},
                            {"feature_id": "f001", "type": "categorical"},
                        ],
                        "classifier": classifier,
                        "weighting": weighting,
                    }
                    p = call(path + "/configuration", "PUT", config)
                    assert p["baseline"] is None
                    p = call(path + "/train", "POST")
                    p = wait(path, lambda p: p["job"]["state"] == "SUCCEEDED")
                    assert p["baseline"]["status"] == "TRAINED"
                    results = p["baseline"]["results"]
                    assert results["heldout_count"] == classes * 30
                    assert all(len(s["values"]) == 5 for s in results["cv"].values())
                    for curve in results["calibration"]["classes"]:
                        assert sum(b["count"] for b in curve["bins"]) == classes * 30
                    with sessions() as session:
                        snapshot = session.get(BaselineSnapshot, UUID(p["baseline"]["id"]))
                        artifact = session.scalar(
                            select(ModelArtifact).where(ModelArtifact.snapshot_id == snapshot.id)
                        )
                        assert store.exists(artifact.storage_key)
                        assert store.exists(snapshot.split_membership_object_key)
                        manifest = json.loads(
                            store.get(snapshot.artifact_prefix + "/manifest.json")
                        )
                        assert manifest == artifact.environment_manifest
                        assert manifest["class_order"] == results["class_order"]
                    for section in ("summary", "metrics", "calibration", "importance"):
                        assert call(path + "/baseline/" + section)
                    p = call(path + "/establish", "POST", {"snapshot_id": p["baseline"]["id"]})
                    assert (
                        p["state"] == "BASELINE_READY" and p["baseline"]["status"] == "ESTABLISHED"
                    )
                    expect_conflict(path + "/configuration", "PUT", config)
                    expect_conflict(path + "/train", "POST")
                    expect_conflict(path, "DELETE")
                    print(
                        f"PASS: {classes} classes / {classifier} / {weighting}: "
                        "train / CV / evaluate / artifacts / establish / immutable",
                        flush=True,
                    )
                finally:
                    # Test-only cleanup of the exact synthetic project, not a product unlock route.
                    with sessions.begin() as session:
                        created = session.get(Project, UUID(p["id"]))
                        if created:
                            session.delete(created)
                    store.delete_prefix("projects/" + p["id"])
    engine.dispose()


if __name__ == "__main__":
    main()
