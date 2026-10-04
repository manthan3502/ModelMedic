from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text, update

from backend.app.core.config import Settings
from backend.app.db.models import BaselineSnapshot, Dataset, Job, ModelArtifact, Project
from backend.app.domain.jobs import OwnershipLost
from backend.app.jobs.datasets import validation_result
from backend.app.jobs.worker import run_once
from backend.app.main import create_app
from backend.app.services.queue import Queue
from backend.app.storage.local import LocalArtifactStore
from backend.tests.unit.test_datasets import baseline

pytestmark = pytest.mark.integration


def test_migration_upgrade_preserves_m0_projects_and_round_trips(database_url, db):
    engine, _ = db
    project_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO projects (id, name) VALUES (:id, 'M0 preserved')"), {"id": project_id}
        )
    try:
        command.downgrade(Config("alembic.ini"), "0001_m0")
        command.upgrade(Config("alembic.ini"), "head")
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT name FROM projects WHERE id = :id"), {"id": project_id}
                ).scalar_one()
                == "M0 preserved"
            )
    finally:
        command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture
def setup_client(database_url, db, tmp_path):
    _, sessions = db
    settings = Settings(database_url=database_url, artifact_root=tmp_path)
    store = LocalArtifactStore(tmp_path)
    with TestClient(create_app(settings)) as client:
        yield client, Queue(sessions), store, settings


def create(client):
    response = client.post(
        "/api/v1/projects", json={"name": "Synthetic setup", "description": "Generated test only"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def validated(setup_client, content=None):
    client, queue, store, settings = setup_client
    project_id = create(client)
    response = client.post(
        f"/api/v1/projects/{project_id}/baseline",
        content=content or baseline(),
        headers={"Content-Type": "text/csv", "X-Filename": "../../untrusted.csv"},
    )
    assert response.status_code == 202, response.text
    assert response.json()["job"]["state"] == "QUEUED"
    assert run_once(queue, uuid4(), 1, store, settings)
    return project_id, client.get(f"/api/v1/projects/{project_id}").json()


def choice(p, **changes):
    return {
        "dataset_id": p["dataset"]["id"],
        "target_id": "f002",
        "positive_class": "class1",
        "features": [
            {"feature_id": "f000", "type": "numeric"},
            {"feature_id": "f001", "type": "categorical"},
        ],
        "classifier": "random_forest",
        "weighting": "balanced",
        **changes,
    }


def test_complete_setup_without_training_and_project_deletion(setup_client):
    client, queue, store, _ = setup_client
    project_id, p = validated(setup_client)
    assert p["job"]["state"] == "SUCCEEDED" and p["dataset"]["status"] == "READY"
    assert p["dataset"]["canonical_schema_version"] == "canonical-v1"
    assert len(p["dataset"]["canonical_sha256"]) == 64
    assert p["confirmation"] is None
    response = client.put(f"/api/v1/projects/{project_id}/configuration", json=choice(p))
    assert response.status_code == 200, response.text
    p = response.json()
    assert p["confirmation"]["ready"] and p["confirmation"]["training_available"] is False
    assert p["preprocessing"]["fitted"] is False and p["configuration"]["class_order"] == [
        "class0",
        "class1",
    ]
    with queue.sessions() as session:
        assert session.scalar(select(func.count()).select_from(ModelArtifact)) == 0
        assert session.scalar(select(func.count()).select_from(BaselineSnapshot)) == 0
        dataset = session.get(Dataset, UUID(p["dataset"]["id"]))
        assert "untrusted" not in dataset.original_object_key
        assert store.exists(dataset.canonical_object_key)
    assert client.get("/api/v1/projects").json()[0]["id"] == project_id
    assert client.delete(f"/api/v1/projects/{project_id}").status_code == 204
    assert not (store.root / "projects" / project_id).exists()
    assert client.get(f"/api/v1/projects/{project_id}").status_code == 404
    with queue.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 0
        assert session.scalar(select(func.count()).select_from(Dataset)) == 0


def test_validation_rejection_is_persisted_and_blocks_configuration(setup_client):
    client, _, _, _ = setup_client
    project_id, p = validated(setup_client, b"__mm_x\n1\n")
    assert p["dataset"]["status"] == "VALIDATION_FAILED"
    assert "reserved" in p["dataset"]["validation_report"]["errors"][0]
    assert p["dataset"]["canonical_sha256"] is None
    assert (
        client.put(f"/api/v1/projects/{project_id}/configuration", json=choice(p)).status_code
        == 409
    )


def test_active_jobs_and_non_draft_projects_block_mutations(setup_client):
    client, queue, _, _ = setup_client
    project_id = create(client)
    assert (
        client.post(
            f"/api/v1/projects/{project_id}/baseline",
            content=baseline(),
            headers={"Content-Type": "text/csv"},
        ).status_code
        == 202
    )
    assert (
        client.post(
            f"/api/v1/projects/{project_id}/baseline",
            content=baseline(),
            headers={"Content-Type": "text/csv"},
        ).status_code
        == 409
    )
    assert client.delete(f"/api/v1/projects/{project_id}").status_code == 409
    with queue.sessions.begin() as session:
        session.execute(update(Job).values(state="FAILED"))
        session.execute(
            update(Project).where(Project.id == UUID(project_id)).values(state="BASELINE_READY")
        )
    assert (
        client.post(
            f"/api/v1/projects/{project_id}/baseline",
            content=baseline(),
            headers={"Content-Type": "text/csv"},
        ).status_code
        == 409
    )
    assert client.delete(f"/api/v1/projects/{project_id}").status_code == 409


def test_reupload_invalidates_configuration_and_stale_dataset_id(setup_client):
    client, queue, store, settings = setup_client
    project_id, p = validated(setup_client)
    client.put(f"/api/v1/projects/{project_id}/configuration", json=choice(p))
    response = client.post(
        f"/api/v1/projects/{project_id}/baseline",
        content=baseline(3),
        headers={"Content-Type": "text/csv"},
    )
    assert response.status_code == 202 and response.json()["configuration"] == {}
    run_once(queue, uuid4(), 1, store, settings)
    assert (
        client.put(f"/api/v1/projects/{project_id}/configuration", json=choice(p)).status_code
        == 409
    )
    p = client.get(f"/api/v1/projects/{project_id}").json()
    assert (
        client.put(
            f"/api/v1/projects/{project_id}/configuration", json=choice(p, positive_class=None)
        ).status_code
        == 200
    )


def test_byte_limit_is_counted_without_content_length(database_url, db, tmp_path):
    settings = Settings(database_url=database_url, artifact_root=tmp_path, upload_max_bytes=10)
    with TestClient(create_app(settings)) as client:
        project_id = create(client)
        response = client.post(
            f"/api/v1/projects/{project_id}/baseline",
            content=iter([b"a\n123", b"456789012"]),
            headers={"Content-Type": "text/csv"},
        )
        assert response.status_code == 413
        assert client.get(f"/api/v1/projects/{project_id}").json()["dataset"] is None
    assert list((tmp_path / ".uploads").iterdir()) == []


@pytest.mark.parametrize(
    "changes",
    [
        {"positive_class": None},
        {"classifier": "automl"},
        {"weighting": "recommended"},
        {"features": [{"feature_id": "f001", "type": "numeric"}]},
    ],
)
def test_invalid_configuration_choices(setup_client, changes):
    client, _, _, _ = setup_client
    project_id, p = validated(setup_client)
    assert (
        client.put(
            f"/api/v1/projects/{project_id}/configuration", json=choice(p, **changes)
        ).status_code
        == 422
    )


def test_dataset_results_are_fenced_and_atomic_with_job_state(setup_client):
    client, queue, store, settings = setup_client
    project_id = create(client)
    client.post(
        f"/api/v1/projects/{project_id}/baseline",
        content=baseline(),
        headers={"Content-Type": "text/csv"},
    )
    job = queue.claim()
    persist, key = validation_result(queue, job, store, settings)
    with queue.sessions() as session:
        assert session.get(Job, job.id).stage == "BUILDING_TYPED_COPY"
    with queue.sessions.begin() as session:
        session.execute(
            update(Project).where(Project.id == UUID(project_id)).values(deletion_pending=True)
        )
    with pytest.raises(OwnershipLost):
        queue.finalize(job, result=persist)
    with queue.sessions() as session:
        assert session.get(Job, job.id).state == "RUNNING"
        assert session.get(Dataset, job.target_id).canonical_object_key is None
    store.delete(key)


def test_failed_external_deletion_is_recoverable(setup_client, monkeypatch):
    client, _, store, _ = setup_client
    project_id, _ = validated(setup_client)
    original = store.delete_prefix
    # Router has its own instance of the same private store implementation.
    monkeypatch.setattr(
        LocalArtifactStore,
        "delete_prefix",
        lambda *_: (_ for _ in ()).throw(OSError("private path")),
    )
    response = client.delete(f"/api/v1/projects/{project_id}")
    assert response.status_code == 503 and "private path" not in response.text
    assert client.get(f"/api/v1/projects/{project_id}").json()["deletion_pending"]
    assert (
        client.post(
            f"/api/v1/projects/{project_id}/baseline",
            content=baseline(),
            headers={"Content-Type": "text/csv"},
        ).status_code
        == 409
    )
    monkeypatch.setattr(LocalArtifactStore, "delete_prefix", lambda _, key: original(key))
    assert client.delete(f"/api/v1/projects/{project_id}").status_code == 204


def test_demo_denies_every_added_mutation_route(database_url, db, tmp_path):
    settings = Settings(database_url=database_url, artifact_root=tmp_path, deployment_mode="demo")
    with TestClient(create_app(settings)) as client:
        for path, method in [
            ("", "POST"),
            (f"/{uuid4()}/baseline", "POST"),
            (f"/{uuid4()}/configuration", "PUT"),
            (f"/{uuid4()}", "DELETE"),
        ]:
            assert client.request(method, "/api/v1/projects" + path).status_code == 403
