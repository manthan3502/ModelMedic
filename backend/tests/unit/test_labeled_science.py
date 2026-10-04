import copy
import json
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import log_loss, precision_recall_fscore_support, roc_auc_score

from backend.app.science.baseline import calibration, evaluate, fit_pipeline, make_pipeline
from backend.app.science.labeled import (
    CLASS_COMPOSITION_CAUTION,
    MODE_B_STATEMENT,
    PERFORMANCE_LIMITATION,
    analyze_mode_b,
    errors,
    performance,
)


def rows(result):
    return {m["metric_name"]: m for m in result["metrics"]}


def test_binary_known_answers_explicit_first_positive_class():
    classes = ["yes", "no"]
    y = np.array(["yes", "yes", "no", "no"])
    predicted = np.array(["yes", "no", "yes", "no"])
    prob = np.array([[0.9, 0.1], [0.4, 0.6], [0.6, 0.4], [0.1, 0.9]])
    baseline = evaluate(y, y, np.eye(2)[[0, 0, 1, 1]], classes, "yes")
    result = performance(y, predicted, prob, classes, "yes", baseline)
    r = rows(result)
    for name in ("accuracy", "balanced_accuracy", "precision", "recall", "f1"):
        assert r[name]["current_value"] == 0.5 and r[name]["delta"] == -0.5
        assert r[name]["baseline_support"] == r[name]["current_support"] == 4
    assert r["roc_auc"]["current_value"] == 0.75
    assert r["average_precision"]["current_value"] == pytest.approx(5 / 6)
    assert r["brier"]["current_value"] == pytest.approx(0.185)
    assert r["log_loss"]["current_value"] == pytest.approx(-np.log([0.9, 0.4, 0.4, 0.9]).mean())
    assert result["current_evaluation"]["confusion_matrix"] == [[1, 1], [1, 1]]


def test_multiclass_known_answers_full_frozen_space_and_per_class():
    classes = ["Gold", "Bronze", "Silver"]
    y = np.array(["Gold", "Gold", "Bronze", "Bronze", "Silver", "Silver"])
    prob = np.array(
        [
            [0.8, 0.1, 0.1],
            [0.2, 0.7, 0.1],
            [0.1, 0.8, 0.1],
            [0.2, 0.3, 0.5],
            [0.1, 0.1, 0.8],
            [0.6, 0.1, 0.3],
        ]
    )
    predicted = np.array(classes)[prob.argmax(axis=1)]
    baseline = evaluate(y, y, np.eye(3)[[0, 0, 1, 1, 2, 2]], classes, None)
    result = performance(y, predicted, prob, classes, None, baseline)
    r = rows(result)
    assert r["accuracy"]["current_value"] == 0.5
    expected = precision_recall_fscore_support(y, predicted, labels=classes, zero_division=np.nan)
    for c, precision, recall, f1, support in zip(result["per_class"], *expected, strict=True):
        assert c["current_support"] == support
        for key, value in (("precision", precision), ("recall", recall), ("f1", f1)):
            assert rows(c)[key]["current_value"] == value
    assert r["macro_f1"]["current_value"] == np.mean(expected[2])
    assert r["weighted_f1"]["current_value"] == np.average(expected[2], weights=expected[3])
    auc = np.mean([roc_auc_score(y == c, prob[:, i]) for i, c in enumerate(classes)])
    assert r["macro_ovr_roc_auc"]["current_value"] == auc
    onehot = np.eye(3)[[0, 0, 1, 1, 2, 2]]
    assert r["brier"]["current_value"] == pytest.approx(np.square(prob - onehot).sum(axis=1).mean())
    # sklearn's labels are sorted; remap columns before comparing its reference.
    assert r["log_loss"]["current_value"] == pytest.approx(
        log_loss(y, prob[:, [1, 0, 2]], labels=sorted(classes))
    )
    assert [c["class"] for c in result["per_class"]] == classes


@pytest.mark.parametrize("classes,positive", [(["a", "b"], "a"), (["a", "b", "c"], None)])
def test_absent_class_not_misleadingly_compared_and_probability_caution(classes, positive):
    by = np.tile(classes, 30)
    bp = np.eye(len(classes))[[classes.index(c) for c in by]]
    baseline = evaluate(by, by, bp, classes, positive)
    y = np.array([classes[-1]] * 60)
    pred = np.array([classes[-1]] * 30 + [classes[0]] * 30)
    prob = np.full((60, len(classes)), 1 / len(classes))
    result = performance(y, pred, prob, classes, positive, baseline)
    r = rows(result)
    assert result["absent_classes"] == classes[:-1]
    assert r["accuracy"]["current_value"] == 0.5
    assert r["balanced_accuracy"]["current_value"] is None
    assert r["balanced_accuracy"]["delta"] is None
    assert r["balanced_accuracy"]["reason"]
    for key in ("log_loss", "brier"):
        assert r[key]["current_value"] is not None and r[key]["note"] == CLASS_COMPOSITION_CAUTION
    ranking = "roc_auc" if positive else "macro_ovr_roc_auc"
    assert r[ranking]["current_value"] is None and r[ranking]["reason"]
    if len(classes) > 2:
        for key in ("macro_precision", "macro_recall", "macro_f1"):
            assert r[key]["status"] == "UNAVAILABLE" and r[key]["delta"] is None
        assert r["weighted_f1"]["current_value"] is not None
    for c in result["per_class"][:-1]:
        assert c["current_support"] == 0 and rows(c)["recall"]["current_value"] is None
    json.dumps(result, allow_nan=False)


def test_undefined_predictions_precision_and_f1_have_reasons_not_fake_zero():
    classes = ["a", "b", "c"]
    y = np.array(["a"] * 50)
    prob = np.tile([1.0, 0.0, 0.0], (50, 1))
    baseline = evaluate(classes, classes, np.eye(3), classes, None)
    r = performance(y, y, prob, classes, None, baseline)
    for c in r["per_class"][1:]:
        assert all(m["current_value"] is None and m["reason"] for m in c["metrics"])


@pytest.mark.parametrize(
    "n,bins", [(40, 3), (99, 3), (100, 5), (249, 5), (250, 8), (499, 8), (500, 10)]
)
def test_all_calibration_thresholds_counts_and_warning(n, bins):
    y = np.array(["yes" if i % 2 else "no" for i in range(n)])
    p = np.linspace(0.01, 0.99, n)
    result = calibration(y, np.column_stack([p, 1 - p]), ["yes", "no"], "yes")
    assert result["requested_bins"] == bins
    assert len(result["classes"][0]["bins"]) == bins
    assert sum(b["count"] for b in result["classes"][0]["bins"]) == n
    assert bool(result["warning"]) == (n < 250)


@pytest.mark.parametrize(
    "positive,negative,valid", [(19, 31, False), (31, 19, False), (20, 30, True), (30, 20, True)]
)
def test_calibration_event_support_boundary(positive, negative, valid):
    y = np.array(["a"] * positive + ["b"] * negative)
    p = np.tile([0.3, 0.7], (len(y), 1))
    curve = calibration(y, p, ["a", "b"], "a")["classes"][0]
    assert bool(curve["bins"]) is valid
    assert bool(curve["reason"]) is not valid
    if valid:
        assert sum(b["count"] for b in curve["bins"]) == len(y)  # ties collapse quantile boundaries


def test_multiclass_calibration_absent_class_unavailable_in_frozen_order():
    y = np.array(["a"] * 30 + ["b"] * 30)
    p = np.tile([0.4, 0.3, 0.3], (len(y), 1))
    c = calibration(y, p, ["c", "b", "a"], None)
    assert [v["class"] for v in c["classes"]] == ["c", "b", "a"]
    assert c["classes"][0]["positive_count"] == 0
    assert c["classes"][0]["reason"] and not c["classes"][0]["bins"]
    assert all(sum(b["count"] for b in v["bins"]) == 60 for v in c["classes"][1:])


def test_error_aggregates_rates_pairs_row_references_and_limit():
    y = np.array(["a"] * 70 + ["b"] * 70)
    pred = np.array(["b"] * 70 + ["a"] * 70)
    e = errors(
        y, pred, np.arange(1000, 1140), ["a", "b"], "a", [[20, 0], [0, 20]], [[0, 70], [70, 0]]
    )
    assert e["current"]["binary"] == {"tp": 0, "tn": 0, "fp": 70, "fn": 70}
    assert e["current"]["normalized"] == [[0, 1], [1, 0]]
    assert e["row_references"]["fp"] == list(range(1070, 1120))
    assert e["row_references"]["fn"] == list(range(1000, 1050))
    assert all(len(v) <= 50 for v in e["row_references"].values())
    multi = errors(
        ["a", "b", "b"],
        ["b", "c", "b"],
        [9, 11, 15],
        ["a", "b", "c"],
        None,
        [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        [[0, 1, 0], [0, 1, 1], [0, 0, 0]],
    )
    assert multi["current"]["normalized"][2] == [None] * 3
    assert multi["current"]["common_pairs"][0]["actual"] == "a"
    assert multi["current"]["common_pairs"][1]["rate"] == 0.5


def test_mode_b_single_frozen_inference_historical_values_stages_and_no_refit():
    class ReversedModel:
        classes_ = np.array(["no", "yes"])
        calls = 0

        def predict_proba(self, X):
            self.calls += 1
            return np.tile([0.2, 0.8], (len(X), 1))

        def predict(self, X):
            return np.array(["yes"] * len(X))

        def fit(self, *args):
            raise AssertionError("Monitoring cannot fit")

    classes = ["yes", "no"]
    y = np.array(["yes", "no"] * 30)
    reference = pd.DataFrame({"__mm_y_pred": y, "__mm_confidence": [0.123] * 60})
    current = pd.DataFrame(
        {"x": np.arange(60), "label": y, "__mm_row_id": np.arange(60), "excluded": ["private"] * 60}
    )
    stored = {
        "metrics": evaluate(y, y, np.eye(2)[[0, 1] * 30], classes, "yes"),
        "calibration": calibration(y, np.tile([0.6, 0.4], (60, 1)), classes, "yes"),
    }
    before = copy.deepcopy(stored)
    stages = []
    model = ReversedModel()
    result = analyze_mode_b(
        current,
        current,
        reference,
        [{"name": "x", "type": "numeric", "feature_id": "f000"}],
        model,
        classes,
        [],
        stored,
        "label",
        "yes",
        stages.append,
    )
    assert model.calls == 1
    assert result["mode"] == "B" and result["limitation"] == MODE_B_STATEMENT
    assert rows(result["performance"])["brier"]["current_value"] == pytest.approx(0.34)
    assert result["confidence"]["baseline_mean"] == pytest.approx(0.123)
    assert result["calibration"]["baseline"] == before["calibration"]
    assert stored == before
    assert stages == [
        "PREDICTING",
        "DATA_DRIFT",
        "MISSINGNESS",
        "PREDICTION_DRIFT",
        "CONFIDENCE",
        "PERFORMANCE",
        "CALIBRATION",
    ]
    assert PERFORMANCE_LIMITATION in result["limitations"]
    encoded = json.dumps(result, allow_nan=False)
    assert "private" not in encoded
    for forbidden in (
        "retrain now",
        "model is failing",
        "calibration worsened",
        "health_score",
        "severity",
    ):
        assert forbidden not in encoded.lower()


def test_mode_b_cannot_change_fitted_imputer_scaler_encoder_or_model():
    from backend.app.jobs.artifacts import dump

    baseline = pd.DataFrame(
        {
            "x": [None if i % 10 == 0 else str(i) for i in range(100)],
            "c": ["a" if i % 2 else "b" for i in range(100)],
        }
    )
    y = pd.Series(["yes" if i % 2 else "no" for i in range(100)])
    model = fit_pipeline(
        make_pipeline({"x": "numeric", "c": "categorical"}, "logistic_regression", "standard"),
        baseline,
        y,
        "logistic_regression",
        "standard",
    )
    before = dump(model)
    classes = model.classes_.tolist()
    prob = model.predict_proba(baseline)
    stored = {
        "metrics": evaluate(y, model.predict(baseline), prob, classes, "yes"),
        "calibration": calibration(y, prob, classes, "yes"),
    }
    reference = pd.DataFrame(
        {"__mm_y_pred": model.predict(baseline), "__mm_confidence": prob.max(axis=1)}
    )
    current = pd.DataFrame(
        {
            "x": ["10000"] * 60,
            "c": ["new"] * 60,
            "target": ["yes", "no"] * 30,
            "__mm_row_id": np.arange(60),
        }
    )
    with patch.object(model, "fit", side_effect=AssertionError("Mode B cannot fit")):
        result = analyze_mode_b(
            baseline,
            current,
            reference,
            [
                {"name": "x", "type": "numeric", "feature_id": "f000"},
                {"name": "c", "type": "categorical", "feature_id": "f001"},
            ],
            model,
            classes,
            [],
            stored,
            "target",
            "yes",
            lambda _: None,
        )
    assert dump(model) == before
    assert result["features"][0]["distribution"]["baseline_n"] == 90
    assert result["features"][0]["distribution"]["current_n"] == 60
