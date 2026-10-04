"""Exercise M1 against the real API, proxy, worker, PostgreSQL and artifact volume."""

import hashlib
import json
import time
from urllib.request import Request, urlopen
from uuid import UUID

import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import func, select

from backend.app.core.config import Settings
from backend.app.db.models import BaselineSnapshot, Dataset, ModelArtifact
from backend.app.db.session import create_db
from backend.app.storage.local import LocalArtifactStore

BASE = "http://frontend:5173/api/v1/projects"


def call(path: str = "", method: str = "GET", body: object = None):
    headers = {"Content-Type": "application/json"}
    data = json.dumps(body).encode() if body is not None else None
    with urlopen(
        Request(BASE + path, data=data, method=method, headers=headers), timeout=10
    ) as response:
        return json.load(response) if response.status != 204 else None


def main():
    settings = Settings()
    engine, sessions = create_db(settings)
    store = LocalArtifactStore(settings.artifact_root)
    with sessions() as session:
        before = [
            session.scalar(select(func.count()).select_from(table))
            for table in (BaselineSnapshot, ModelArtifact)
        ]
    project = call(
        method="POST",
        body={
            "name": "M1 synthetic smoke",
            "description": "Generated in memory; removed after verification",
        },
    )
    path = f"/{project['id']}"
    try:
        csv = (
            "amount,segment,target\n"
            + "".join(f"{i},group{i % 3},{'event' if i % 2 else 'none'}\n" for i in range(240))
        ).encode()
        # Iterable body uses real HTTP chunked transfer: Content-Length is not the upload guard.
        with urlopen(
            Request(
                BASE + path + "/baseline",
                data=iter([csv[:300], csv[300:]]),
                method="POST",
                headers={"Content-Type": "text/csv"},
            ),
            timeout=10,
        ) as response:
            assert response.status == 202
            queued = json.load(response)
            assert queued["job"]["state"] in {"QUEUED", "RUNNING"}
        for _ in range(60):
            project = call(path)
            if project["dataset"]["status"] == "READY":
                break
            assert project["job"]["state"] != "FAILED"
            time.sleep(0.5)
        else:
            raise AssertionError("Dataset validation timed out")
        assert project["dataset"]["profile"]["row_count"] == 240
        assert project["dataset"]["canonical_schema_version"] == "canonical-v1"
        with sessions() as session:
            dataset = session.get(Dataset, UUID(project["dataset"]["id"]))
            canonical = store.get(dataset.canonical_object_key)
            assert hashlib.sha256(canonical).hexdigest() == dataset.canonical_sha256
            table = pq.read_table(pa.BufferReader(canonical))
            assert table.column("__mm_row_id").to_pylist() == list(range(240))
        config = {
            "dataset_id": project["dataset"]["id"],
            "target_id": "f002",
            "positive_class": "event",
            "features": [
                {"feature_id": "f000", "type": "numeric"},
                {"feature_id": "f001", "type": "categorical"},
            ],
            "classifier": None,
            "weighting": None,
        }
        project = call(path + "/configuration", "PUT", config)
        assert project["preprocessing"]["fitted"] is False and project["confirmation"] is None
        for classifier in ("logistic_regression", "random_forest", "gradient_boosting"):
            for weighting in ("standard", "balanced"):
                project = call(
                    path + "/configuration",
                    "PUT",
                    {**config, "classifier": classifier, "weighting": weighting},
                )
                assert project["confirmation"]["ready"]
                assert project["confirmation"]["training_available"] is False
        with sessions() as session:
            after = [
                session.scalar(select(func.count()).select_from(table))
                for table in (BaselineSnapshot, ModelArtifact)
            ]
            assert before == after
        print(
            "PASS: streamed upload → validation worker → hashed canonical Parquet → profile → "
            "binary target/features → preprocessing review → all 3 classifiers/2 weights → "
            "confirmation, without training"
        )
    finally:
        call(path, "DELETE")
        engine.dispose()


if __name__ == "__main__":
    main()
