from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.storage.local import LocalArtifactStore


def test_liveness_needs_no_database():
    app = create_app(Settings(database_url="postgresql+psycopg://localhost:1/unavailable"))
    with TestClient(app) as client:
        response = client.get("/api/v1/health/live")
        assert response.json() == {"status": "alive"}
        assert response.headers["x-request-id"]
        assert client.get("/api/v1/health/ready").status_code == 503
        missing = client.get("/absent")
        assert missing.status_code == 404
        assert set(missing.json()) == {"code", "message", "details", "request_id"}


def test_configuration_rejects_unsafe_runtime():
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite:///wrong.db")
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql+psycopg://localhost/db",
            environment="deployment",
            deployment_mode=None,
        )
    with pytest.raises(ValidationError):
        Settings(database_url="postgresql+psycopg://localhost/db", heartbeat_seconds=30)


def test_demo_denies_mutations_even_on_unknown_routes():
    app = create_app(
        Settings(database_url="postgresql+psycopg://localhost/db", deployment_mode="demo")
    )
    with TestClient(app) as client:
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            assert client.request(method, "/api/v1/future-route").status_code == 403


def test_artifacts_are_write_once_and_prefix_cleanup_is_scoped(tmp_path: Path):
    store = LocalArtifactStore(tmp_path)
    store.put("projects/one/test.bin", b"harmless m0 fixture")
    store.put("projects/two/test.bin", b"keep")
    assert store.exists("projects/one/test.bin")
    assert store.get("projects/one/test.bin") == b"harmless m0 fixture"
    with pytest.raises(FileExistsError):
        store.put("projects/one/test.bin", b"overwrite")
    store.delete_prefix("projects/one/")
    assert not store.exists("projects/one/test.bin")
    assert store.get("projects/two/test.bin") == b"keep"
    store.delete("projects/two/test.bin")
    store.delete("projects/two/test.bin")


@pytest.mark.parametrize(
    "key", ["", "../escape", "/absolute", "a/../b", "a//b", "C:/data", "a\\b", "."]
)
def test_artifacts_reject_untrusted_keys(tmp_path: Path, key: str):
    with pytest.raises(ValueError):
        LocalArtifactStore(tmp_path).put(key, b"no")
