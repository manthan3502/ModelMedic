"""Privacy-projected canonical rows; no scientific calculation or model loading."""

from hashlib import sha256
from io import BytesIO
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.db.models import BaselineSnapshot, Dataset, MonitoringRun
from backend.app.domain.datasets import SCHEMA_VERSION
from backend.app.storage.base import ArtifactStore


def error_examples(
    session: Session, run: MonitoringRun, store: ArtifactStore, view: str
) -> dict[str, Any]:
    assert run.results
    references = run.results["errors"]["row_references"]
    if view not in references:
        raise HTTPException(404, "Error example view not found.")
    dataset = session.get(Dataset, run.dataset_id)
    snapshot = session.get(BaselineSnapshot, run.baseline_snapshot_id)
    assert dataset and snapshot
    if not dataset.canonical_object_key or dataset.canonical_schema_version != SCHEMA_VERSION:
        raise HTTPException(409, "Canonical source is unavailable or incompatible.")
    try:
        content = store.get(dataset.canonical_object_key)
    except OSError:
        raise HTTPException(409, "Canonical source is unavailable.") from None
    if sha256(content).hexdigest() != dataset.canonical_sha256:
        raise HTTPException(409, "Canonical source failed integrity verification.")
    baseline = session.get(Dataset, snapshot.dataset_id)
    assert baseline and baseline.profile
    included = {f["feature_id"] for f in snapshot.configuration["features"]}
    names = [c["name"] for c in baseline.profile["columns"] if c["feature_id"] in included]
    # Projection occurs before materializing rows: excluded columns and target are never returned.
    table = pq.read_table(BytesIO(content), columns=["__mm_row_id", *names])
    positions = {row_id: i for i, row_id in enumerate(table["__mm_row_id"].to_pylist())}
    ids = references[view][:50]
    if any(row_id not in positions for row_id in ids):
        raise HTTPException(409, "Stored example references do not match the canonical source.")
    return {
        "view": view,
        "features": names,
        "limit": 50,
        "rows": [
            {"row_id": row["__mm_row_id"], "features": {name: row[name] for name in names}}
            for row in table.take(
                pa.array([positions[row_id] for row_id in ids], type=pa.int64())
            ).to_pylist()
        ],
    }
