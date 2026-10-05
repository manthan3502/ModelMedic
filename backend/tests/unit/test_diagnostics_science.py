import copy
import json
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest

from backend.app.science.baseline import calibration, evaluate
from backend.app.science.labeled import analyze_mode_b
from backend.app.science.monitoring import MODE_A_LIMITATION, analyze_mode_a
from backend.app.science.slices import INSUFFICIENT_SLICE, SLICE_LIMITATION, analyze_slices
from backend.app.services.reporting import (
    FEATURE_LIMITATION,
    REPORT_FOOTER,
    REPORT_LIMITATIONS,
    build_report,
    diagnostic,
)
from backend.app.services.trends import selected_value, signal_options


def results(mode="B"):
    classes = ["a", "b"]
    y = np.tile(classes, 60)
    probabilities = np.tile([[0.8, 0.2], [0.2, 0.8]], (60, 1))
    pipeline = Mock(classes_=np.array(classes))
    pipeline.predict_proba.return_value = probabilities
    pipeline.predict.return_value = y
    frame = pd.DataFrame(
        {"x": range(120), "c": [" x ", "x"] * 60, "target": y, "__mm_row_id": range(120)}
    )
    reference = pd.DataFrame({"__mm_y_pred": y, "__mm_confidence": [0.8] * 120})
    features = [
        {"feature_id": "f000", "name": "x", "type": "numeric"},
        {"feature_id": "f001", "name": "c", "type": "categorical"},
    ]
    if mode == "A":
        data = analyze_mode_a(
            frame, frame, reference, features, pipeline, classes, [], lambda _: None
        )
    else:
        baseline = {
            "metrics": evaluate(y, y, probabilities, classes, "a"),
            "calibration": calibration(y, probabilities, classes, "a"),
        }
        data = analyze_mode_b(
            frame,
            frame,
            reference,
            features,
            pipeline,
            classes,
            [],
            baseline,
            "target",
            "a",
            lambda _: None,
        )
    data.update(
        methodology_version="monitoring-v1",
        code_version="a" * 40,
        canonical_sha256="b" * 64,
        validation={
            "warnings": [],
            "required_features": ["x", "c"],
            "ignored_extra_columns": ["excluded_id"],
        },
    )
    return data


def report(data):
    return build_report(
        {"name": "Synthetic report", "description": None},
        {"held-out n": 120},
        {"id": "synthetic", "date": "2026-10-05"},
        data,
        "2026-10-05T12:00:00Z",
        "a" * 40,
    )


@pytest.mark.parametrize("count", [29, 30])
def test_slice_threshold_never_calculates_below_guardrail(count):
    y = np.array(["a", "b"] * 30)
    probability = np.eye(2)[[0, 1] * 30]
    baseline = evaluate(y, y, probability, ["a", "b"], "a")
    # All rows remains eligible. Spy confirms the small slice is not calculated anyway.
    from backend.app.science.slices import performance

    with patch("backend.app.science.slices.performance", wraps=performance) as calculate:
        rows = analyze_slices(
            ["slice"] * count + ["other"] * (60 - count),
            y,
            y,
            probability,
            ["a", "b"],
            "a",
            baseline,
        )
    row = next(r for r in rows if r["slice_value"] == "slice")
    assert row["row_count"] == count and sum(row["class_support"].values()) == count
    if count == 29:
        assert row["metrics"] == {} and row["reason"] == INSUFFICIENT_SLICE
        assert all(len(c.args[0]) >= 30 for c in calculate.call_args_list)
    else:
        assert row["metrics"]["balanced_accuracy"]["value"] == 1


def test_raw_categories_missing_and_absent_class_slice_reasons():
    y = np.array(["a"] * 60 + ["b"] * 60)
    probabilities = np.eye(2)[[0] * 60 + [1] * 60]
    baseline = evaluate(y, y, probabilities, ["a", "b"], "a")
    rows = analyze_slices(
        [None] * 30 + ["null"] * 30 + [" x "] * 30 + ["x"] * 30,
        y,
        y,
        probabilities,
        ["a", "b"],
        "a",
        baseline,
    )
    assert rows[0]["is_overall"] and rows[0]["row_count"] == 120
    assert [r["slice_value"] for r in rows[1:]] == [None, " x ", "null", "x"]
    assert sum(r["row_count"] for r in rows[1:]) == 120
    for r in rows[1:]:
        assert r["metrics"]["balanced_accuracy"]["value"] is None
        assert r["metrics"]["balanced_accuracy"]["reason"]
        assert r["metrics"]["brier"]["value"] == 0
    assert "This is not a fairness audit." in SLICE_LIMITATION
    assert "does not perform significance testing or multiplicity correction" in SLICE_LIMITATION


@pytest.mark.parametrize("classes,positive", [(["a", "b"], "a"), (["a", "b", "c"], None)])
def test_slice_current_metrics_do_not_inherit_unavailable_baseline_metric_reasons(
    classes, positive
):
    y = np.tile(classes, 30)
    probabilities = np.eye(len(classes))[[classes.index(c) for c in y]]
    baseline = evaluate(y, y, probabilities, classes, positive)
    baseline["metrics"]["balanced_accuracy"] = {
        "value": None,
        "reason": "Synthetic unavailable baseline reference",
    }
    rows = analyze_slices(["raw"] * len(y), y, y, probabilities, classes, positive, baseline)
    for row in rows:
        assert row["metrics"]["balanced_accuracy"] == {"value": 1.0, "reason": None, "note": None}
        assert row["class_support"] == dict.fromkeys(classes, 30)


def test_feature_diagnostic_separate_statuses_reference_and_negative_reliance():
    data = results()
    f = data["features"][0]
    f["distribution"]["status"] = "DETECTED"
    f["missingness"]["status"] = "NOT DETECTED"
    f["reliance"] = {"mean": -0.1, "sd": 0.01}
    before = copy.deepcopy(f)
    frame = diagnostic(f, data["data_reference"])
    assert "all valid baseline rows" in frame["measured"]
    assert "Distribution: DETECTED; missingness: NOT DETECTED" in frame["result"]
    assert frame["cannot_conclude"] == FEATURE_LIMITATION
    assert "Shuffling this feature did not reduce held-out Balanced Accuracy" in frame["reliance"]
    assert f == before


@pytest.mark.parametrize("mode", ["A", "B"])
def test_fixed_report_structure_evidence_limitations_versions_and_claim_safety(mode):
    data = results(mode)
    before = copy.deepcopy(data)
    with patch(
        "backend.app.science.labeled.performance",
        side_effect=AssertionError("Reports may not recompute science"),
    ):
        payload = report(data)
    assert data == before
    assert len(payload["sections"]) == 12
    assert [s["key"] for s in payload["sections"]] == [
        "project",
        "baseline",
        "run",
        "schema",
        "data",
        "predictions",
        "confidence",
        "performance",
        "calibration",
        "errors",
        "slices",
        "limitations",
    ]
    assert payload["report_template_version"] == "report-v1"
    assert payload["methodology_version"] == "monitoring-v1"
    assert payload["generated_at"] == "2026-10-05T12:00:00Z"
    assert (
        payload["footer"]
        == REPORT_FOOTER
        == (
            "Generated from stored results using fixed reviewed templates. "
            "No language model generated this report."
        )
    )
    assert all(x in payload["sections"][-1]["paragraphs"] for x in REPORT_LIMITATIONS)
    for section in payload["sections"]:
        for f in section["findings"]:
            assert set(f) == {"measured", "result", "evidence", "may_conclude", "cannot_conclude"}
    if mode == "A":
        for s in payload["sections"][7:10]:
            assert MODE_A_LIMITATION in s["paragraphs"] and s["tables"] == []
        assert MODE_A_LIMITATION in payload["sections"][10]["paragraphs"]
    else:
        assert all(payload["sections"][i]["tables"] for i in (7, 8, 9))
    serialized = json.dumps(payload, allow_nan=False).lower()
    for forbidden in (
        "retrain now",
        "retraining is required",
        "health score",
        "performance degraded",
        "drift caused",
        "model is unreliable",
        "synthetic-secret",
    ):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    "group,signal",
    [("performance", "balanced_accuracy"), ("probability", "brier"), ("probability", "log_loss")],
)
def test_mode_a_trend_keeps_unavailable_outcome_gap(group, signal):
    selected = selected_value(results("A"), group, signal, None, None)
    assert selected["value"] is None and selected["n"] is None and selected["reason"]


@pytest.mark.parametrize(
    "signal,feature", [("ks", "f000"), ("js", "f001"), ("missing_percent", "f001")]
)
def test_feature_trend_one_persisted_signal_with_correct_reference_and_adjusted_p(signal, feature):
    data = results()
    f = next(f for f in data["features"] if f["feature_id"] == feature)
    point = selected_value(data, "data", signal, feature, None)
    evidence = f["missingness"] if signal == "missing_percent" else f["distribution"]
    expected = (
        evidence["current_missing_percent"]
        if signal == "missing_percent"
        else evidence["statistic"]
        if signal == "ks"
        else evidence["distance"]
    )
    assert point["value"] == expected and point["adjusted_p"] == evidence["adjusted_p"]
    baseline = selected_value(data, "data", signal, feature, None, True)
    assert baseline["value"] == (
        evidence["baseline_missing_percent"] if signal == "missing_percent" else None
    )


def test_prediction_trend_frozen_class_selector_and_signal_options():
    data = results()
    for c in data["predictions"]["categories"]:
        assert (
            selected_value(data, "predictions", "class_share", None, c["category"])["value"]
            == c["current_share"]
        )
    assert "average_precision" in signal_options(["a", "b"])["performance"]
    assert "average_precision" not in signal_options(["a", "b", "c"])["performance"]
    assert "macro_f1" in signal_options(["a", "b", "c"])["performance"]
    assert selected_value(None, "confidence", "median", None, None)["value"] is None
