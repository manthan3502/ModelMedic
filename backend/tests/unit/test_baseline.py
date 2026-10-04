from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from sklearn import metrics

from backend.app.science.baseline import (
    TrainingError,
    calibration,
    evaluate,
    fit_pipeline,
    guard_heldout,
    make_pipeline,
    split_indices,
    train,
)


def data(classes=2):
    rng = np.random.default_rng(42)
    n = classes * 150
    X = pd.DataFrame(
        {"amount": rng.normal(size=n), "category": ["a" if i % 3 else None for i in range(n)]}
    )
    X.loc[::7, "amount"] = np.nan
    y = pd.Series([f"c{i % classes}" for i in range(n)])
    return X, y


def test_split_deterministic_stratified_and_actual_guard():
    _, y = data(3)
    dev, heldout = split_indices(y)
    dev2, heldout2 = split_indices(y)
    np.testing.assert_array_equal(dev, dev2)
    np.testing.assert_array_equal(heldout, heldout2)
    assert not set(dev) & set(heldout)
    assert len(dev) == 360 and len(heldout) == 90
    assert all((y.iloc[heldout] == c).sum() == 30 for c in y.unique())
    with pytest.raises(TrainingError, match="Actual held-out"):
        guard_heldout(["a"] * 19 + ["b"] * 21, ["a", "b"])
    with pytest.raises(TrainingError, match="100 observations"):
        split_indices(["a"] * 99 + ["b"] * 101)


@pytest.mark.parametrize(
    "classifier", ["logistic_regression", "random_forest", "gradient_boosting"]
)
@pytest.mark.parametrize("weighting", ["standard", "balanced"])
def test_all_models_weighting_and_no_heldout_or_future_leakage(classifier, weighting):
    X, y = data()
    dev, heldout = split_indices(y)
    types = {"amount": "numeric", "category": "categorical"}
    first = fit_pipeline(
        make_pipeline(types, classifier, weighting), X.iloc[dev], y.iloc[dev], classifier, weighting
    )
    mutated = X.copy()
    mutated.loc[heldout, "amount"] = 1e9
    mutated.loc[heldout, "category"] = "only-heldout"
    second = fit_pipeline(
        make_pipeline(types, classifier, weighting),
        mutated.iloc[dev],
        y.iloc[dev],
        classifier,
        weighting,
    )
    for pipe in (first, second):
        numeric = pipe["preprocessor"].named_transformers_["numeric"]
        np.testing.assert_allclose(numeric["imputer"].statistics_, [X.iloc[dev].amount.median()])
        assert ("scaler" in numeric.named_steps) == (classifier == "logistic_regression")
        assert (
            "v:only-heldout"
            not in pipe["preprocessor"].named_transformers_["categorical"].categories_[0]
        )
    np.testing.assert_array_equal(
        first.predict_proba(X.iloc[dev]), second.predict_proba(X.iloc[dev])
    )
    before = first["preprocessor"].named_transformers_["numeric"]["imputer"].statistics_.copy()
    first.predict_proba(mutated.iloc[heldout])
    np.testing.assert_array_equal(
        before, first["preprocessor"].named_transformers_["numeric"]["imputer"].statistics_
    )
    if classifier == "logistic_regression":
        np.testing.assert_array_equal(first["classifier"].coef_, second["classifier"].coef_)
        np.testing.assert_array_equal(
            first["preprocessor"].named_transformers_["numeric"]["scaler"].mean_,
            second["preprocessor"].named_transformers_["numeric"]["scaler"].mean_,
        )
    assert first.classes_.tolist() == ["c0", "c1"]


def test_metrics_known_binary_positive_index_zero_and_undefined():
    y = np.array(["a", "b", "a", "b"])
    probabilities = np.array([[0.8, 0.2], [0.3, 0.7], [0.4, 0.6], [0.1, 0.9]])
    predicted = np.array(["a", "b", "b", "b"])
    m = evaluate(y, predicted, probabilities, ["a", "b"], "a")["metrics"]
    assert m["precision"]["value"] == metrics.precision_score(y, predicted, pos_label="a")
    assert m["recall"]["value"] == metrics.recall_score(y, predicted, pos_label="a")
    assert m["f1"]["value"] == metrics.f1_score(y, predicted, pos_label="a")
    assert m["accuracy"]["value"] == metrics.accuracy_score(y, predicted)
    assert m["balanced_accuracy"]["value"] == metrics.balanced_accuracy_score(y, predicted)
    assert m["roc_auc"]["value"] == metrics.roc_auc_score(y == "a", probabilities[:, 0])
    assert m["average_precision"]["value"] == metrics.average_precision_score(
        y == "a", probabilities[:, 0]
    )
    assert m["brier"]["value"] == metrics.brier_score_loss(y == "a", probabilities[:, 0])
    assert m["log_loss"]["value"] == pytest.approx(
        metrics.log_loss(y, probabilities, labels=["a", "b"])
    )
    reordered = evaluate(y, predicted, probabilities[:, ::-1], ["b", "a"], "a")
    assert reordered["metrics"] == m
    undefined = evaluate(y, np.array(["b"] * 4), probabilities, ["a", "b"], "a")["metrics"]
    assert undefined["precision"]["value"] is None and undefined["precision"]["reason"]
    assert undefined["recall"]["value"] == 0  # Defined zero remains a genuine zero.
    absent = evaluate(np.array(["b"] * 4), np.array(["b"] * 4), probabilities, ["a", "b"], "a")[
        "metrics"
    ]
    assert absent["roc_auc"]["value"] is None and absent["average_precision"]["value"] is None


def test_multiclass_metrics_match_reference_and_brier_full_sum():
    y = np.array(["a", "b", "c", "a", "b", "c"])
    prob = np.array(
        [
            [0.7, 0.2, 0.1],
            [0.1, 0.6, 0.3],
            [0.1, 0.2, 0.7],
            [0.3, 0.5, 0.2],
            [0.1, 0.8, 0.1],
            [0.5, 0.1, 0.4],
        ]
    )
    classes = ["a", "b", "c"]
    predicted = np.array(classes)[prob.argmax(axis=1)]
    result = evaluate(y, predicted, prob, classes, None)
    m = result["metrics"]
    for name, fn in [
        ("precision", metrics.precision_score),
        ("recall", metrics.recall_score),
        ("f1", metrics.f1_score),
    ]:
        assert m["macro_" + name]["value"] == fn(y, predicted, average="macro")
    assert m["weighted_f1"]["value"] == metrics.f1_score(y, predicted, average="weighted")
    assert m["macro_ovr_roc_auc"]["value"] == pytest.approx(
        metrics.roc_auc_score(y, prob, multi_class="ovr", average="macro")
    )
    assert m["log_loss"]["value"] == pytest.approx(metrics.log_loss(y, prob))
    truth = np.eye(3)[[0, 1, 2, 0, 1, 2]]
    assert m["brier"]["value"] == pytest.approx(np.mean(np.sum((prob - truth) ** 2, axis=1)))
    assert result["confusion_matrix"] == metrics.confusion_matrix(y, predicted).tolist()


@pytest.mark.parametrize(
    "n,bins", [(40, 3), (99, 3), (100, 5), (249, 5), (250, 8), (499, 8), (500, 10)]
)
def test_calibration_quantile_counts_support_and_warning(n, bins):
    y = np.array(["a" if i % 2 else "b" for i in range(n)])
    p = np.linspace(0, 1, n)
    result = calibration(y, np.column_stack([p, 1 - p]), ["a", "b"], "a")
    assert result["requested_bins"] == bins
    assert len(result["classes"][0]["bins"]) == bins
    assert sum(b["count"] for b in result["classes"][0]["bins"]) == n
    assert bool(result["warning"]) == (n < 250)
    failed = calibration(["a"] * 19 + ["b"] * 21, np.full((40, 2), 0.5), ["a", "b"], "a")
    assert failed["classes"][0]["reason"] and not failed["classes"][0]["bins"]


def test_multiclass_calibration_ties_and_no_missing_observations():
    result = calibration(["a", "b", "c"] * 30, np.full((90, 3), 1 / 3), ["a", "b", "c"], None)
    assert len(result["classes"]) == 3
    for c in result["classes"]:
        assert c["positive_count"] == 30 and c["non_positive_count"] == 60
        assert c["bins"] == [
            {
                "mean_probability": pytest.approx(1 / 3),
                "observed_rate": pytest.approx(1 / 3),
                "count": 90,
            }
        ]


def test_cv_only_development_and_raw_heldout_importance_negative_preserved():
    X, y = data()
    dev, heldout = split_indices(y)
    config = {"classifier": "logistic_regression", "weighting": "standard", "positive_class": "c0"}
    fitted = []
    original = fit_pipeline

    def track(pipeline, frame, target, classifier, weighting):
        fitted.append(set(frame.index))
        return original(pipeline, frame, target, classifier, weighting)

    def importance(pipeline, frame, target, **kwargs):
        assert set(frame.index) == set(heldout) and list(frame.columns) == ["amount", "category"]
        assert list(pipeline.named_steps) == ["semantics", "preprocessor", "classifier"]
        assert kwargs == {
            "scoring": "balanced_accuracy",
            "n_repeats": 10,
            "random_state": 42,
            "n_jobs": 1,
        }
        return SimpleNamespace(
            importances_mean=np.array([-0.1, 0.2]), importances_std=np.array([0.01, 0.02])
        )

    with (
        patch("backend.app.science.baseline.fit_pipeline", side_effect=track),
        patch("backend.app.science.baseline.permutation_importance", side_effect=importance),
    ):
        _, results, reference, membership = train(
            X,
            y,
            np.arange(len(y)),
            config,
            {"amount": "numeric", "category": "categorical"},
            lambda stage: None,
        )
    assert len(fitted) == 6 and fitted[-1] == set(dev)
    assert all(rows <= set(dev) and not rows & set(heldout) for rows in fitted)
    validation = []
    for fold in results["cv_folds"]:
        assert not set(fold["fit"]) & set(fold["validation"])
        assert set(fold["fit"]) | set(fold["validation"]) == set(dev)
        validation += fold["validation"]
    assert sorted(validation) == sorted(dev)
    assert results["importance"][0]["mean"] == -0.1
    assert set(reference.__mm_row_id) == set(heldout)
    assert len(membership) == len(y)
