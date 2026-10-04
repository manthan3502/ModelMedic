"""Worker-only persistence and guarded deserialization of internally generated pipelines."""

import platform
from hashlib import sha256
from io import BytesIO
from typing import Any

import joblib
import numpy
import pandas
import scipy
import sklearn

from backend.app.science.baseline import ARTIFACT_VERSION, TrainingError
from backend.app.storage.base import ArtifactStore


def environment() -> dict[str, str]:
    return {
        "python_version": platform.python_version(),
        "scikit_learn_version": sklearn.__version__,
        "numpy_version": numpy.__version__,
        "scipy_version": scipy.__version__,
        "pandas_version": pandas.__version__,
    }


def dump(pipeline: Any) -> bytes:
    stream = BytesIO()
    joblib.dump(pipeline, stream, compress=3)
    return stream.getvalue()


def load_trusted(
    store: ArtifactStore, key: str, expected_hash: str, manifest: dict[str, Any]
) -> Any:
    # Callers obtain all three arguments from the trusted model_artifacts database row.
    data = store.get(key)
    runtime = environment()
    if (
        sha256(data).hexdigest() != expected_hash
        or manifest.get("artifact_sha256") != expected_hash
    ):
        raise TrainingError("Artifact integrity check failed. The frozen model cannot be loaded.")
    if manifest.get("artifact_version") != ARTIFACT_VERSION:
        raise TrainingError("Artifact compatibility error: unsupported artifact version.")
    if (
        str(manifest.get("python_version", "")).split(".")[:2]
        != runtime["python_version"].split(".")[:2]
        or manifest.get("scikit_learn_version") != runtime["scikit_learn_version"]
    ):
        raise TrainingError(
            "Artifact compatibility error: Python minor and exact scikit-learn versions must match."
        )
    return joblib.load(BytesIO(data))
