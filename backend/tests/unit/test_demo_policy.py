import json
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.services.demo import REGISTRY_KEY, VERSIONS, authorize_read, registry
from backend.app.storage.local import LocalArtifactStore


def seed_registry(store):
    data = {"versions": VERSIONS, "synthetic_only": True}
    data.update({k: [str(uuid4())] for k in ("projects", "runs", "jobs", "slices")})
    store.put(REGISTRY_KEY, json.dumps(data).encode())
    return data


def test_all_registered_mutation_methods_fail_closed(tmp_path):
    app = create_app(
        Settings(
            database_url="postgresql+psycopg://unused/unused",
            deployment_mode="demo",
            artifact_root=tmp_path,
        )
    )
    with TestClient(app) as client:
        paths = app.openapi()["paths"]
        assert len(paths) >= 30
        assert "/api/v1/projects/{project_id}/configuration" in paths
        assert "/api/v1/runs/{run_id}/slices" in paths
        for path in paths:
            for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"):
                response = client.request(method, path)
                assert response.status_code == 403, (method, path)
                assert response.headers["X-Request-ID"]
                if method != "HEAD":
                    assert response.json()["code"] == "READ_ONLY_DEMO"
        assert client.get("/api/v1/runtime").json()["read_only"] is True
        assert client.get("/api/v1/health/worker").json()["status"] == "NOT_REQUIRED"
        assert client.get("/docs").status_code == 403
        assert client.get("/api/v1/future-export").status_code == 403
        assert client.get("/api/v1/projects").status_code == 503


def test_only_registered_synthetic_identifiers_are_readable(tmp_path):
    store = LocalArtifactStore(tmp_path)
    data = seed_registry(store)
    for path in (
        "/api/v1/projects",
        f"/api/v1/projects/{data['projects'][0]}/runs",
        f"/api/v1/runs/{data['runs'][0]}/features/f001",
        f"/api/v1/runs/{data['runs'][0]}/slices/{data['slices'][0]}",
        f"/api/v1/jobs/{data['jobs'][0]}",
    ):
        authorize_read(path, store)
    for path in (
        f"/api/v1/projects/{uuid4()}",
        f"/api/v1/runs/{uuid4()}/summary",
        f"/api/v1/runs/{data['runs'][0]}/slices/{uuid4()}",
    ):
        with pytest.raises(HTTPException) as denied:
            authorize_read(path, store)
        assert denied.value.status_code == 404
    with pytest.raises(HTTPException):
        authorize_read(f"/api/v1/runs/{data['runs'][0]}/future-export", store)


@pytest.mark.parametrize("change", ["method", "private", "invalid-id"])
def test_registry_incompatible_or_private_fails_closed(tmp_path, change):
    store = LocalArtifactStore(tmp_path)
    data = seed_registry(store)
    store.delete(REGISTRY_KEY)
    if change == "method":
        data["versions"] = {**VERSIONS, "monitoring": "future"}
    elif change == "private":
        data["synthetic_only"] = False
    else:
        data["projects"] = ["invalid"]
    store.put(REGISTRY_KEY, json.dumps(data).encode())
    with pytest.raises(HTTPException) as denied:
        registry(store)
    assert denied.value.status_code == 503
