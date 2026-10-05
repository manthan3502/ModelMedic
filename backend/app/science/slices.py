"""Exploratory categorical partitions; no hypothesis tests or cross-slice ranking."""

from typing import Any

import numpy as np

from backend.app.science.labeled import performance

SLICE_METHODOLOGY_VERSION = "slices-v1"
SLICE_LIMITATION = (
    "Slice comparisons are exploratory. ModelMedic does not perform significance testing or "
    "multiplicity correction across slices. Apparent differences may reflect sampling variation. "
    "This is not a fairness audit."
)
INSUFFICIENT_SLICE = "Insufficient sample size for stable slice analysis."


def analyze_slices(
    values: Any,
    y: Any,
    predicted: Any,
    probabilities: Any,
    classes: list[str],
    positive: str | None,
    baseline_metrics: dict[str, Any],
) -> list[dict[str, Any]]:
    observed = [
        None if v is None or isinstance(v, float) and np.isnan(v) else str(v) for v in values
    ]
    categories = sorted(set(v for v in observed if v is not None))
    groups: list[tuple[str, str | None, Any]] = [("all", None, np.ones(len(y), dtype=bool))]
    if None in observed:
        groups.append(("missing", None, np.array([v is None for v in observed])))
    groups.extend(
        (f"category-{i}", v, np.array([x == v for x in observed])) for i, v in enumerate(categories)
    )
    output = []
    for key, value, mask in groups:
        labels = np.asarray(y)[mask]
        support = {c: int(np.sum(labels == c)) for c in classes}
        metrics = {}
        if len(labels) >= 30:
            result = performance(
                labels,
                np.asarray(predicted)[mask],
                np.asarray(probabilities)[mask],
                classes,
                positive,
                baseline_metrics,
            )
            metrics = {
                m["metric_name"]: {
                    "value": m["current_value"],
                    "reason": result["current_evaluation"]["metrics"][m["metric_name"]]["reason"],
                    "note": m["note"],
                }
                for m in result["metrics"]
            }
        output.append(
            {
                "slice_key": key,
                "slice_value": value,
                "is_overall": key == "all",
                "row_count": len(labels),
                "class_support": support,
                "metrics": metrics,
                "status": "AVAILABLE" if metrics else "INSUFFICIENT DATA",
                "reason": None if metrics else INSUFFICIENT_SLICE,
            }
        )
    return output
