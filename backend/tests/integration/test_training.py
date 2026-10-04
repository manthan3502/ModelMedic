from hashlib import sha256
from io import BytesIO
from unittest.mock import patch
from uuid import UUID, uuid4

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import select, update

from backend.app.db.models import BaselineSnapshot, Job, ModelArtifact, Project
from backend.app.domain.jobs import OwnershipLost
from backend.app.jobs.artifacts import load_trusted
from backend.app.jobs.training import training_result
from backend.app.jobs.worker import run_once
from backend.app.science.baseline import TrainingError
from backend.tests.integration.test_setup import choice, validated
from backend.tests.integration.test_setup import setup_client as setup_client

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "classes,classifier,weighting",
    [
        (2, "logistic_regression", "standard"),
        (2, "random_forest", "balanced"),
        (2, "gradient_boosting", "balanced"),
        (3, "logistic_regression", "balanced"),
        (3, "random_forest", "standard"),
        (3, "gradient_boosting", "standard"),
    ],
)
def test_train_reload_establish_and_all_mutations_blocked(
    setup_client, classes, classifier, weighting
):
    client, queue, store, settings = setup_client
    content = (
        "amount,segment,outcome\n"
        + "\n".join(f"{i % 17},group{i % 3},class{i % classes}" for i in range(classes * 150))
        + "\n"
    ).encode()
    project_id, p = validated(setup_client, content)
    config = choice(
        p,
        classifier=classifier,
        weighting=weighting,
        positive_class="class0" if classes == 2 else None,
    )
    assert (
        client.put(f"/api/v1/projects/{project_id}/configuration", json=config).status_code == 200
    )
    assert client.post(f"/api/v1/projects/{project_id}/train").status_code == 202
    assert client.post(f"/api/v1/projects/{project_id}/train").status_code == 409
    with patch.object(queue, "stage", wraps=queue.stage) as stage:
        assert run_once(queue, uuid4(), 1, store, settings)
    assert [call.args[1] for call in stage.call_args_list] == [
        "VALIDATING",
        "SPLITTING",
        "CROSS_VALIDATING",
        "TRAINING",
        "EVALUATING",
        "CALIBRATION",
        "IMPORTANCE",
        "PERSISTING",
    ]
    p = client.get(f"/api/v1/projects/{project_id}").json()
    assert p["job"]["state"] == "SUCCEEDED", p
    result = p["baseline"]["results"]
    assert result["development_count"] == classes * 120 and result["heldout_count"] == classes * 30
    assert result["manifest"]["class_order"] == [f"class{i}" for i in range(classes)]
    with queue.sessions() as session:
        artifact = session.scalar(select(ModelArtifact))
        snapshot = session.get(BaselineSnapshot, UUID(p["baseline"]["id"]))
        loaded = load_trusted(
            store, artifact.storage_key, artifact.sha256, artifact.environment_manifest
        )
        reference = pd.read_parquet(BytesIO(store.get(snapshot.heldout_reference_object_key)))
        probability_columns = [f"__mm_probability_{i}" for i in range(classes)]
        np.testing.assert_array_equal(
            loaded.predict_proba(reference[["amount", "segment"]]), reference[probability_columns]
        )
        assert sha256(store.get(artifact.storage_key)).hexdigest() == artifact.sha256
        assert not reference.__mm_row_id.duplicated().any()
        split = pd.read_parquet(BytesIO(store.get(snapshot.split_membership_object_key)))
        assert set(split.loc[split.partition == "heldout", "__mm_row_id"]) == set(
            reference.__mm_row_id
        )
        manifest = artifact.environment_manifest
        with patch("backend.app.jobs.artifacts.joblib.load") as deserialize:
            for key, value in [
                ("artifact_version", "unsupported"),
                ("python_version", "0.0.0"),
                ("scikit_learn_version", "0.0"),
            ]:
                with pytest.raises(TrainingError, match="compatibility"):
                    load_trusted(
                        store, artifact.storage_key, artifact.sha256, {**manifest, key: value}
                    )
            with pytest.raises(TrainingError, match="integrity"):
                load_trusted(store, artifact.storage_key, "0" * 64, manifest)
            deserialize.assert_not_called()
    for section in ["summary", "metrics", "calibration", "importance"]:
        assert client.get(f"/api/v1/projects/{project_id}/baseline/{section}").status_code == 200
    established = client.post(
        f"/api/v1/projects/{project_id}/establish", json={"snapshot_id": p["baseline"]["id"]}
    )
    assert established.status_code == 200, established.text
    assert established.json()["state"] == "BASELINE_READY"
    assert established.json()["baseline"]["status"] == "ESTABLISHED"
    for field, value in [
        ("target_id", "f001"),
        ("positive_class", "class1"),
        ("features", []),
        ("features", [{"feature_id": "f000", "type": "categorical"}]),
        ("classifier", "random_forest"),
        ("weighting", "standard"),
    ]:
        assert (
            client.put(
                f"/api/v1/projects/{project_id}/configuration?discard_results=true",
                json={**config, field: value},
            ).status_code
            == 409
        )
    assert (
        client.post(
            f"/api/v1/projects/{project_id}/baseline",
            content=content,
            headers={"Content-Type": "text/csv"},
        ).status_code
        == 409
    )
    assert client.post(f"/api/v1/projects/{project_id}/train").status_code == 409
    assert (
        client.post(
            f"/api/v1/projects/{project_id}/establish", json={"snapshot_id": p["baseline"]["id"]}
        ).status_code
        == 409
    )
    assert client.delete(f"/api/v1/projects/{project_id}").status_code == 409
    # No API for changing deterministic preprocessing, nor monitoring functionality.
    assert client.put(f"/api/v1/projects/{project_id}/preprocessing", json={}).status_code == 404
    assert client.post(f"/api/v1/projects/{project_id}/runs", json={}).status_code == 404


def trained(setup_client):
    client, queue, store, settings = setup_client
    project_id, p = validated(setup_client)
    config = choice(p, classifier="logistic_regression", weighting="standard")
    client.put(f"/api/v1/projects/{project_id}/configuration", json=config)
    client.post(f"/api/v1/projects/{project_id}/train")
    run_once(queue, uuid4(), 1, store, settings)
    p = client.get(f"/api/v1/projects/{project_id}").json()
    assert p["baseline"]["status"] == "TRAINED", p
    return project_id, p, config


def test_config_change_requires_confirmation_invalidates_and_stale_fingerprint_rejected(
    setup_client,
):
    client, queue, store, _ = setup_client
    project_id, p, config = trained(setup_client)
    old = p["baseline"]["id"]
    with queue.sessions.begin() as session:
        project = session.get(Project, UUID(project_id))
        project.positive_class = "class0"
    assert (
        client.post(
            f"/api/v1/projects/{project_id}/establish", json={"snapshot_id": old}
        ).status_code
        == 409
    )
    changed = {**config, "weighting": "balanced"}
    assert (
        client.put(f"/api/v1/projects/{project_id}/configuration", json=changed).status_code == 409
    )
    with queue.sessions() as session:
        artifact = session.scalar(select(ModelArtifact))
        key = artifact.storage_key
    assert (
        client.put(
            f"/api/v1/projects/{project_id}/configuration?discard_results=true", json=changed
        ).status_code
        == 200
    )
    assert not store.exists(key)
    assert (
        client.post(
            f"/api/v1/projects/{project_id}/establish", json={"snapshot_id": old}
        ).status_code
        == 409
    )
    assert client.get(f"/api/v1/projects/{project_id}").json()["baseline"] is None


def test_actual_split_guard_failure_publishes_no_model(setup_client):
    client, queue, store, settings = setup_client
    project_id, p = validated(setup_client)
    client.put(f"/api/v1/projects/{project_id}/configuration", json=choice(p))
    client.post(f"/api/v1/projects/{project_id}/train")
    with patch(
        "backend.app.science.baseline.guard_heldout",
        side_effect=TrainingError("Actual held-out support is below 20 for a class."),
    ):
        run_once(queue, uuid4(), 1, store, settings)
    p = client.get(f"/api/v1/projects/{project_id}").json()
    assert p["job"]["state"] == "FAILED" and "below 20" in p["job"]["error_message"]
    assert p["baseline"]["status"] == "FAILED" and p["baseline"]["results"] is None
    with queue.sessions() as session:
        assert session.scalar(select(ModelArtifact)) is None
    assert (
        client.post(
            f"/api/v1/projects/{project_id}/establish", json={"snapshot_id": p["baseline"]["id"]}
        ).status_code
        == 409
    )


def test_training_finalization_is_fenced_and_atomic(setup_client):
    client, queue, store, settings = setup_client
    project_id, p = validated(setup_client)
    client.put(
        f"/api/v1/projects/{project_id}/configuration",
        json=choice(p, classifier="logistic_regression"),
    )
    client.post(f"/api/v1/projects/{project_id}/train")
    job = queue.claim()
    persist, prefix, failed = training_result(queue, job, store, settings)
    assert not failed
    with queue.sessions.begin() as session:
        session.execute(update(Job).where(Job.id == job.id).values(owner_token=uuid4()))
    with pytest.raises(OwnershipLost):
        queue.finalize(job, result=persist)
    with queue.sessions() as session:
        assert session.scalar(select(ModelArtifact)) is None
        assert session.scalar(select(BaselineSnapshot)).status == "TRAINING"
    store.delete_prefix(prefix)


def test_discard_cleanup_failure_cannot_delete_new_committed_upload(setup_client):
    client, queue, store, settings = setup_client
    project_id, p, _ = trained(setup_client)
    content = (
        "amount,segment,outcome\n" + "".join(f"{i},group{i % 3},class{i % 2}\n" for i in range(240))
    ).encode()
    with patch.object(
        type(store), "delete_prefix", side_effect=OSError("controlled failure")
    ) as cleanup:
        response = client.post(
            f"/api/v1/projects/{project_id}/baseline?discard_results=true",
            content=content,
            headers={"Content-Type": "text/csv"},
        )
    cleanup.assert_called_once()
    assert response.status_code == 202, response.text
    assert run_once(queue, uuid4(), 1, store, settings)
    current = client.get(f"/api/v1/projects/{project_id}").json()
    assert current["dataset"]["status"] == "READY" and current["baseline"] is None
    assert (
        client.post(
            f"/api/v1/projects/{project_id}/establish", json={"snapshot_id": p["baseline"]["id"]}
        ).status_code
        == 409
    )
    assert client.delete(f"/api/v1/projects/{project_id}").status_code == 204
    assert not (store.root / "projects" / project_id).exists()
