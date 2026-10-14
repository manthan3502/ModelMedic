"""Safely measure the joint row/encoded boundary without six expensive classifier fits.

Actual locked preprocessing fits on Development only; no model is trained here.
This is a memory/limit check, not a full classifier capacity claim.
"""

import json
import resource
import time
from io import BytesIO

import numpy as np
import pandas as pd

from backend.app.core.config import Settings
from backend.app.domain.datasets import validate_configuration, validate_csv
from backend.app.science.baseline import make_pipeline, split_indices


def main() -> None:
    n = 50_000
    rng = np.random.default_rng(42)
    frame = pd.DataFrame({f"x{i}": rng.normal(size=n).round(4) for i in range(30)})
    for i in range(20):
        frame[f"c{i}"] = rng.integers(0, 97 if i < 10 else 98, n).astype(str)
        frame.loc[::1009, f"c{i}"] = None
    frame["target"] = np.where(frame.x0 > 0, "event", "other")
    source = frame.to_csv(index=False).encode()
    settings = Settings(database_url="postgresql+psycopg://unused/unused")
    start = time.monotonic()
    canonical, profile = validate_csv(source, settings)
    validation = time.monotonic() - start
    config = validate_configuration(
        profile,
        {
            "target_id": "f050",
            "positive_class": "event",
            "classifier": "logistic_regression",
            "weighting": "standard",
            "features": [
                {
                    "feature_id": c["feature_id"],
                    "type": "categorical" if c["name"].startswith("c") else "numeric",
                }
                for c in profile["columns"][:-1]
            ],
        },
        settings,
    )
    typed = pd.read_parquet(BytesIO(canonical))
    types = {
        c["name"]: "categorical" if c["name"].startswith("c") else "numeric"
        for c in profile["columns"][:-1]
    }
    development, heldout = split_indices(typed.target)
    start = time.monotonic()
    pipeline = make_pipeline(types, "logistic_regression", "standard")
    raw = pipeline["semantics"].fit_transform(typed[list(types)].iloc[development])
    dense = pipeline["preprocessor"].fit_transform(raw)
    reference = pipeline["preprocessor"].transform(
        pipeline["semantics"].transform(typed[list(types)].iloc[heldout])
    )
    assert config["encoded_columns"] == dense.shape[1] == reference.shape[1] == 2000
    print(
        json.dumps(
            {
                "rows": n,
                "features": 50,
                "encoded_columns": 2000,
                "csv_bytes": len(source),
                "canonical_bytes": len(canonical),
                "validation_seconds": validation,
                "preprocessing_seconds": time.monotonic() - start,
                "development_dense_bytes": dense.nbytes,
                "heldout_dense_bytes": reference.nbytes,
                "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "classifier_training": "NOT RUN at joint maximum",
            }
        )
    )


if __name__ == "__main__":
    main()
