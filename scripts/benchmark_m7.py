"""Synthetic operating-budget evidence; runs the actual scientific pipeline, without a DB.

Run in the Linux test image with explicit single-thread BLAS/OpenMP settings.
Output is measurements, not a capacity guarantee. No artifacts or raw rows are saved.
"""

import argparse
import json
import resource
import time
from io import BytesIO

import numpy as np
import pandas as pd

from backend.app.core.config import Settings
from backend.app.domain.datasets import validate_configuration, validate_csv
from backend.app.jobs.artifacts import dump
from backend.app.science.baseline import train
from backend.app.science.monitoring import analyze_mode_a


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "classifier", choices=["logistic_regression", "random_forest", "gradient_boosting"]
    )
    parser.add_argument("case", choices=["rows", "encoded"])
    args = parser.parse_args()
    settings = Settings(database_url="postgresql+psycopg://unused/unused")
    n, categorical = (50_000, 0) if args.case == "rows" else (5_000, 20)
    rng = np.random.default_rng(42)
    frame = pd.DataFrame({f"x{i}": rng.normal(size=n).round(4) for i in range(50 - categorical)})
    for i in range(categorical):
        frame[f"c{i}"] = rng.integers(0, 97, n).astype(str)
    frame["target"] = np.where(frame.x0 + rng.normal(size=n) > 0, "event", "other")
    source = frame.to_csv(index=False).encode()
    start = time.monotonic()
    canonical, profile = validate_csv(source, settings)
    validation_seconds = time.monotonic() - start
    features = [
        {
            "feature_id": c["feature_id"],
            "type": "categorical" if c["name"].startswith("c") else "numeric",
        }
        for c in profile["columns"][:-1]
    ]
    config = validate_configuration(
        profile,
        {
            "target_id": "f050",
            "positive_class": "event",
            "features": features,
            "classifier": args.classifier,
            "weighting": "balanced",
        },
        settings,
    )
    typed = pd.read_parquet(BytesIO(canonical))
    types = {c["name"]: features[i]["type"] for i, c in enumerate(profile["columns"][:-1])}
    start = time.monotonic()
    pipeline, results, reference, membership = train(
        typed[list(types)],
        typed.target,
        np.arange(n),
        config,
        types,
        lambda stage: print(json.dumps({"stage": stage}), flush=True),
    )
    training_seconds = time.monotonic() - start
    start = time.monotonic()
    analyze_mode_a(
        typed,
        typed,
        reference,
        [
            {"feature_id": c["feature_id"], "name": c["name"], "type": types[c["name"]]}
            for c in profile["columns"][:-1]
        ],
        pipeline,
        config["class_order"],
        results["importance"],
        lambda _: None,
    )
    print(
        json.dumps(
            {
                "classifier": args.classifier,
                "case": args.case,
                "rows": n,
                "features": 50,
                "csv_bytes": len(source),
                "encoded_estimate": config["encoded_columns"],
                "encoded_actual": pipeline["preprocessor"]
                .transform(pipeline["semantics"].transform(typed[list(types)].iloc[:1]))
                .shape[1],
                "validation_seconds": validation_seconds,
                "training_seconds": training_seconds,
                "monitoring_seconds": time.monotonic() - start,
                "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "artifact_bytes": {
                    "canonical": len(canonical),
                    "model": len(dump(pipeline)),
                    "reference": len(reference.to_parquet(index=False)),
                    "membership": len(membership.to_parquet(index=False)),
                },
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
