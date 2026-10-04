"""Deterministic import/profile rules. No preprocessing is learned here."""

import csv
import hashlib
import io
import json
import math
import re
from collections import Counter
from collections.abc import Callable
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from backend.app.core.config import Settings

SCHEMA_VERSION = "canonical-v1"
MISSING_LITERALS = {"NA", "N/A", "None", "null", "unknown", "?"}


class DatasetError(Exception):
    """Reviewed diagnostics only; never include a raw row or parser exception."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def missing(value: str) -> bool:
    return not value.strip()


def numeric(value: str) -> bool:
    try:
        return math.isfinite(float(value))
    except (ValueError, OverflowError):
        return False


def target_info(values: list[str | None]) -> dict[str, Any]:
    observed = [v for v in values if v is not None]
    raw = set(observed)
    labels = sorted({v.strip() for v in observed})
    counts = Counter(v.strip() for v in observed)
    reasons = []
    if len(observed) != len(values):
        reasons.append("Target labels must be present in every row.")
    if len(labels) != len(raw):
        reasons.append(
            "Labels differ only by whitespace; clean the source to avoid merging classes."
        )
    for label in raw:
        try:
            parsed_label = json.loads(label)
        except (ValueError, TypeError):
            continue
        if isinstance(parsed_label, (list, dict)):
            reasons.append(
                "Multilabel or structured target cells are unsupported; use one class per row."
            )
            break
    if not 2 <= len(labels) <= 10:
        reasons.append("Select a binary target (2 classes) or multiclass target (3–10 classes).")
    if len(values) < max(200, 100 * len(labels)) or any(n < 100 for n in counts.values()):
        reasons.append(
            "Baseline needs at least 100 rows per class and max(200, 100 × classes) rows."
        )
    # Discrete numeric labels (including decimals) remain valid class labels.
    # Numeric outcomes outside the locked class cap cannot be classification targets.
    if observed and all(numeric(v) for v in observed) and len(labels) > 10:
        reasons.append("Continuous numeric targets are unsupported; use discrete class labels.")
    return {
        "eligible": not reasons,
        "reasons": reasons,
        "class_balance_note": (
            "Class counts are unequal. Review the proportions and weighting choice; "
            "there is no universal imbalance cutoff."
            if counts and len(set(counts.values())) > 1
            else None
        ),
        "classes": [
            {"label": label, "count": counts[label], "proportion": counts[label] / len(values)}
            for label in labels
        ]
        if len(labels) <= 10
        else [],
    }


def validate_csv(
    content: bytes, settings: Settings, on_stage: Callable[[str], None] | None = None
) -> tuple[bytes, dict[str, Any]]:
    if len(content) > settings.upload_max_bytes:
        raise DatasetError("CSV exceeds the configured byte limit. Use a smaller file.")
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise DatasetError("Use a UTF-8 encoded CSV file; this encoding is unsupported.") from None
    if "\x00" in decoded:
        raise DatasetError("CSV contains null bytes. Export a plain UTF-8 CSV.")
    try:
        reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
        if on_stage:
            on_stage("CHECKING_COLUMNS")
        headers = next(reader, [])
        if not headers or any(not h.strip() for h in headers):
            raise DatasetError("CSV requires a non-empty header for every column.")
        if len(headers) > settings.max_columns:
            raise DatasetError("CSV exceeds the configured input-column limit.")
        if len(set(h.strip() for h in headers)) != len(headers):
            raise DatasetError("Duplicate column names are unsupported; use unique headers.")
        if any(h.strip().startswith("__mm_") for h in headers):
            raise DatasetError("Column names beginning __mm_ are reserved. Rename these columns.")
        rows: list[list[str | None]] = []
        for row in reader:
            if len(row) != len(headers):
                raise DatasetError(
                    "CSV row widths must match the header. Check delimiters and quoting."
                )
            rows.append([None if missing(v) else v for v in row])
            if len(rows) > settings.max_rows:
                raise DatasetError("CSV exceeds the configured row limit.")
    except csv.Error:
        raise DatasetError("Malformed CSV. Check quoting, delimiters and cell sizes.") from None
    if not rows:
        raise DatasetError("CSV has no data rows. Include a header and observations.")
    columns = []
    arrays = [pa.array(range(len(rows)), type=pa.uint64())]
    for index, header in enumerate(headers):
        values = [row[index] for row in rows]
        observed = [v for v in values if v is not None]
        distinct = set(observed)
        is_numeric = bool(observed) and all(numeric(v) for v in observed)
        kind = "numeric" if is_numeric else "categorical"
        flags = []
        unsupported = None
        if len(distinct) <= 1:
            flags.append("Constant column; consider excluding it.")
        if len(observed) < len(rows) / 2:
            flags.append("High missingness: more than half of values are missing.")
        if is_numeric and len(distinct) <= 10:
            flags.append("Review feature type — this feature may represent categories.")
        if len(distinct) == len(rows) or re.search(
            r"(^|[_\s])(id|identifier)($|[_\s])", header, re.I
        ):
            flags.append("Likely identifier; review whether this belongs in the model.")
        if (
            any(v.strip() in MISSING_LITERALS for v in observed)
            and any(numeric(v) for v in observed)
            and all(numeric(v) or v.strip() in MISSING_LITERALS for v in observed)
        ):
            flags.append(
                "Numeric-looking column contains literal missing-like strings "
                "(NA/N/A/None/null/unknown/?). These remain values; "
                "clean the source or use categories."
            )
        if len({v.strip() for v in distinct}) != len(distinct):
            flags.append(
                "Categories differ only by surrounding whitespace; values have not been merged."
            )
        if observed and all(
            re.fullmatch(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:[T ].*)?", v.strip()) for v in observed
        ):
            unsupported = "Datetime features are unsupported; transform the source explicitly."
        elif not is_numeric and any(len(v) > 200 or len(v.split()) > 15 for v in observed):
            unsupported = "Free-text features are unsupported."
        elif not is_numeric and len(distinct) > settings.max_categories:
            unsupported = "Categorical cardinality exceeds the configured modelling limit."
        if unsupported:
            flags.append(unsupported)
        columns.append(
            {
                "feature_id": f"f{index:03d}",
                "name": header,
                "inferred_type": kind,
                "missing_count": len(rows) - len(observed),
                "distinct_count": len(distinct),
                "samples": list(dict.fromkeys(observed))[:3],
                "flags": flags,
                "unsupported_reason": unsupported,
                "allowed_types": []
                if unsupported
                else (
                    ["numeric"]
                    + (["categorical"] if len(distinct) <= settings.max_categories else [])
                    if is_numeric
                    else ["categorical"]
                ),
                "target": target_info(values),
            }
        )
        # Lossless lexical strings retain categories such as 001 versus 1 for valid overrides.
        # Missing cells alone become Arrow null; numeric conversion is a later frozen type step.
        arrays.append(pa.array(values, type=pa.string()))
    if on_stage:
        on_stage("BUILDING_TYPED_COPY")
    table = pa.Table.from_arrays(arrays, names=["__mm_row_id", *headers]).replace_schema_metadata(
        {b"modelmedic.schema_version": SCHEMA_VERSION.encode()}
    )
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
        "duplicate_rows": len(rows) - len({tuple(row) for row in rows}),
        "columns": columns,
        "preview": rows[:10],
        "canonical_sha256": hashlib.sha256(canonical).hexdigest(),
        "canonical_schema_version": SCHEMA_VERSION,
    }
    return canonical, profile


def validate_configuration(
    profile: dict[str, Any], config: dict[str, Any], settings: Settings
) -> dict[str, Any]:
    columns = {c["feature_id"]: c for c in profile["columns"]}
    target = columns.get(config["target_id"])
    if not target or not target["target"]["eligible"]:
        raise DatasetError("Select an eligible target; review the profile's target diagnostics.")
    classes = [c["label"] for c in target["target"]["classes"]]
    positive = config.get("positive_class")
    if len(classes) == 2 and positive not in classes:
        raise DatasetError("Select a positive class for binary classification.")
    if len(classes) > 2 and positive is not None:
        raise DatasetError("Positive-class selection applies only to binary classification.")
    seen: set[str] = set()
    encoded = 0
    for feature in config["features"]:
        feature_id = feature["feature_id"]
        column = columns.get(feature_id)
        if not column or feature_id == config["target_id"] or feature_id in seen:
            raise DatasetError("Choose each input feature once and exclude the target from inputs.")
        seen.add(feature_id)
        if feature["type"] not in column["allowed_types"]:
            raise DatasetError(
                "Unsupported feature or invalid type override. Review column diagnostics."
            )
        encoded += 1 if feature["type"] == "numeric" else column["distinct_count"] + 1
    if not seen or len(seen) > settings.max_features:
        raise DatasetError("Include at least one feature, within the configured feature limit.")
    if encoded > settings.max_encoded_columns:
        raise DatasetError("Encoded-column estimate exceeds the configured computational limit.")
    return {
        **config,
        "class_order": classes,
        "encoded_columns": encoded,
        "target_normalization": "surrounding_whitespace_without_merging",
    }


def preprocessing_summary(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "steps": [
            "Raw columns",
            "Handle missing values",
            "Encode categories",
            "Scale numeric values when required",
            "Classifier",
        ],
        "numeric": (
            "Median imputation for every classifier. StandardScaler for Logistic Regression only."
        ),
        "categorical": "Explicit missing category and one-hot encoding for every classifier.",
        "learning": (
            "Learned from the Development 80% only; "
            "held-out reference is never used to fit preprocessing."
        ),
        "frozen": "Frozen after baseline establishment; later datasets never refit preprocessing.",
        "fitted": False,
        "scaling_required": config.get("classifier") == "logistic_regression",
    }
