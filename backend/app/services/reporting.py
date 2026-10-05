"""Reviewed deterministic templates over immutable facts; no scientific calculation."""

from typing import Any

from backend.app.science.labeled import PERFORMANCE_LIMITATION
from backend.app.science.monitoring import MODE_A_LIMITATION
from backend.app.science.slices import SLICE_LIMITATION

REPORT_TEMPLATE_VERSION = "report-v1"
REPORT_FOOTER = (
    "Generated from stored results using fixed reviewed templates. No "
    "language model generated this report."
)
FEATURE_LIMITATION = (
    "ModelMedic does not claim this feature change caused any change in performance."
)
REPORT_LIMITATIONS = [
    "Data drift does not prove predictive degradation.",
    "Actual current predictive performance and calibration require ground-truth labels.",
    "Statistical significance does not imply practical importance.",
    "Permutation importance is a model reliance estimate, not causal importance.",
    "Small samples may be unstable; product guardrails are not universal statistical laws.",
    PERFORMANCE_LIMITATION,
    SLICE_LIMITATION,
    "ModelMedic does not establish causality.",
    "NOT DETECTED does not prove populations are identical or stable.",
]


def diagnostic(feature: dict[str, Any], reference: str) -> dict[str, str]:
    return {
        "measured": "Raw observed non-missing values · " + reference,
        "result": "Distribution: "
        + feature["distribution"]["status"]
        + "; missingness: "
        + feature["missingness"]["status"]
        + ".",
        "may_conclude": (
            "The test evaluates evidence of a marginal distribution difference"
            " in the available samples. Review distance, sample sizes and "
            "context separately."
        ),
        "cannot_conclude": FEATURE_LIMITATION,
        "reliance": (
            "Model reliance estimate — not causal importance. Shuffling this "
            "feature did not reduce held-out Balanced Accuracy on average in "
            "these repeats. Negative values can arise from sampling variation,"
            " correlated features, or model behaviour and are not causal "
            "evidence."
        )
        if feature.get("reliance") and feature["reliance"]["mean"] <= 0
        else (
            "Model reliance estimate — not causal importance. Mean and "
            "standard deviation describe held-out Balanced Accuracy changes "
            "across ten raw-feature permutations."
        ),
    }


def finding(measured: str, result: str, evidence: str, may: str, cannot: str) -> dict[str, str]:
    return {
        "measured": measured,
        "result": result,
        "evidence": evidence,
        "may_conclude": may,
        "cannot_conclude": cannot,
    }


def table(caption: str, columns: list[str], rows: list[list[Any]]) -> dict[str, Any]:
    return {"caption": caption, "columns": columns, "rows": rows}


def build_report(
    project: dict[str, Any],
    baseline: dict[str, Any],
    run: dict[str, Any],
    results: dict[str, Any],
    generated_at: str,
    code_version: str,
) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []

    def section(
        key: str,
        title: str,
        paragraphs: list[str],
        tables: list[dict[str, Any]] | None = None,
        findings: list[dict[str, str]] | None = None,
    ) -> None:
        sections.append(
            {
                "key": key,
                "title": title,
                "paragraphs": paragraphs,
                "tables": tables or [],
                "findings": findings or [],
            }
        )

    section("project", "Project", [project["name"], project.get("description") or ""])
    section(
        "baseline",
        "Baseline",
        ["The model, preprocessing, features, target and class order are frozen."],
        [
            table(
                "Frozen baseline configuration and references",
                ["Fact", "Stored value"],
                [[k, v] for k, v in baseline.items()],
            )
        ],
    )
    section(
        "run",
        "Run metadata",
        ["Mode " + results["mode"]],
        [table("Monitoring run", ["Fact", "Stored value"], [[k, v] for k, v in run.items()])],
    )
    validation = results["validation"]
    section(
        "schema",
        "Schema / compatibility",
        [
            "All required frozen features passed compatibility review.",
            *validation.get("warnings", []),
        ],
        [
            table(
                "Compatibility",
                ["Fact", "Stored value"],
                [
                    ["Required features", validation.get("required_features", [])],
                    ["Ignored extra columns", validation.get("ignored_extra_columns", [])],
                    ["Canonical SHA-256", results["canonical_sha256"]],
                ],
            )
        ],
    )
    features = results["features"]
    data_rows = []
    for f in features:
        d, m = f["distribution"], f["missingness"]
        data_rows.append(
            [
                f["name"],
                f["type"],
                d["status"],
                m["status"],
                d.get("test"),
                d.get("statistic"),
                d.get("distance_name"),
                d.get("distance"),
                d.get("raw_p"),
                d.get("adjusted_p"),
                results["bh_family_size"],
                d["baseline_n"],
                d["current_n"],
                m["delta_pp"],
                f.get("reliance"),
                d.get("warnings", []),
            ]
        )
    section(
        "data",
        "Data changes",
        [results["data_reference"], FEATURE_LIMITATION],
        [
            table(
                "Separate feature distribution and missingness evidence",
                [
                    "Feature",
                    "Frozen type",
                    "Distribution",
                    "Missingness",
                    "Test",
                    "Statistic",
                    "Distance",
                    "Distance value",
                    "Raw p",
                    "Adjusted p",
                    "BH family size",
                    "Baseline n",
                    "Current n",
                    "Missing Δ pp",
                    "Baseline reliance",
                    "Cautions",
                ],
                data_rows,
            )
        ],
        [
            finding(
                "Raw observed feature distributions and missingness",
                "Separate per-feature signals are recorded.",
                "BH family size "
                + str(results["bh_family_size"])
                + "; q = 0.05. "
                + results["data_reference"],
                "Detected signals provide evidence of difference; review magnitude and context.",
                (
                    "Drift does not prove predictive degradation. NOT DETECTED does "
                    "not prove equality. "
                )
                + FEATURE_LIMITATION,
            )
        ],
    )
    predictions = results["predictions"]
    section(
        "predictions",
        "Prediction behavior",
        [],
        [
            table(
                "Frozen predicted class shares",
                ["Class", "Baseline share", "Current share", "Baseline count", "Current count"],
                [
                    [
                        c["category"],
                        c["baseline_share"],
                        c["current_share"],
                        c["baseline_count"],
                        c["current_count"],
                    ]
                    for c in predictions["categories"]
                ],
            )
        ],
        [
            finding(
                "Predicted class distribution · " + results["model_reference"],
                predictions["status"],
                (
                    f"Baseline n = {predictions['baseline_n']}; "
                    f"Current n = {predictions['current_n']}; "
                    f"JS distance = {predictions.get('distance')}; "
                    f"test = {predictions.get('test')}; "
                    f"p = {predictions.get('raw_p')}."
                ),
                predictions["interpretation"],
                predictions["limitation"],
            )
        ],
    )
    confidence = results["confidence"]
    section(
        "confidence",
        "Confidence",
        [],
        [
            table(
                "Max class probability · held-out baseline vs current",
                ["Measure", "Baseline", "Current"],
                [
                    ["Mean", confidence["baseline_mean"], confidence["current_mean"]],
                    ["Median", confidence["baseline_median"], confidence["current_median"]],
                    ["n", confidence["baseline_n"], confidence["current_n"]],
                ],
            )
        ],
        [
            finding(
                "Max predicted class probability",
                confidence["status"],
                (
                    f"KS = {confidence.get('statistic')}; "
                    f"p = {confidence.get('raw_p')}; "
                    f"Baseline n = {confidence['baseline_n']}; "
                    f"Current n = {confidence['current_n']}."
                ),
                "These observations describe model confidence in the supplied samples.",
                confidence["limitation"],
            )
        ],
    )
    if results["mode"] == "B":
        performance = results["performance"]
        section(
            "performance",
            "Performance",
            [PERFORMANCE_LIMITATION, *performance["warnings"]],
            [
                table(
                    "Measured performance · signed Δ in metric units",
                    [
                        "Metric",
                        "Baseline",
                        "Current",
                        "Δ",
                        "Baseline support",
                        "Current support",
                        "Availability / reason / note",
                    ],
                    [
                        [
                            m["metric_name"],
                            m["baseline_value"],
                            m["current_value"],
                            m["delta"],
                            m["baseline_support"],
                            m["current_support"],
                            " ".join(v for v in [m["status"], m["reason"], m["note"]] if v),
                        ]
                        for m in performance["metrics"]
                    ],
                ),
                table(
                    "True class composition · held-out baseline vs current",
                    ["Class", "Baseline count", "Current count", "Baseline share", "Current share"],
                    [
                        [
                            c["category"],
                            c["baseline_count"],
                            c["current_count"],
                            c["baseline_share"],
                            c["current_share"],
                        ]
                        for c in performance["class_composition"]
                    ],
                ),
            ],
            [
                finding(
                    "Actual labeled predictive performance",
                    "Stored metric comparisons with availability and sample sizes.",
                    (
                        f"Baseline n = {performance['baseline_n']}; "
                        f"Current n = {performance['current_n']}."
                    ),
                    (
                        "These metrics describe predictive performance on the supplied "
                        "labeled observations."
                    ),
                    PERFORMANCE_LIMITATION,
                )
            ],
        )
        calibration = results["calibration"]
        bins = []
        cautions = []
        for series in ("baseline", "current"):
            curve = calibration[series]
            if curve["warning"]:
                cautions.append(series.capitalize() + ": " + curve["warning"])
            for c in curve["classes"]:
                if c["reason"]:
                    bins.append(
                        [
                            series,
                            c["class"],
                            None,
                            None,
                            None,
                            c["positive_count"],
                            c["non_positive_count"],
                            c["reason"],
                        ]
                    )
                for b in c["bins"]:
                    bins.append(
                        [
                            series,
                            c["class"],
                            b["mean_probability"],
                            b["observed_rate"],
                            b["count"],
                            c["positive_count"],
                            c["non_positive_count"],
                            "AVAILABLE",
                        ]
                    )
        section(
            "calibration",
            "Calibration",
            cautions,
            [
                table(
                    (
                        "Persisted reliability bins · Brier/Log Loss appear in Performance"
                        " as probability quality"
                    ),
                    [
                        "Series",
                        "Class",
                        "Mean predicted probability",
                        "Observed frequency",
                        "Bin n",
                        "Positive n",
                        "Non-positive n",
                        "Availability",
                    ],
                    bins,
                )
            ],
            [
                finding(
                    "Reliability bins and probability quality",
                    "Historical baseline and current empirical frequencies with support.",
                    (
                        f"Baseline n = {calibration['baseline']['support']}; "
                        f"Current n = {calibration['current']['support']}."
                    ),
                    (
                        "Compare empirical frequencies with mean predicted probabilities "
                        "in these samples."
                    ),
                    PERFORMANCE_LIMITATION,
                )
            ],
        )
        errors = results["errors"]
        counts = []
        for series in ("baseline", "current"):
            for i, actual in enumerate(errors["class_order"]):
                for j, predicted in enumerate(errors["class_order"]):
                    counts.append(
                        [
                            series,
                            actual,
                            predicted,
                            errors[series]["counts"][i][j],
                            errors[series]["normalized"][i][j],
                        ]
                    )
        section(
            "errors",
            "Classes & errors",
            [
                errors["normalization"],
                (
                    "Example rows are not copied into reports. Included-feature "
                    "examples remain bounded canonical source references."
                ),
            ],
            [
                table(
                    "Confusion counts and actual-class row-normalized rates",
                    ["Series", "Actual", "Predicted", "Count", "Rate"],
                    counts,
                )
            ],
            [
                finding(
                    "Frozen-class confusion counts and actual-class rates",
                    "Recorded labeled errors with support; unsupported rates remain unavailable.",
                    f"Class order = {errors['class_order']}; {errors['normalization']}",
                    "These counts describe observed errors on the supplied labeled samples.",
                    "Errors do not establish a cause or justify an automatic "
                    "retraining recommendation.",
                )
            ],
        )
        error_tables = sections[-1]["tables"]
        for series in ("baseline", "current"):
            if "binary" in errors[series]:
                error_tables.append(
                    table(
                        series.capitalize()
                        + " binary counts · selected positive class "
                        + str(errors["positive_class"]),
                        ["Kind", "Count"],
                        [[k.upper(), v] for k, v in errors[series]["binary"].items()],
                    )
                )
            else:
                error_tables.append(
                    table(
                        series.capitalize() + " common confusion pairs",
                        ["Actual", "Predicted", "Count", "Actual support", "Rate"],
                        [
                            [
                                p["actual"],
                                p["predicted"],
                                p["count"],
                                p["actual_support"],
                                p["rate"],
                            ]
                            for p in errors[series]["common_pairs"]
                        ],
                    )
                )
    else:
        for key, title in (
            ("performance", "Performance"),
            ("calibration", "Calibration"),
            ("errors", "Classes & errors"),
        ):
            section(
                key,
                title,
                ["Unavailable — ground-truth labels were not provided.", MODE_A_LIMITATION],
                findings=[
                    finding(
                        title,
                        "Unavailable",
                        "Mode A: target column absent.",
                        "Data, prediction behavior and confidence can still be inspected.",
                        MODE_A_LIMITATION,
                    )
                ],
            )
    section(
        "slices",
        "Slices if created",
        (
            ["Unavailable — ground-truth labels were not provided.", MODE_A_LIMITATION]
            if results["mode"] == "A"
            else [
                (
                    "Slice analyses are separately versioned additive results. None "
                    "were included in this core report at creation. Later completed "
                    "analyses are shown separately without rewriting this payload."
                ),
            ]
        )
        + [SLICE_LIMITATION],
    )
    section("limitations", "Limitations", REPORT_LIMITATIONS + results.get("limitations", []))
    return {
        "report_template_version": REPORT_TEMPLATE_VERSION,
        "methodology_version": results["methodology_version"],
        "code_version": code_version,
        "source_code_version": results["code_version"],
        "generated_at": generated_at,
        "run_id": run["id"],
        "sections": sections,
        "footer": REPORT_FOOTER,
    }
