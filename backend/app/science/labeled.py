"""M4 labeled comparisons. Historical baseline values are read, never reevaluated."""

from collections.abc import Callable
from typing import Any

import numpy as np

from backend.app.science.baseline import calibration, evaluate
from backend.app.science.monitoring import (
    MODE_A_LIMITATION,
    analyze_mode_a,
    predict_probabilities,
)

PERFORMANCE_LIMITATION = (
    "Small metric differences may reflect sampling variation. ModelMedic V1 does not estimate "
    "uncertainty intervals for performance changes."
)
MODE_B_STATEMENT = (
    "Labels were provided, so performance and calibration were measured. "
    "Read every comparison with its sample sizes and limitations."
)
CLASS_COMPOSITION_CAUTION = (
    "Class composition changed; aggregate probability-metric deltas should be interpreted "
    "cautiously because the absent class has no current outcome support."
)


def comparison(
    name: str,
    baseline: dict[str, Any],
    current: dict[str, Any],
    baseline_n: int,
    current_n: int,
    note: str | None = None,
    class_label: str | None = None,
) -> dict[str, Any]:
    b, c = baseline["value"], current["value"]
    reason = current["reason"] or (
        "Baseline unavailable: " + baseline["reason"] if baseline["reason"] else None
    )
    return {
        "metric_name": name,
        "class_label": class_label,
        "baseline_value": b,
        "current_value": c,
        "delta": float(c - b) if b is not None and c is not None else None,
        "baseline_support": baseline_n,
        "current_support": current_n,
        "status": "AVAILABLE" if b is not None and c is not None else "UNAVAILABLE",
        "reason": reason,
        "note": note,
    }


def performance(
    y: Any,
    predicted: Any,
    probabilities: Any,
    classes: list[str],
    positive: str | None,
    baseline_metrics: dict[str, Any],
) -> dict[str, Any]:
    current = evaluate(y, predicted, probabilities, classes, positive)
    absent = [c["class"] for c in current["per_class"] if c["support"] == 0]
    if absent:
        for name in current["metrics"]:
            if name.startswith("macro_") or name == "balanced_accuracy":
                current["metrics"][name] = {
                    "value": None,
                    "reason": "Unavailable for direct comparison: not all frozen classes have "
                    "current support. Different class sets must not be compared as equivalent.",
                }
        if len(classes) > 2:
            supported = [c for c in current["per_class"] if c["support"] > 0]
            if all(c["f1"]["value"] is not None for c in supported):
                current["metrics"]["weighted_f1"] = {
                    "value": float(
                        sum(c["f1"]["value"] * c["support"] for c in supported) / len(y)
                    ),
                    "reason": None,
                }
    rows = [
        comparison(
            name,
            baseline_metrics["metrics"][name],
            score,
            baseline_metrics["support"],
            len(y),
            CLASS_COMPOSITION_CAUTION if absent and name in {"log_loss", "brier"} else None,
        )
        for name, score in current["metrics"].items()
    ]
    per_class = []
    for b, c in zip(baseline_metrics["per_class"], current["per_class"], strict=True):
        if b["class"] != c["class"]:
            raise ValueError("Historical class order does not match frozen class order.")
        per_class.append(
            {
                "class": c["class"],
                "baseline_support": b["support"],
                "current_support": c["support"],
                "metrics": [
                    comparison(
                        k,
                        b[k],
                        c[k],
                        b["support"],
                        c["support"],
                        "No current outcome support for this class." if not c["support"] else None,
                        c["class"],
                    )
                    for k in ("precision", "recall", "f1")
                ],
            }
        )
    return {
        "metrics": rows,
        "per_class": per_class,
        "class_order": classes,
        "baseline_n": baseline_metrics["support"],
        "current_n": len(y),
        "absent_classes": absent,
        "warnings": ["Absent current classes: " + ", ".join(absent), CLASS_COMPOSITION_CAUTION]
        if absent
        else [],
        "limitation": PERFORMANCE_LIMITATION,
        "class_composition": [
            {
                "category": c["class"],
                "baseline_count": b["support"],
                "current_count": c["support"],
                "baseline_share": b["support"] / baseline_metrics["support"],
                "current_share": c["support"] / len(y),
                "delta_pp": 100
                * (c["support"] / len(y) - b["support"] / baseline_metrics["support"]),
            }
            for b, c in zip(baseline_metrics["per_class"], current["per_class"], strict=True)
        ],
        "current_evaluation": current,
    }


def matrix_data(
    matrix: list[list[int]], classes: list[str], positive: str | None
) -> dict[str, Any]:
    normalized = []
    pairs: list[dict[str, Any]] = []
    for i, row in enumerate(matrix):
        n = sum(row)
        normalized.append([v / n if n else None for v in row])
        for j, count in enumerate(row):
            if i != j and count:
                pairs.append(
                    {
                        "view": f"pair-{i}-{j}",
                        "actual": classes[i],
                        "predicted": classes[j],
                        "count": count,
                        "actual_support": n,
                        "rate": count / n,
                    }
                )
    pairs.sort(key=lambda p: (-p["count"], p["view"]))
    output: dict[str, Any] = {"counts": matrix, "normalized": normalized, "common_pairs": pairs}
    if len(classes) == 2:
        assert positive in classes
        p = classes.index(positive)
        n = 1 - p
        output["binary"] = {
            "tp": matrix[p][p],
            "tn": matrix[n][n],
            "fp": matrix[n][p],
            "fn": matrix[p][n],
        }
    return output


def errors(
    y: Any,
    predicted: Any,
    row_ids: Any,
    classes: list[str],
    positive: str | None,
    baseline_matrix: list[list[int]],
    current_matrix: list[list[int]],
) -> dict[str, Any]:
    references: dict[str, list[int]] = {}
    for i, actual in enumerate(classes):
        for j, estimated in enumerate(classes):
            if i == j:
                continue
            ids = np.asarray(row_ids)[
                (np.asarray(y) == actual) & (np.asarray(predicted) == estimated)
            ]
            references[f"pair-{i}-{j}"] = [int(v) for v in ids[:50]]
    if len(classes) == 2:
        assert positive in classes
        p = classes.index(positive)
        references["fp"] = references[f"pair-{1 - p}-{p}"]
        references["fn"] = references[f"pair-{p}-{1 - p}"]
    return {
        "class_order": classes,
        "positive_class": positive,
        "baseline": matrix_data(baseline_matrix, classes, positive),
        "current": matrix_data(current_matrix, classes, positive),
        "row_references": references,
        "example_limit": 50,
        "normalization": "Row-normalized by actual-class support; no support is Unavailable.",
    }


def analyze_mode_b(
    baseline: Any,
    current: Any,
    reference: Any,
    features: list[dict[str, Any]],
    pipeline: Any,
    classes: list[str],
    reliance: list[dict[str, Any]],
    baseline_results: dict[str, Any],
    target: str,
    positive: str | None,
    on_stage: Callable[[str], None],
) -> dict[str, Any]:
    # Inference exactly once; Mode A drift and model-behaviour calculations are reused unchanged.
    on_stage("PREDICTING")
    predicted, probabilities = predict_probabilities(pipeline, current, classes)
    result = analyze_mode_a(
        baseline,
        current,
        reference,
        features,
        pipeline,
        classes,
        reliance,
        lambda s: on_stage(s) if s != "PREDICTING" else None,
        (predicted, probabilities.max(axis=1)),
    )
    y = current[target].map(lambda v: v.strip()).to_numpy()
    on_stage("PERFORMANCE")
    measured = performance(
        y, predicted, probabilities, classes, positive, baseline_results["metrics"]
    )
    current_metrics = measured.pop("current_evaluation")
    result["performance"] = measured
    result["errors"] = errors(
        y,
        predicted,
        current["__mm_row_id"],
        classes,
        positive,
        baseline_results["metrics"]["confusion_matrix"],
        current_metrics["confusion_matrix"],
    )
    on_stage("CALIBRATION")
    result["calibration"] = {
        "baseline": baseline_results["calibration"],
        "current": calibration(y, probabilities, classes, positive),
        "class_order": [positive] if len(classes) == 2 else classes,
        "metrics": [m for m in measured["metrics"] if m["metric_name"] in {"brier", "log_loss"}],
        "limitation": PERFORMANCE_LIMITATION,
    }
    result["mode"] = "B"
    result["limitation"] = MODE_B_STATEMENT
    result["limitations"] = [v for v in result["limitations"] if v != MODE_A_LIMITATION] + [
        PERFORMANCE_LIMITATION
    ]
    return result
