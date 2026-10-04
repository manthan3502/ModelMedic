import hashlib
import io

import pyarrow.parquet as pq
import pytest

from backend.app.core.config import Settings
from backend.app.domain.datasets import (
    DatasetError,
    missing,
    target_info,
    validate_configuration,
    validate_csv,
)


def settings(**kwargs):
    return Settings(database_url="postgresql+psycopg://localhost/unused", **kwargs)


def baseline(classes=2):
    return (
        "number,category,target\n"
        + "".join(f"{i % 8},group{i % 3},class{i % classes}\n" for i in range(100 * classes))
    ).encode()


def test_canonical_stability_and_lossless_missing_policy():
    content = b"raw,value\n001,NA\n1,N/A\n ,None\n,unknown\nnull,?\n"
    first, profile = validate_csv(content, settings())
    second, again = validate_csv(content, settings())
    assert first == second and profile == again
    assert profile["canonical_sha256"] == hashlib.sha256(first).hexdigest()
    table = pq.read_table(io.BytesIO(first))
    assert table.column("__mm_row_id").to_pylist() == list(range(5))
    assert table.column("raw").to_pylist() == ["001", "1", None, None, "null"]
    assert table.column("value").to_pylist() == ["NA", "N/A", "None", "unknown", "?"]
    assert table.schema.metadata[b"modelmedic.schema_version"] == b"canonical-v1"
    assert missing("\t ") and not missing("NA") and not missing("null")


@pytest.mark.parametrize(
    "content,diagnostic",
    [
        (b"__mm_row_id,x\n1,2\n", "reserved"),
        (b" __mm_x,x\n1,2\n", "reserved"),
        (b"x,x\n1,2\n", "Duplicate"),
        (b"x, x\n1,2\n", "Duplicate"),
        (b"x,\n1,2\n", "header"),
        (b"x,y\n1\n", "widths"),
        (b'x\n"broken\n', "Malformed"),
        (b"x\n\xff\n", "UTF-8"),
        (b"x\n\x00\n", "null bytes"),
        (b"x\n", "no data"),
    ],
)
def test_rejected_imports_are_actionable(content, diagnostic):
    with pytest.raises(DatasetError, match=diagnostic):
        validate_csv(content, settings())


@pytest.mark.parametrize("limit", [{"upload_max_bytes": 2}, {"max_rows": 1}, {"max_columns": 1}])
def test_import_resource_limits(limit):
    with pytest.raises(DatasetError, match="limit"):
        validate_csv(b"a,b\n1,x\n2,y\n", settings(**limit))


@pytest.mark.parametrize(
    "values",
    [
        ["one"] * 200,
        [str(i % 11) for i in range(1100)],
        ["a"] * 100 + ["b"] * 99,
        ["a"] * 100 + [None] + ["b"] * 100,
        ["a"] * 100 + [" a "] * 100,
        [str(i / 10) for i in range(200)],
        ['["a", "b"]'] * 100 + ['["c"]'] * 100,
    ],
)
def test_ineligible_targets(values):
    assert target_info(values)["eligible"] is False


def test_binary_multiclass_support_order_and_safe_normalization():
    info = target_info([" yes "] * 100 + ["no"] * 100)
    assert info["eligible"]
    assert [c["label"] for c in info["classes"]] == ["no", "yes"]
    assert all(c["proportion"] == 0.5 for c in info["classes"])
    assert target_info([str(i % 10) for i in range(1000)])["eligible"]
    assert target_info(["0.1"] * 100 + ["0.2"] * 100)["eligible"]


def test_profile_warnings_and_unsupported_types():
    content = "id,constant,missing,number,category,literal,date,text\n" + "".join(
        f"{i},same,{'1' if i == 0 else ''},{i % 4},{' x' if i % 2 else 'x'},"
        f"{'NA' if i % 2 else '1'},2025-01-01,{'word ' * 16}\n"
        for i in range(200)
    )
    _, profile = validate_csv(content.encode(), settings())
    columns = profile["columns"]
    assert "identifier" in columns[0]["flags"][0]
    assert "Constant" in columns[1]["flags"][0]
    assert any("High missingness" in f for f in columns[2]["flags"])
    assert any("Review feature type" in f for f in columns[3]["flags"])
    assert any("whitespace" in f for f in columns[4]["flags"])
    assert any("literal missing-like" in f for f in columns[5]["flags"])
    assert "Datetime" in columns[6]["unsupported_reason"]
    assert "Free-text" in columns[7]["unsupported_reason"]
    assert columns[7]["allowed_types"] == []
    _, duplicate = validate_csv(b"a\nx\nx\n", settings())
    assert duplicate["duplicate_rows"] == 1
    _, high = validate_csv(
        ("a\n" + "".join(f"value{i}\n" for i in range(101))).encode(), settings()
    )
    assert "cardinality" in high["columns"][0]["unsupported_reason"]


def config():
    return {
        "target_id": "f002",
        "positive_class": "class1",
        "features": [{"feature_id": "f000", "type": "numeric"}],
        "classifier": "logistic_regression",
        "weighting": "standard",
    }


def test_feature_overrides_and_encoded_column_limits():
    _, profile = validate_csv(baseline(), settings())
    choice = config()
    assert validate_configuration(profile, choice, settings())["encoded_columns"] == 1
    choice["features"][0]["type"] = "categorical"
    assert validate_configuration(profile, choice, settings())["encoded_columns"] == 9
    with pytest.raises(DatasetError, match="Encoded-column"):
        validate_configuration(profile, choice, settings(max_encoded_columns=8))
    choice["features"] = [{"feature_id": "f001", "type": "numeric"}]
    with pytest.raises(DatasetError, match="override"):
        validate_configuration(profile, choice, settings())


@pytest.mark.parametrize(
    "changes",
    [
        {"positive_class": None},
        {"positive_class": "wrong"},
        {"target_id": "unknown"},
        {"features": []},
        {"features": [{"feature_id": "f002", "type": "categorical"}]},
        {"features": [{"feature_id": "f000", "type": "numeric"}] * 2},
    ],
)
def test_configuration_rejects_invalid_choices(changes):
    _, profile = validate_csv(baseline(), settings())
    with pytest.raises(DatasetError):
        validate_configuration(profile, {**config(), **changes}, settings())
