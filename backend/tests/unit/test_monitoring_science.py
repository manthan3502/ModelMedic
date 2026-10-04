import json
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest

from backend.app.science.baseline import fit_pipeline, make_pipeline
from backend.app.science.monitoring import (
    MODE_A_LIMITATION,
    analyze_mode_a,
    categorical_drift,
    confidence_drift,
    correct_family,
    missingness,
    numeric_drift,
    predict_frozen,
)


def test_numeric_identical_shift_insufficient_ties_and_range():
    b = list(range(100))
    same = numeric_drift(b, b)
    assert same["raw_p"] == 1 and same["distance"] == 0
    shifted = numeric_drift(b, list(range(200, 300)))
    assert shifted["status"] == "DETECTED" and shifted["outside_range_share"] == 1
    assert shifted["baseline_min"] == 0 and shifted["baseline_max"] == 99
    assert shifted["distance"] == 200
    assert shifted["plot"]["bins"][-1]["baseline_count"] == 0
    assert numeric_drift(b, b[:29])["status"] == "INSUFFICIENT DATA"
    assert numeric_drift([1, 2] * 50, [1, 2] * 50)["warnings"]
    assert sum(x["current_share"] for x in shifted["plot"]["bins"]) == 1


def test_categorical_identical_shift_new_disappeared_and_order():
    b = ["a"] * 50 + ["b"] * 50
    same = categorical_drift(b, b, ["b", "a"])
    assert same["raw_p"] == 1 and same["distance"] == 0
    assert [x["category"] for x in same["categories"]] == ["b", "a"]
    c = ["a"] * 10 + ["c"] * 90
    changed = categorical_drift(b, c)
    assert changed["status"] == "DETECTED"
    assert changed["new_categories"] == ["c"] and changed["disappeared_categories"] == ["b"]
    assert changed["distance"] > 0


def test_dynamic_pooling_unbalanced_expected_cells():
    b = ["large"] * 9900 + ["small"] * 100
    c = ["large"] * 49 + ["new"]
    d = categorical_drift(b, c)
    assert d["pooling_threshold"] == 1005
    assert d["status"] == "INSUFFICIENT DATA" and len(d["pooling"]) == 1
    assert set(d["pooling"][0]["members"]) == {"large", "small", "new"}
    assert d["categories"][1]["category"] == "new"


def test_pool_bucket_membership_collision_and_merge():
    b = ["__MM_OTHER__"] * 40 + ["b"] * 58 + ["rare"] * 2
    c = ["__MM_OTHER__"] * 40 + ["b"] * 55 + ["new"] * 5
    d = categorical_drift(b, c)
    assert d["raw_p"] is not None
    group = next(g for g in d["pooling"] if "rare" in g["members"])
    assert group["id"] != "pooled" and "__MM_OTHER__" in group["members"]
    assert {x["category"] for x in d["categories"]} == {"__MM_OTHER__", "b", "rare", "new"}
    retained_pool = categorical_drift(
        ["a"] * 40 + ["b"] * 40 + list("cdefg"), ["a"] * 40 + ["b"] * 40 + list("cdefg")
    )
    assert next(g for g in retained_pool["pooling"] if g["id"] == "pooled")["members"] == list(
        "cdefg"
    )
    assert np.min(retained_pool["expected_counts"]) >= 5
    assert categorical_drift(["a"] * 29, ["b"] * 100)["raw_p"] is None


@pytest.mark.parametrize(
    "mb,mc,test,detected",
    [(10, 10, "Chi-square", False), (1, 1, "Fisher exact", False), (0, 50, "Chi-square", True)],
)
def test_missingness_paths(mb, mc, test, detected):
    result = missingness(100, 100, mb, mc)
    assert result["test"] == test
    assert (result["status"] == "DETECTED") == detected
    assert result["delta_pp"] == mc - mb


def test_zero_missingness_and_all_missing():
    assert missingness(100, 50, 0, 0)["raw_p"] is None
    assert missingness(100, 50, 0, 0)["status"] == "NOT DETECTED"
    assert missingness(100, 50, 100, 50)["raw_p"] == 1


def test_bh_trusted_vector_combined_family_excludes_invalid():
    # Hand-calculated sorted BH: m*p/rank, followed by reverse cumulative minima.
    p = [0.01, 0.04, 0.03, 0.002]
    features = [
        {
            "distribution": {"raw_p": p[i], "status": "DETECTED"},
            "missingness": {"raw_p": p[i + 1], "status": "DETECTED"},
        }
        for i in (0, 2)
    ]
    features.append(
        {
            "distribution": {"raw_p": None, "status": "INSUFFICIENT DATA"},
            "missingness": missingness(100, 100, 0, 0),
        }
    )
    assert correct_family(features) == 4
    actual = [f[k]["adjusted_p"] for f in features[:2] for k in ("distribution", "missingness")]
    np.testing.assert_allclose(actual, [0.02, 0.04, 0.04, 0.008])
    assert all(
        f[k]["bh_family_size"] == 4 for f in features for k in ("distribution", "missingness")
    )


def test_confidence_shift_unchanged_support_fixed_axis():
    same = confidence_drift([0.8] * 60, [0.8] * 60)
    assert same["raw_p"] == 1 and same["baseline_n"] == same["current_n"] == 60
    shifted = confidence_drift([0.8] * 60, [0.5] * 50)
    assert shifted["status"] == "DETECTED" and shifted["current_mean"] == 0.5
    assert shifted["plot"]["bins"][0]["lower"] == 0
    assert shifted["plot"]["bins"][-1]["upper"] == 1


def test_reversed_model_class_order_and_max_probability():
    model = Mock(classes_=np.array(["b", "a"]))
    model.predict_proba.return_value = np.array([[0.7, 0.3], [0.4, 0.6]])
    model.predict.return_value = np.array(["b", "a"])
    pred, confidence = predict_frozen(model, pd.DataFrame({"x": [0, 1]}), ["a", "b"])
    assert pred.tolist() == ["b", "a"] and confidence.tolist() == [0.7, 0.6]


def test_raw_boundary_no_refit_persisted_reference_and_claim_safety():
    base = pd.DataFrame({"x": [None, "1", "2", "3"] * 30, "c": [None, "a", "b", "a"] * 30})
    current = pd.DataFrame(
        {"x": [None, "200", "201", "202"] * 15, "c": [None, "new", "new", "a"] * 15}
    )
    model = fit_pipeline(
        make_pipeline({"x": "numeric", "c": "categorical"}, "logistic_regression", "standard"),
        base,
        ["a", "b"] * 60,
        "logistic_regression",
        "standard",
    )
    imputer = model["preprocessor"].named_transformers_["numeric"]["imputer"]
    scaler = model["preprocessor"].named_transformers_["numeric"]["scaler"]
    encoder = model["preprocessor"].named_transformers_["categorical"]
    before = (
        imputer.statistics_.copy(),
        scaler.mean_.copy(),
        scaler.scale_.copy(),
        [x.copy() for x in encoder.categories_],
        model["classifier"].coef_.copy(),
    )
    reference = pd.DataFrame({"__mm_y_pred": ["b"] * 40, "__mm_confidence": [0.99] * 40})
    with patch.object(model, "fit", side_effect=AssertionError("Monitoring must not fit")):
        result = analyze_mode_a(
            base,
            current,
            reference,
            [
                {"feature_id": "f000", "name": "x", "type": "numeric"},
                {"feature_id": "f001", "name": "c", "type": "categorical"},
            ],
            model,
            ["a", "b"],
            [],
            lambda _: None,
        )
    for old, new in zip(
        before,
        (
            imputer.statistics_,
            scaler.mean_,
            scaler.scale_,
            encoder.categories_,
            model["classifier"].coef_,
        ),
        strict=True,
    ):
        np.testing.assert_array_equal(old, new)
    assert result["features"][0]["distribution"]["baseline_n"] == 90
    assert result["features"][0]["distribution"]["current_n"] == 45
    assert "m:" not in [x["category"] for x in result["features"][1]["distribution"]["categories"]]
    assert result["predictions"]["baseline_n"] == 40
    assert result["confidence"]["baseline_mean"] == 0.99
    assert result["limitation"] == MODE_A_LIMITATION
    serialized = json.dumps(result, allow_nan=False).lower()
    for forbidden in (
        "performance degraded",
        "accuracy fell",
        "model is failing",
        "model is unreliable",
        "calibration worsened",
        "retraining is required",
        "retrain now",
        '"metrics"',
        '"calibration"',
        '"confusion_matrix"',
        '"slices"',
    ):
        assert forbidden not in serialized
