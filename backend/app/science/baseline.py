"""M2 deterministic scientific contract. No monitoring or model selection."""

import json
from collections.abc import Callable
from hashlib import sha256
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

SEED = 42
METHODOLOGY_VERSION = "baseline-v1"
ARTIFACT_VERSION = "pipeline-v1"


class TrainingError(ValueError):
    """Only reviewed, non-sensitive messages may cross the worker boundary."""


def fingerprint(dataset_hash: str, config: dict[str, Any]) -> str:
    values = {
        k: config[k] for k in ("target_id", "positive_class", "features", "classifier", "weighting")
    }
    return sha256(
        json.dumps(
            {"dataset_sha256": dataset_hash, **values}, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


class RawFeatures(TransformerMixin, BaseEstimator):  # type: ignore[misc]
    """Frozen semantic conversion lives inside the persisted, permuted pipeline."""

    def __init__(self, feature_types: dict[str, str]):
        self.feature_types = feature_types

    def fit(self, X: Any, y: Any = None) -> Any:
        self.feature_names_in_ = np.asarray(list(self.feature_types), dtype=object)
        self.n_features_in_ = len(self.feature_types)
        for name, kind in self.feature_types.items():
            if kind == "numeric" and X[name].isna().all():
                raise TrainingError(
                    "A numeric feature has no observed values in a development fold. "
                    "Exclude it or revise the baseline dataset."
                )
        return self

    def transform(self, X: Any) -> Any:
        output = pd.DataFrame(index=X.index)
        for name, kind in self.feature_types.items():
            if kind == "numeric":
                output[name] = pd.to_numeric(X[name], errors="raise").astype(float)
            else:
                # Prefixing observed values prevents collisions with the explicit missing category.
                output[name] = X[name].map(lambda x: "m:" if pd.isna(x) else "v:" + str(x))
        return output


def make_pipeline(types: dict[str, str], classifier: str, weighting: str) -> Any:
    numeric = [n for n, t in types.items() if t == "numeric"]
    categorical = [n for n, t in types.items() if t == "categorical"]
    numeric_steps: list[tuple[str, Any]] = [("imputer", SimpleImputer(strategy="median"))]
    if classifier == "logistic_regression":
        numeric_steps.append(("scaler", StandardScaler()))
    transforms: list[tuple[str, Any, list[str]]] = []
    if numeric:
        transforms.append(("numeric", Pipeline(numeric_steps), numeric))
    if categorical:
        transforms.append(
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False, dtype=np.float64),
                categorical,
            )
        )
    weight = "balanced" if weighting == "balanced" else None
    if classifier == "logistic_regression":
        model = LogisticRegression(
            C=1.0,
            penalty="l2",
            solver="lbfgs",
            max_iter=1000,
            tol=1e-4,
            class_weight=weight,
            random_state=SEED,
        )
    elif classifier == "random_forest":
        model = RandomForestClassifier(
            n_estimators=100,
            criterion="gini",
            max_depth=None,
            min_samples_split=2,
            min_samples_leaf=1,
            max_features="sqrt",
            bootstrap=True,
            class_weight=weight,
            random_state=SEED,
            n_jobs=1,
        )
    elif classifier == "gradient_boosting":
        model = GradientBoostingClassifier(
            loss="log_loss",
            learning_rate=0.1,
            n_estimators=100,
            subsample=1.0,
            criterion="friedman_mse",
            min_samples_split=2,
            min_samples_leaf=1,
            max_depth=3,
            max_features=None,
            random_state=SEED,
        )
    else:
        raise TrainingError("Choose a supported classifier before training.")
    return Pipeline(
        [
            ("semantics", RawFeatures(types)),
            ("preprocessor", ColumnTransformer(transforms, remainder="drop", sparse_threshold=0)),
            ("classifier", model),
        ]
    )


def fit_pipeline(pipeline: Any, X: Any, y: Any, classifier: str, weighting: str) -> Any:
    options = (
        {"classifier__sample_weight": compute_sample_weight("balanced", y)}
        if classifier == "gradient_boosting" and weighting == "balanced"
        else {}
    )
    pipeline.fit(X, y, **options)
    return pipeline


def metric(value: float | None, reason: str | None = None) -> dict[str, Any]:
    return {"value": value, "reason": reason}


def evaluate(
    y: Any, predicted: Any, probabilities: Any, classes: list[str], positive: str | None
) -> dict[str, Any]:
    y, predicted, probabilities = np.asarray(y), np.asarray(predicted), np.asarray(probabilities)
    if (
        len(y) == 0
        or probabilities.shape != (len(y), len(classes))
        or not set(y).issubset(classes)
        or not set(predicted).issubset(classes)
    ):
        raise TrainingError("Evaluation data does not match the frozen class space.")
    matrix = confusion_matrix(y, predicted, labels=classes)
    actual, estimated = matrix.sum(axis=1), matrix.sum(axis=0)
    per_class: list[dict[str, Any]] = []
    for i, name in enumerate(classes):
        tp = int(matrix[i, i])
        per_class.append(
            {
                "class": name,
                "support": int(actual[i]),
                "precision": metric(float(tp / estimated[i]))
                if estimated[i]
                else metric(None, "No predictions for this class."),
                "recall": metric(float(tp / actual[i]))
                if actual[i]
                else metric(None, "No observations for this class."),
                "f1": metric(float(2 * tp / (actual[i] + estimated[i])))
                if actual[i] + estimated[i]
                else metric(None, "No observations or predictions for this class."),
            }
        )
    scores = {
        "accuracy": metric(float(accuracy_score(y, predicted))),
        "balanced_accuracy": metric(float(balanced_accuracy_score(y, predicted)))
        if all(actual)
        else metric(None, "Not all frozen classes have observed support."),
    }
    index = {label: i for i, label in enumerate(classes)}
    truth = np.array([index[v] for v in y])
    onehot = np.eye(len(classes))[truth]
    eps = np.finfo(probabilities.dtype).eps
    clipped = np.clip(probabilities, eps, 1 - eps)
    scores["log_loss"] = metric(float(-np.log(clipped[np.arange(len(y)), truth]).mean()))
    if len(classes) == 2:
        if positive not in classes:
            raise TrainingError("Select the binary positive class before training.")
        i = classes.index(positive)
        for key in ("precision", "recall", "f1"):
            scores[key] = per_class[i][key]
        binary = y == positive
        valid = bool(binary.any() and (~binary).any())
        for key, fn in (("roc_auc", roc_auc_score), ("average_precision", average_precision_score)):
            scores[key] = (
                metric(float(fn(binary, probabilities[:, i])))
                if valid
                else metric(None, "Positive and non-positive observations are required.")
            )
        scores["brier"] = metric(float(np.mean((probabilities[:, i] - binary) ** 2)))
    else:
        for key in ("precision", "recall", "f1"):
            values = [p[key]["value"] for p in per_class]
            scores["macro_" + key] = (
                metric(float(np.mean(values)))
                if all(v is not None for v in values)
                else metric(None, "A frozen-class component is undefined.")
            )
        f1 = [p["f1"]["value"] for p in per_class]
        scores["weighted_f1"] = (
            metric(float(np.average(f1, weights=actual)))
            if all(v is not None for v in f1)
            else metric(None, "A frozen-class F1 is undefined.")
        )
        scores["macro_ovr_roc_auc"] = (
            metric(
                float(
                    np.mean(
                        [roc_auc_score(y == c, probabilities[:, i]) for i, c in enumerate(classes)]
                    )
                )
            )
            if all(actual)
            else metric(None, "All frozen classes require positive and non-positive observations.")
        )
        scores["brier"] = metric(float(np.mean(np.sum((probabilities - onehot) ** 2, axis=1))))
    return {
        "support": len(y),
        "class_order": classes,
        "metrics": scores,
        "per_class": per_class,
        "confusion_matrix": matrix.tolist(),
    }


def calibration(
    y: Any, probabilities: Any, classes: list[str], positive: str | None
) -> dict[str, Any]:
    y = np.asarray(y)
    n = len(y)
    bins = 3 if n < 100 else 5 if n < 250 else 8 if n < 500 else 10
    output: dict[str, Any] = {
        "support": n,
        "requested_bins": bins,
        "warning": "Limited-support calibration estimate — empirical rates may be unstable."
        if n < 250
        else None,
        "classes": [],
    }
    for name in [positive] if len(classes) == 2 else classes:
        assert name is not None
        i = classes.index(name)
        truth = y == name
        result: dict[str, Any] = {
            "class": name,
            "positive_count": int(truth.sum()),
            "non_positive_count": int((~truth).sum()),
            "bins": [],
            "reason": None,
        }
        if truth.sum() < 20 or (~truth).sum() < 20:
            result["reason"] = "Unavailable — insufficient positive/non-positive observations."
        else:
            prob = probabilities[:, i]
            edges = np.unique(np.quantile(prob, np.linspace(0, 1, bins + 1)))
            assignment = np.searchsorted(edges[1:-1], prob, side="left")
            for b in np.unique(assignment):
                mask = assignment == b
                result["bins"].append(
                    {
                        "mean_probability": float(prob[mask].mean()),
                        "observed_rate": float(truth[mask].mean()),
                        "count": int(mask.sum()),
                    }
                )
        output["classes"].append(result)
    return output


def split_indices(y: Any) -> tuple[Any, Any]:
    classes, counts = np.unique(y, return_counts=True)
    if not 2 <= len(classes) <= 10 or len(y) < max(200, 100 * len(classes)) or counts.min() < 100:
        raise TrainingError(
            "Baseline requires at least 100 observations per class and max(200, 100 ×"
            " classes) rows."
        )
    development, heldout = train_test_split(
        np.arange(len(y)), test_size=0.2, stratify=y, random_state=SEED
    )
    guard_heldout(np.asarray(y)[heldout], classes)
    return development, heldout


def guard_heldout(y: Any, classes: Any) -> None:
    if any(int(np.sum(np.asarray(y) == c)) < 20 for c in classes):
        raise TrainingError(
            "Actual held-out support is below 20 for a class. Add labeled baseline "
            "observations and train again."
        )


def train(
    X: Any,
    y: Any,
    row_ids: Any,
    config: dict[str, Any],
    types: dict[str, str],
    stage: Callable[[str], None],
) -> tuple[Any, dict[str, Any], Any, Any]:
    stage("SPLITTING")
    development, heldout = split_indices(y)
    Xdev, ydev = X.iloc[development], y.iloc[development]
    Xref, yref = X.iloc[heldout], y.iloc[heldout]
    stage("CROSS_VALIDATING")
    folds, fold_membership = [], []
    for fit, validation in StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED).split(
        Xdev, ydev
    ):
        model = fit_pipeline(
            make_pipeline(types, config["classifier"], config["weighting"]),
            Xdev.iloc[fit],
            ydev.iloc[fit],
            config["classifier"],
            config["weighting"],
        )
        folds.append(
            evaluate(
                ydev.iloc[validation],
                model.predict(Xdev.iloc[validation]),
                model.predict_proba(Xdev.iloc[validation]),
                model.classes_.tolist(),
                config["positive_class"],
            )
        )
        fold_membership.append(
            {
                "fit": row_ids[development[fit]].tolist(),
                "validation": row_ids[development[validation]].tolist(),
            }
        )
    cv: dict[str, Any] = {}
    for key in folds[0]["metrics"]:
        values = [f["metrics"][key]["value"] for f in folds]
        cv[key] = (
            {
                "values": values,
                "mean": float(np.mean(values)),
                "sd": float(np.std(values, ddof=1)),
                "min": min(values),
                "max": max(values),
                "reason": None,
            }
            if all(v is not None for v in values)
            else {
                "values": values,
                "reason": "One or more development-fold metrics are unavailable.",
            }
        )
    stage("TRAINING")
    pipeline = fit_pipeline(
        make_pipeline(types, config["classifier"], config["weighting"]),
        Xdev,
        ydev,
        config["classifier"],
        config["weighting"],
    )
    stage("EVALUATING")
    classes = pipeline.classes_.tolist()
    predictions, probabilities = pipeline.predict(Xref), pipeline.predict_proba(Xref)
    metrics = evaluate(yref, predictions, probabilities, classes, config["positive_class"])
    stage("CALIBRATION")
    reliability = calibration(yref, probabilities, classes, config["positive_class"])
    stage("IMPORTANCE")
    importance = permutation_importance(
        pipeline, Xref, yref, scoring="balanced_accuracy", n_repeats=10, random_state=SEED, n_jobs=1
    )
    reference = Xref.copy()
    reference.insert(0, "__mm_row_id", row_ids[heldout])
    reference["__mm_y_true"], reference["__mm_y_pred"] = np.asarray(yref), predictions
    for i in range(len(classes)):
        reference[f"__mm_probability_{i}"] = probabilities[:, i]
    reference["__mm_confidence"] = probabilities.max(axis=1)
    development_set = set(development)
    membership = pd.DataFrame(
        {
            "__mm_row_id": row_ids,
            "partition": [
                "development" if i in development_set else "heldout" for i in range(len(y))
            ],
        }
    )

    def counts(data: Any) -> dict[str, int]:
        return {c: int(np.sum(np.asarray(data) == c)) for c in classes}

    results = {
        "metrics": metrics,
        "cv": cv,
        "cv_folds": fold_membership,
        "calibration": reliability,
        "importance": [
            {"feature": n, "mean": float(m), "sd": float(s)}
            for n, m, s in zip(
                X.columns, importance.importances_mean, importance.importances_std, strict=True
            )
        ],
        "class_order": classes,
        "class_counts": counts(y),
        "development_class_counts": counts(ydev),
        "heldout_class_counts": counts(yref),
        "development_count": len(development),
        "heldout_count": len(heldout),
        "warnings": [
            "Low held-out class support (20–29): interpret class metrics, "
            "calibration and model reliance cautiously."
        ]
        if any(v < 30 for v in counts(yref).values())
        else [],
    }
    return pipeline, results, reference, membership
