"""M3 raw-data comparisons and persisted plot values. No fitting or outcome metrics."""

from collections import Counter
from collections.abc import Callable
from typing import Any

import numpy as np
from scipy.spatial.distance import jensenshannon
from scipy.stats import (
    chi2_contingency,
    false_discovery_control,
    fisher_exact,
    ks_2samp,
    wasserstein_distance,
)

METHODOLOGY_VERSION = "monitoring-v1"
MODE_A_LIMITATION = (
    "Actual current predictive performance and calibration cannot be measured because "
    "ground-truth labels were not provided."
)
CONFIDENCE_LIMITATION = "Confidence change does not prove accuracy or calibration changed."
FROZEN_STATEMENT = (
    "The established model and preprocessing are applied exactly as frozen. "
    "Nothing is retrained, refitted or updated from this file."
)


def status(p: float | None) -> str:
    return "INSUFFICIENT DATA" if p is None else "DETECTED" if p < 0.05 else "NOT DETECTED"


def test_result(nb: int, nc: int, test: str | None = None) -> dict[str, Any]:
    return {
        "baseline_n": nb,
        "current_n": nc,
        "test": test,
        "statistic": None,
        "raw_p": None,
        "adjusted_p": None,
        "status": "INSUFFICIENT DATA",
    }


def histogram(base: Any, current: Any, confidence: bool = False) -> dict[str, Any]:
    """Baseline-derived bins with explicit overflow; fixed [0,1] for confidence."""
    if confidence:
        edges = np.linspace(0, 1, 11)
    elif len(base):
        low, high = float(np.min(base)), float(np.max(base))
        if low == high:
            width = max(abs(low) * 0.01, 0.5)
            low, high = low - width, high + width
        shared = np.linspace(low, high, 11)
        shared[-1] = np.nextafter(high, np.inf)  # Baseline maximum stays in its last finite bin.
        edges = np.r_[-np.inf, shared, np.inf]
    else:
        return {"bins": [], "reason": "No observed baseline values define histogram bins."}
    b = np.histogram(base, edges)[0]
    c = np.histogram(current, edges)[0]
    return {
        "bins": [
            {
                "lower": float(edges[i]) if np.isfinite(edges[i]) else None,
                "upper": float(edges[i + 1]) if np.isfinite(edges[i + 1]) else None,
                "baseline_count": int(b[i]),
                "current_count": int(c[i]),
                "baseline_share": float(b[i] / len(base)) if len(base) else 0.0,
                "current_share": float(c[i] / len(current)) if len(current) else 0.0,
            }
            for i in range(len(b))
        ],
        "reason": None,
    }


def numeric_drift(base: list[float], current: list[float]) -> dict[str, Any]:
    b, c = np.asarray(base, dtype=float), np.asarray(current, dtype=float)
    result = test_result(len(b), len(c), "KS two-sample")
    result.update(
        {
            "distance_name": "Wasserstein-1",
            "distance": None,
            "baseline_min": None,
            "baseline_max": None,
            "outside_range_share": None,
            "warnings": [],
            "plot": histogram(b, c),
        }
    )
    if len(b):
        low, high = float(np.min(b)), float(np.max(b))
        result.update(baseline_min=low, baseline_max=high)
        if len(c):
            result["outside_range_share"] = float(np.mean((c < low) | (c > high)))
            result["distance"] = float(wasserstein_distance(b, c))
        if len(np.unique(b)) <= 10 or len(np.unique(b)) < len(b) / 2:
            result["warnings"].append(
                "Tied/discrete numeric feature: the continuous KS assumption is imperfect."
            )
    if min(len(b), len(c)) >= 30:
        test = ks_2samp(b, c, method="auto")
        result.update(statistic=float(test.statistic), raw_p=float(test.pvalue))
        result["status"] = status(result["raw_p"])
    else:
        result["reason"] = "Distribution testing requires at least 30 observed values per sample."
    return result


def categorical_drift(
    base: list[str], current: list[str], order: list[str] | None = None
) -> dict[str, Any]:
    b, c = Counter(base), Counter(current)
    categories = order if order is not None else sorted(b.keys() | c.keys())
    nb, nc = len(base), len(current)
    result = test_result(nb, nc, "Chi-square")
    result.update(
        {
            "distance_name": "Jensen-Shannon (base 2)",
            "distance": None,
            "new_categories": sorted(c.keys() - b.keys()),
            "disappeared_categories": sorted(b.keys() - c.keys()),
            "warnings": [],
            "pooling_threshold": None,
            "pooling": [],
            "expected_counts": [],
            "reason": None,
            "categories": [
                {
                    "category": k,
                    "baseline_count": b[k],
                    "current_count": c[k],
                    "baseline_share": b[k] / nb if nb else 0.0,
                    "current_share": c[k] / nc if nc else 0.0,
                    "delta_pp": 100 * ((c[k] / nc if nc else 0) - (b[k] / nb if nb else 0)),
                }
                for k in categories
            ],
        }
    )
    if nb and nc:
        result["distance"] = float(
            jensenshannon([b[k] / nb for k in categories], [c[k] / nc for k in categories], base=2)
        )
    if min(nb, nc) < 30:
        result["reason"] = "Distribution testing requires at least 30 observed values per sample."
        return result
    threshold = 5 * (nb + nc) / min(nb, nc)
    result["pooling_threshold"] = threshold
    observed = [k for k in categories if b[k] + c[k] > 0]
    pooled = [k for k in observed if b[k] + c[k] < threshold]
    retained = [k for k in observed if k not in pooled]
    # Internal bucket identity is independent of its display label: raw __MM_OTHER__ is safe.
    groups: list[dict[str, Any]] = [
        {"id": f"retained-{i}", "label": k, "members": [k]} for i, k in enumerate(retained)
    ]
    if pooled:
        total = sum(b[k] + c[k] for k in pooled)
        if total * min(nb, nc) / (nb + nc) < 5 and groups:
            smallest = min(groups, key=lambda g: (b[g["label"]] + c[g["label"]], g["label"]))
            smallest["members"].extend(pooled)
        else:
            groups.append({"id": "pooled", "label": "__MM_OTHER__", "members": pooled})
    result["pooling"] = groups
    if len(groups) < 2:
        result["reason"] = "Pooling leaves fewer than two test categories."
        return result
    table = np.asarray(
        [[sum(counts[k] for k in g["members"]) for g in groups] for counts in (b, c)], dtype=int
    )
    expected = np.outer(table.sum(axis=1), table.sum(axis=0)) / table.sum()
    result["expected_counts"] = expected.tolist()
    if np.any(expected < 5):
        result["reason"] = "At least one expected cell is below five after pooling."
        return result
    test = chi2_contingency(table, correction=False)
    result.update(statistic=float(test.statistic), raw_p=float(test.pvalue))
    result["status"] = status(result["raw_p"])
    return result


def missingness(nb: int, nc: int, mb: int, mc: int) -> dict[str, Any]:
    result = test_result(nb, nc)
    result.update(
        {
            "baseline_missing_count": mb,
            "current_missing_count": mc,
            "baseline_missing_percent": 100 * mb / nb,
            "current_missing_percent": 100 * mc / nc,
            "delta_pp": 100 * (mc / nc - mb / nb),
        }
    )
    if mb == mc == 0:
        result.update(status="NOT DETECTED", reason="Neither sample contains missing values.")
        return result
    table = np.asarray([[mb, nb - mb], [mc, nc - mc]])
    expected = np.outer(table.sum(axis=1), table.sum(axis=0)) / table.sum()
    result["expected_counts"] = expected.tolist()
    if np.all(expected >= 5):
        test = chi2_contingency(table, correction=False)
        result.update(test="Chi-square", statistic=float(test.statistic), raw_p=float(test.pvalue))
    else:
        test = fisher_exact(table, alternative="two-sided")
        # Infinite/undefined odds ratios are not serialized as scientific JSON numbers.
        result.update(test="Fisher exact", statistic=None, raw_p=float(test.pvalue))
    result["status"] = status(result["raw_p"])
    return result


def correct_family(features: list[dict[str, Any]]) -> int:
    family = [
        f[k]
        for f in features
        for k in ("distribution", "missingness")
        if f[k]["raw_p"] is not None and f[k]["status"] != "INSUFFICIENT DATA"
    ]
    if family:
        for item, adjusted in zip(
            family, false_discovery_control([f["raw_p"] for f in family], method="bh"), strict=True
        ):
            item["adjusted_p"] = float(adjusted)
            item["status"] = status(item["adjusted_p"])
    for f in features:
        for k in ("distribution", "missingness"):
            f[k]["bh_family_size"] = len(family)
    return len(family)


def confidence_drift(base: Any, current: Any) -> dict[str, Any]:
    b, c = np.asarray(base, dtype=float), np.asarray(current, dtype=float)
    result = test_result(len(b), len(c), "KS two-sample")
    result.update(
        {
            "baseline_mean": float(np.mean(b)),
            "current_mean": float(np.mean(c)),
            "baseline_median": float(np.median(b)),
            "current_median": float(np.median(c)),
            "plot": histogram(b, c, confidence=True),
            "limitation": CONFIDENCE_LIMITATION,
        }
    )
    if min(len(b), len(c)) >= 30:
        test = ks_2samp(b, c, method="auto")
        result.update(statistic=float(test.statistic), raw_p=float(test.pvalue))
        result["status"] = status(result["raw_p"])
    return result


def predict_probabilities(pipeline: Any, current: Any, classes: list[str]) -> tuple[Any, Any]:
    model_order = [str(c) for c in pipeline.classes_]
    if set(model_order) != set(classes) or len(model_order) != len(classes):
        raise ValueError("Frozen model classes do not match the baseline manifest.")
    probabilities = np.asarray(pipeline.predict_proba(current))[
        :, [model_order.index(c) for c in classes]
    ]
    if (
        probabilities.shape != (len(current), len(classes))
        or not np.isfinite(probabilities).all()
        or np.any(probabilities < 0)
        or np.any(probabilities > 1)
        or not np.allclose(probabilities.sum(axis=1), 1)
    ):
        raise ValueError("Frozen model probabilities are invalid.")
    predictions = np.asarray(pipeline.predict(current), dtype=str)
    if not set(predictions).issubset(classes):
        raise ValueError("Frozen model predictions are outside the baseline class space.")
    return predictions, probabilities


def predict_frozen(pipeline: Any, current: Any, classes: list[str]) -> tuple[Any, Any]:
    predictions, probabilities = predict_probabilities(pipeline, current, classes)
    return predictions, probabilities.max(axis=1)


def analyze_mode_a(
    baseline: Any,
    current: Any,
    reference: Any,
    features: list[dict[str, Any]],
    pipeline: Any,
    classes: list[str],
    reliance: list[dict[str, Any]],
    on_stage: Callable[[str], None],
    frozen_output: tuple[Any, Any] | None = None,
) -> dict[str, Any]:
    on_stage("PREDICTING")
    predicted, confidence = (
        frozen_output if frozen_output is not None else predict_frozen(pipeline, current, classes)
    )
    on_stage("DATA_DRIFT")
    results = []
    for f in features:
        name, kind = f["name"], f["type"]
        # Read raw canonical values, independent of the fitted transformer's output.
        b, c = baseline[name].dropna().tolist(), current[name].dropna().tolist()
        d = (
            numeric_drift([float(x) for x in b], [float(x) for x in c])
            if kind == "numeric"
            else categorical_drift(b, c)
        )
        results.append(
            {
                **f,
                "distribution": d,
                "reliance": next((r for r in reliance if r["feature"] == name), None),
            }
        )
    on_stage("MISSINGNESS")
    for f in results:
        name = f["name"]
        f["missingness"] = missingness(
            len(baseline),
            len(current),
            int(baseline[name].isna().sum()),
            int(current[name].isna().sum()),
        )
    family_size = correct_family(results)
    on_stage("PREDICTION_DRIFT")
    prediction = categorical_drift(reference["__mm_y_pred"].tolist(), predicted.tolist(), classes)
    prediction["class_order"] = classes
    prediction["interpretation"] = (
        "Prediction distribution changed."
        if prediction["status"] == "DETECTED"
        else "No evidence of a prediction distribution difference was detected in these samples."
        if prediction["status"] == "NOT DETECTED"
        else "Prediction distribution testing has insufficient data."
    )
    prediction["limitation"] = (
        "Prediction shift does not tell you whether the predictions are correct."
    )
    on_stage("CONFIDENCE")
    confidence_result = confidence_drift(reference["__mm_confidence"], confidence)
    return {
        "mode": "A",
        "methodology_version": METHODOLOGY_VERSION,
        "limitation": MODE_A_LIMITATION,
        "frozen_statement": FROZEN_STATEMENT,
        "data_reference": "Baseline — all valid baseline rows",
        "model_reference": "Baseline — held-out reference",
        "features": results,
        "bh_family_size": family_size,
        "predictions": prediction,
        "confidence": confidence_result,
        "counts": {
            s: sum(f["distribution"]["status"] == s for f in results)
            for s in ("DETECTED", "NOT DETECTED", "INSUFFICIENT DATA")
        },
        "tested_features": sum(f["distribution"]["raw_p"] is not None for f in results),
        "missingness_detected": sum(f["missingness"]["status"] == "DETECTED" for f in results),
        "limitations": [
            MODE_A_LIMITATION,
            CONFIDENCE_LIMITATION,
            "Drift does not prove predictive degradation.",
            "Statistical significance does not imply practical importance.",
            "Model reliance estimate — not causal importance.",
            "Small samples may be unstable. ModelMedic does not establish causality.",
            "NOT DETECTED does not prove that populations are identical.",
        ],
    }
