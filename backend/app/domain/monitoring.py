"""Current import semantics are taken exclusively from the established snapshot."""

from hashlib import sha256
from io import BytesIO
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from backend.app.core.config import Settings
from backend.app.domain.datasets import SCHEMA_VERSION, DatasetError, numeric, parse_csv


def frozen_features(profile: dict[str, Any], config: dict[str, Any]) -> list[dict[str, str]]:
    names = {c["feature_id"]: c["name"] for c in profile["columns"]}
    return [
        {"feature_id": f["feature_id"], "name": names[f["feature_id"]], "type": f["type"]}
        for f in config["features"]
    ]


def validate_current(
    content: bytes,
    settings: Settings,
    baseline_content: bytes,
    baseline_profile: dict[str, Any],
    config: dict[str, Any],
) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    headers, rows = parse_csv(content, settings)
    if len(rows) < 50:
        raise DatasetError("Monitoring requires at least 50 rows. No rows were deleted.")
    features = frozen_features(baseline_profile, config)
    required = [f["name"] for f in features]
    if not set(required).issubset(headers):
        raise DatasetError(
            "Required frozen model features are missing. Include every model feature."
        )
    target = next(
        c["name"] for c in baseline_profile["columns"] if c["feature_id"] == config["target_id"]
    )
    values = {h: [r[i] for r in rows] for i, h in enumerate(headers)}
    mode = "A"
    if target in headers:
        labels = values[target]
        if any(v is None for v in labels):
            raise DatasetError(
                "Target column must be absent for Mode A or completely labeled for Mode B."
            )
        raw_labels = {v for v in labels if v is not None}
        if len(raw_labels) != len({v.strip() for v in raw_labels}):
            raise DatasetError(
                "Target labels differ only by whitespace; clean the source without merging classes."
            )
        if not {v.strip() for v in raw_labels}.issubset(config["class_order"]):
            raise DatasetError(
                "Unknown target class blocks Mode B. Use the frozen baseline classes."
            )
        mode = "B"
    baseline = pq.read_table(BytesIO(baseline_content))
    extras = [h for h in headers if h not in required and h != target]
    warnings = ["Extra columns are allowed and ignored for model inference."] if extras else []
    coercions = []
    new_categories = []
    for f in features:
        observed = [v for v in values[f["name"]] if v is not None]
        if f["type"] == "numeric":
            if not all(numeric(v) for v in observed):
                raise DatasetError(
                    "A frozen numeric feature contains non-numeric or non-finite values. "
                    "Clean the source."
                )
            coercions.append(
                {
                    "feature_id": f["feature_id"],
                    "name": f["name"],
                    "observed_count": len(observed),
                    "conversion": (
                        "CSV numeric strings to finite numbers in frozen inference and raw tests."
                    ),
                }
            )
        else:
            old = set(baseline[f["name"]].drop_null().to_pylist())
            new = sorted(set(observed) - old)
            new_categories.append(
                {"feature_id": f["feature_id"], "name": f["name"], "categories": new}
            )
            if new:
                warnings.append("New categories are reported; the frozen encoder is not updated.")
            combined = old | set(observed)
            if len(combined) != len({v.strip() for v in combined}):
                warnings.append(
                    "Categories differ only by whitespace; "
                    "raw values have not been trimmed or merged."
                )
    table = pa.Table.from_arrays(
        [
            pa.array(range(len(rows)), type=pa.uint64()),
            *[pa.array(values[h], type=pa.string()) for h in headers],
        ],
        names=["__mm_row_id", *headers],
    ).replace_schema_metadata({b"modelmedic.schema_version": SCHEMA_VERSION.encode()})
    buffer = pa.BufferOutputStream()
    pq.write_table(
        table,
        buffer,
        version="2.6",
        compression="zstd",
        use_dictionary=False,
        write_statistics=False,
    )
    canonical = buffer.getvalue().to_pybytes()
    profile = {
        "row_count": len(rows),
        "column_count": len(headers),
        "duplicate_rows": len(rows) - len({tuple(r) for r in rows}),
        "features": features,
        "canonical_sha256": sha256(canonical).hexdigest(),
        "canonical_schema_version": SCHEMA_VERSION,
    }
    report = {
        "errors": [],
        "warnings": list(dict.fromkeys(warnings)),
        "mode": mode,
        "required_features": required,
        "ignored_extra_columns": extras,
        "coercions": coercions,
        "new_categories": new_categories,
    }
    return canonical, profile, report
