import json
from io import BytesIO
from unittest.mock import patch

import boto3
import numpy as np
import pytest
from botocore.stub import Stubber
from fastapi.testclient import TestClient
from pydantic import ValidationError
from scipy import stats
from scipy.spatial.distance import jensenshannon

from backend.app.core.config import Settings
from backend.app.domain.datasets import (
    DatasetError,
    parse_csv,
    validate_configuration,
    validate_csv,
)
from backend.app.jobs.artifacts import environment, load_trusted
from backend.app.main import create_app
from backend.app.science.baseline import ARTIFACT_VERSION, TrainingError, split_indices
from backend.app.science.monitoring import (
    categorical_drift,
    correct_family,
    missingness,
    numeric_drift,
)
from backend.app.storage.local import LocalArtifactStore
from backend.app.storage.s3 import S3ArtifactStore


def s3_client():
    return boto3.client(
        "s3", region_name="us-east-1", aws_access_key_id="fixture", aws_secret_access_key="fixture"
    )


def test_s3_conditional_encrypted_private_objects_and_scoped_cleanup(tmp_path):
    client = s3_client()
    store = S3ArtifactStore(
        "private-fixture",
        "application",
        "us-east-1",
        client=client,
        server_side_encryption="AES256",
    )
    with Stubber(client) as stub:
        stub.add_response(
            "put_object",
            {},
            {
                "Bucket": "private-fixture",
                "Key": "application/projects/one/data",
                "Body": b"synthetic",
                "IfNoneMatch": "*",
                "ServerSideEncryption": "AES256",
            },
        )
        store.put("projects/one/data", b"synthetic")
        stub.add_response(
            "get_object",
            {"Body": BytesIO(b"synthetic")},
            {"Bucket": "private-fixture", "Key": "application/projects/one/data"},
        )
        assert store.get("projects/one/data") == b"synthetic"
        stub.add_response(
            "delete_object", {}, {"Bucket": "private-fixture", "Key": "application/projects/one"}
        )
        stub.add_response(
            "list_objects_v2",
            {"Contents": [{"Key": "application/projects/one/data"}]},
            {"Bucket": "private-fixture", "Prefix": "application/projects/one/"},
        )
        stub.add_response(
            "delete_objects",
            {},
            {
                "Bucket": "private-fixture",
                "Delete": {"Objects": [{"Key": "application/projects/one/data"}], "Quiet": True},
            },
        )
        store.delete_prefix("projects/one")
        stub.assert_no_pending_responses()


def test_s3_denies_overwrites_access_errors_and_demo_writes():
    client = s3_client()
    store = S3ArtifactStore("private-fixture", "application", "us-east-1", client=client)
    with Stubber(client) as stub:
        stub.add_client_error(
            "put_object", service_error_code="PreconditionFailed", http_status_code=412
        )
        with pytest.raises(OSError, match="Private artifact"):
            store.put("projects/one/data", b"overwrite")
        stub.add_client_error(
            "head_object", service_error_code="AccessDenied", http_status_code=403
        )
        with pytest.raises(OSError):
            store.exists("projects/one/data")
        stub.add_client_error("head_object", service_error_code="404", http_status_code=404)
        assert not store.exists("projects/one/missing")
    store.read_only = True
    for action in (
        lambda: store.put("data", b"no"),
        lambda: store.delete("data"),
        lambda: store.delete_prefix("projects/one"),
    ):
        with pytest.raises(PermissionError):
            action()
    with pytest.raises(ValueError):
        store.get("../escape")


def test_same_origin_frontend_host_guard_api_errors_and_demo_fail_closed(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>built application</html>")
    (tmp_path / "assets" / "app.js").write_text("/* built */")
    settings = Settings(
        database_url="postgresql+psycopg://unused/unused",
        frontend_root=tmp_path,
        artifact_root=tmp_path / "private",
        deployment_mode="demo",
    )
    with TestClient(create_app(settings)) as client:
        for page in ("/", "/projects", "/methodology", "/projects/" + "a" * 36 + "/trends"):
            response = client.get(page)
            assert response.status_code == 200 and "built application" in response.text
            assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/api/v1/future-export").status_code == 403
        assert client.get("/api/v1/projects").status_code == 503
        assert client.get("/private/index.html").status_code == 403
        assert client.get("/assets/../index.html").status_code != 200
        for path in ("/projects", "/assets/app.js", "/api/v1/runtime"):
            assert client.options(path).status_code == 403
        assert client.get("/projects", headers={"Host": "untrusted.invalid"}).status_code == 400
    with pytest.raises(ValidationError, match="private S3"):
        Settings(
            database_url=settings.database_url, environment="deployment", deployment_mode="demo"
        )


def test_missing_and_corrupt_artifacts_never_deserialize(tmp_path):
    store = LocalArtifactStore(tmp_path)
    with patch("backend.app.jobs.artifacts.joblib.load") as deserialize:
        with pytest.raises(TrainingError, match="unavailable"):
            load_trusted(store, "projects/missing", "0" * 64, {})
        store.put("projects/corrupt", b"not joblib")
        with pytest.raises(TrainingError, match="integrity"):
            load_trusted(
                store,
                "projects/corrupt",
                "0" * 64,
                {**environment(), "artifact_version": ARTIFACT_VERSION},
            )
        deserialize.assert_not_called()


def test_distribution_known_answers_match_scipy_explicit_tolerances():
    a, b = np.arange(30), np.arange(30) + 2
    actual = numeric_drift(a.tolist(), b.tolist())
    expected = stats.ks_2samp(a, b, alternative="two-sided", method="auto")
    assert actual["statistic"] == pytest.approx(expected.statistic, abs=1e-12)
    assert actual["raw_p"] == pytest.approx(expected.pvalue, rel=1e-12, abs=1e-15)
    assert actual["distance"] == pytest.approx(stats.wasserstein_distance(a, b), abs=1e-12)
    assert numeric_drift(a[:29].tolist(), b.tolist())["raw_p"] is None
    categories = categorical_drift(["a"] * 40 + ["b"] * 60, ["a"] * 70 + ["b"] * 30)
    expected_chi = stats.chi2_contingency([[40, 60], [70, 30]], correction=False)
    assert categories["statistic"] == pytest.approx(expected_chi.statistic, rel=1e-12)
    assert categories["raw_p"] == pytest.approx(expected_chi.pvalue, rel=1e-12)
    assert categories["distance"] == pytest.approx(
        jensenshannon([0.4, 0.6], [0.7, 0.3], base=2), abs=1e-12
    )
    for counts in ((100, 100, 10, 30), (100, 100, 1, 4)):
        n, m, x, y = counts
        actual = missingness(*counts)
        table = [[x, n - x], [y, m - y]]
        expected_p = (
            stats.chi2_contingency(table, correction=False).pvalue
            if actual["test"] == "Chi-square"
            else stats.fisher_exact(table, alternative="two-sided").pvalue
        )
        assert actual["raw_p"] == pytest.approx(expected_p, rel=1e-12, abs=1e-15)
    p = [0.003, 0.08, 0.02, 0.01]
    features = [
        {
            "distribution": {"raw_p": p[i], "status": "DETECTED"},
            "missingness": {"raw_p": p[i + 1], "status": "DETECTED"},
        }
        for i in (0, 2)
    ]
    assert correct_family(features) == 4
    np.testing.assert_allclose(
        [f[k]["adjusted_p"] for f in features for k in ("distribution", "missingness")],
        stats.false_discovery_control(p, method="bh"),
        rtol=1e-12,
        atol=1e-15,
    )


@pytest.mark.parametrize("classes", [2, 3, 10])
def test_minimum_baseline_class_boundaries_and_extreme_imbalance(classes):
    y = [f"c{i}" for i in range(classes) for _ in range(100)]
    development, heldout = split_indices(y)
    assert len(development) == classes * 80 and len(heldout) == classes * 20
    assert all(sum(y[i] == f"c{k}" for i in heldout) == 20 for k in range(classes))
    development, heldout = split_indices(["majority"] * 4900 + ["minority"] * 100)
    assert sum(i >= 4900 for i in heldout) == 20


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"x\n",
        b"x,x\n1,2\n",
        b"__mm_x\n1\n",
        b'x\n"unclosed\n',
        b"x\n\xff\n",
        b"x\n" + b"a" * 140_000 + b"\n",
    ],
    ids=["empty", "header-only", "duplicates", "reserved", "malformed", "encoding", "long-cell"],
)
def test_parser_pathological_inputs_have_reviewed_errors(content):
    with pytest.raises(DatasetError):
        parse_csv(content, Settings(database_url="postgresql+psycopg://unused/unused"))


def test_formula_html_and_whitespace_are_literal_values_not_cleaned():
    payload = b"category\n=SUM(1)\n<script>alert(1)</script>\n raw \nraw\n"
    _, profile = validate_csv(payload, Settings(database_url="postgresql+psycopg://unused/unused"))
    assert profile["preview"] == [["=SUM(1)"], ["<script>alert(1)</script>"], [" raw "], ["raw"]]
    assert "have not been merged" in json.dumps(profile)


def test_default_resource_boundaries_rows_columns_features_and_encoded_columns():
    settings = Settings(database_url="postgresql+psycopg://unused/unused")
    headers, rows = parse_csv(b"x\n" + b"1\n" * 50_000, settings)
    assert headers == ["x"] and len(rows) == 50_000
    with pytest.raises(DatasetError, match="row limit"):
        parse_csv(b"x\n" + b"1\n" * 50_001, settings)
    for count in (100, 101):
        content = (
            ",".join(f"x{i}" for i in range(count)) + "\n" + ",".join(["1"] * count) + "\n"
        ).encode()
        if count == 100:
            assert len(parse_csv(content, settings)[0]) == 100
        else:
            with pytest.raises(DatasetError, match="input-column"):
                parse_csv(content, settings)
    # Real profiling, 50 inputs, 20 categorical fields at 97/98 raw levels including
    # the required missing-category estimate: exactly 2,000 encoded columns.
    content = (
        ",".join([f"c{i}" for i in range(20)] + [f"x{i}" for i in range(31)] + ["target"]) + "\n"
    )
    for row in range(300):
        content += (
            ",".join(
                [f"level{row % (97 if i < 10 else 98)}" for i in range(20)]
                + [str(row)] * 31
                + ["a" if row % 2 else "b"]
            )
            + "\n"
        )
    _, profile = validate_csv(content.encode(), settings)
    config = {
        "target_id": "f051",
        "positive_class": "a",
        "classifier": "logistic_regression",
        "weighting": "standard",
        "features": [
            {"feature_id": f"f{i:03}", "type": "categorical" if i < 20 else "numeric"}
            for i in range(50)
        ],
    }
    assert validate_configuration(profile, config, settings)["encoded_columns"] == 2000
    config["features"].append({"feature_id": "f050", "type": "numeric"})
    with pytest.raises(DatasetError, match="feature limit"):
        validate_configuration(profile, config, settings)
    config["features"].pop()
    with pytest.raises(DatasetError, match="Encoded-column"):
        validate_configuration(
            profile, config, settings.model_copy(update={"max_encoded_columns": 1999})
        )
    # Exact default byte boundary enters the parser and fails the pathological cell
    # guard; one byte over is rejected before decoding/parsing at all.
    payload = b"x\n" + b"a" * (settings.upload_max_bytes - 2)
    with pytest.raises(DatasetError, match="Malformed"):
        parse_csv(payload, settings)
    with pytest.raises(DatasetError, match="byte limit"):
        parse_csv(payload + b"a", settings)


def test_all_missing_categorical_near_missing_numeric_and_constant_numeric_semantics():
    import pandas as pd

    from backend.app.science.baseline import fit_pipeline, make_pipeline

    settings = Settings(database_url="postgresql+psycopg://unused/unused")
    content = (
        "empty,near,constant,target\n"
        + "".join(f",{'1' if i == 0 else ''},7,{'a' if i % 2 else 'b'}\n" for i in range(200))
    ).encode()
    _, profile = validate_csv(content, settings)
    assert profile["columns"][0]["missing_count"] == 200
    assert profile["columns"][1]["missing_count"] == 199
    assert any("High missingness" in flag for flag in profile["columns"][1]["flags"])
    types = {"empty": "categorical", "near": "numeric", "constant": "numeric"}
    frame = pd.DataFrame(
        {"empty": [None] * 200, "near": ["1"] + [None] * 199, "constant": ["7"] * 200}
    )
    pipeline = fit_pipeline(
        make_pipeline(types, "logistic_regression", "standard"),
        frame,
        ["a", "b"] * 100,
        "logistic_regression",
        "standard",
    )
    assert pipeline.predict_proba(frame).shape == (200, 2)
    assert pipeline["preprocessor"].named_transformers_["categorical"].categories_[0].tolist() == [
        "m:"
    ]
    with pytest.raises(TrainingError, match="no observed"):
        fit_pipeline(
            make_pipeline(types, "logistic_regression", "standard"),
            frame.assign(near=None),
            ["a", "b"] * 100,
            "logistic_regression",
            "standard",
        )


def test_exact_categorical_cardinality_boundary():
    settings = Settings(database_url="postgresql+psycopg://unused/unused")
    _, profile = validate_csv(
        ("c\n" + "".join(f"level{i}\n" for i in range(100))).encode(), settings
    )
    assert profile["columns"][0]["allowed_types"] == ["categorical"]
