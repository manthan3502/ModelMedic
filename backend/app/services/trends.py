"""Select one persisted historical signal; never reevaluate, interpolate or forecast."""

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import BaselineSnapshot, Dataset, MonitoringRun

METHODOLOGY_CAUTION = (
    "Methodology versions differ across these runs. Direct comparison "
    "may require care. Historical values have not been recomputed."
)


def signal_options(classes: list[str]) -> dict[str, list[str]]:
    return {
        "performance": [
            "balanced_accuracy",
            "f1",
            "precision",
            "recall",
            "roc_auc",
            "average_precision",
        ]
        if len(classes) == 2
        else [
            "balanced_accuracy",
            "macro_f1",
            "macro_precision",
            "macro_recall",
            "macro_ovr_roc_auc",
        ],
        "probability": ["brier", "log_loss"],
        "confidence": ["median", "mean"],
        "predictions": ["class_share"],
        "data": ["ks", "js", "missing_percent"],
    }


def selected_value(
    results: dict[str, Any] | None,
    group: str,
    signal: str,
    feature_id: str | None,
    class_label: str | None,
    baseline: bool = False,
) -> dict[str, Any]:
    unavailable = {
        "value": None,
        "n": None,
        "status": "UNAVAILABLE",
        "reason": "Analysis has not been saved.",
        "adjusted_p": None,
    }
    if not results:
        return unavailable
    prefix = "baseline" if baseline else "current"
    if group in {"performance", "probability"}:
        if results["mode"] != "B":
            return {**unavailable, "reason": "Unavailable — ground-truth labels were not provided."}
        metric = next(m for m in results["performance"]["metrics"] if m["metric_name"] == signal)
        return {
            "value": metric[prefix + "_value"],
            "n": metric[prefix + "_support"],
            "status": metric["status"],
            "reason": metric["reason"],
            "adjusted_p": None,
        }
    if group == "confidence":
        data = results["confidence"]
        return {
            "value": data[prefix + "_" + signal],
            "n": data[prefix + "_n"],
            "status": data["status"],
            "reason": data.get("reason"),
            "adjusted_p": None,
        }
    if group == "predictions":
        data = results["predictions"]
        category = next(c for c in data["categories"] if c["category"] == class_label)
        return {
            "value": category[prefix + "_share"],
            "n": data[prefix + "_n"],
            "status": data["status"],
            "reason": data.get("reason"),
            "adjusted_p": None,
        }
    feature = next(f for f in results["features"] if f["feature_id"] == feature_id)
    if baseline and signal != "missing_percent":
        return {**unavailable, "reason": "No baseline self-comparison is defined for KS/JS."}
    data = feature["missingness"] if signal == "missing_percent" else feature["distribution"]
    return {
        "value": data[prefix + "_missing_percent"]
        if signal == "missing_percent"
        else data.get("statistic")
        if signal == "ks"
        else data.get("distance"),
        "n": data[prefix + "_n"],
        "status": data["status"],
        "reason": data.get("reason"),
        "adjusted_p": data.get("adjusted_p"),
    }


def project_trends(
    session: Session,
    project_id: Any,
    group: str,
    signal: str,
    feature_id: str | None,
    class_label: str | None,
) -> dict[str, Any]:
    snapshot = session.scalar(
        select(BaselineSnapshot).where(
            BaselineSnapshot.project_id == project_id, BaselineSnapshot.status == "ESTABLISHED"
        )
    )
    if not snapshot or not snapshot.results:
        raise HTTPException(409, "Establish the baseline before exploring monitoring history.")
    dataset = session.get(Dataset, snapshot.dataset_id)
    assert dataset and dataset.profile
    included = {f["feature_id"]: f["type"] for f in snapshot.configuration["features"]}
    features = [
        {"feature_id": c["feature_id"], "name": c["name"], "type": included[c["feature_id"]]}
        for c in dataset.profile["columns"]
        if c["feature_id"] in included
    ]
    classes = snapshot.configuration["class_order"]
    options = signal_options(classes)
    if group not in options or signal not in options[group]:
        raise HTTPException(422, "Select a supported signal for this baseline.")
    if group == "data" and (
        feature_id not in included
        or signal == "ks"
        and included[feature_id] != "numeric"
        or signal == "js"
        and included[feature_id] != "categorical"
    ):
        raise HTTPException(422, "Select an included feature with the appropriate frozen type.")
    if group == "predictions" and class_label not in classes:
        raise HTTPException(422, "Select a class from the frozen class order.")
    runs = list(
        session.scalars(
            select(MonitoringRun)
            .where(MonitoringRun.project_id == project_id)
            .order_by(MonitoringRun.monitoring_date, MonitoringRun.created_at, MonitoringRun.id)
        )
    )
    points = [
        {
            "run_id": str(r.id),
            "name": r.name,
            "monitoring_date": r.monitoring_date.isoformat(),
            "created_at": r.created_at.isoformat(),
            "mode": r.mode,
            "methodology_version": r.methodology_version,
            **selected_value(
                r.results if r.state == "ANALYZED" else None, group, signal, feature_id, class_label
            ),
        }
        for r in runs
    ]
    reference = None
    if group in {"performance", "probability"}:
        metric = snapshot.results["metrics"]["metrics"][signal]
        reference = {
            "value": metric["value"],
            "n": snapshot.results["heldout_count"],
            "status": "UNAVAILABLE" if metric["reason"] else "AVAILABLE",
            "reason": metric["reason"],
            "label": "Baseline — held-out reference",
        }
    elif not (group == "data" and signal in {"ks", "js"}):
        first = next((r.results for r in runs if r.state == "ANALYZED" and r.results), None)
        if first:
            reference = {
                **selected_value(first, group, signal, feature_id, class_label, True),
                "label": "Baseline — all valid baseline rows"
                if group == "data"
                else "Baseline — held-out reference",
            }
    versions = sorted(
        {r.methodology_version for r in runs if r.state == "ANALYZED" and r.methodology_version}
    )
    return {
        "group": group,
        "signal": signal,
        "feature_id": feature_id,
        "class_label": class_label,
        "options": options,
        "features": features,
        "class_order": classes,
        "points": points,
        "reference": reference,
        "methodology_versions": versions,
        "warning": METHODOLOGY_CAUTION if len(versions) > 1 else None,
        "limitation": (
            "One stored signal at a time. Unavailable values remain gaps. No "
            "smoothing, interpolation, forecast or overall reliability trend "
            "is produced."
        ),
    }
