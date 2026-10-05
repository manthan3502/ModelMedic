"""Deterministic synthetic source data; all saved science uses real API/worker jobs.

Run create in a local Full Mode Compose test container. The private registry is
published only after all jobs and stored reports are complete. No source CSV or
result artifact belongs in Git. Regenerate explicitly after method version changes.
"""

import argparse
import csv
import io
import json
import math
import random
import time
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select

from backend.app.core.config import Settings
from backend.app.db.models import Job, Project
from backend.app.db.session import create_db
from backend.app.services.demo import REGISTRY_KEY, VERSIONS, registry
from backend.app.storage.local import LocalArtifactStore
from scripts.smoke_m1 import call
from scripts.smoke_m2 import wait
from scripts.smoke_m3 import run_call, wait_run

NAME = "Synthetic reliability lab"


def source(period: int = 0, labels: bool = True) -> bytes:
    """Independent generated observations, no personal/medical/financial records."""
    rng = random.Random(4200 + period)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["signal", "context", "segment"] + (["outcome"] if labels else []))
    for i in range(1500 if period == 0 else 360):
        signal = rng.gauss(0 if not period else 0.55 * period, 1)
        context = rng.gauss(0, 1.2)
        segment = ("North", "South", "West")[i % 3]
        probability = 1 / (
            1 + math.exp(-(signal + 0.45 * context + (0.3 if segment == "North" else -0.2)))
        )
        # Current period 3 has a deliberately different observed relationship.
        outcome = (
            "event" if rng.random() < (1 - probability if period == 3 else probability) else "none"
        )
        writer.writerow(
            [
                "" if period and i % 23 == 0 else f"{signal:.6f}",
                f"{context:.6f}",
                "East" if period and i % 11 == 0 else segment,
            ]
            + ([outcome] if labels else [])
        )
    return stream.getvalue().encode()


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def create(store):
    assert run_call("/runtime")["deployment_mode"] == "FULL_MODE", "Seed only in Full Mode"
    assert not store.exists(REGISTRY_KEY), "Seed exists; verify or explicitly regenerate it"
    p = call(
        method="POST",
        body={
            "name": NAME,
            "description": (
                "Synthetic demo data · generated observations for inspecting independent "
                "reliability signals. No real people or records."
            ),
        },
    )
    pid = p["id"]
    sources = [source()] + [source(i, i != 2) for i in range(1, 4)]
    run_call(f"/projects/{pid}/baseline", "POST", csv=iter([sources[0][:120], sources[0][120:]]))
    p = wait("/" + pid, lambda p: p["dataset"]["status"] == "READY")
    call(
        "/" + pid + "/configuration",
        "PUT",
        {
            "dataset_id": p["dataset"]["id"],
            "target_id": "f003",
            "positive_class": "event",
            "features": [
                {"feature_id": "f000", "type": "numeric"},
                {"feature_id": "f001", "type": "numeric"},
                {"feature_id": "f002", "type": "categorical"},
            ],
            "classifier": "logistic_regression",
            "weighting": "standard",
        },
    )
    call("/" + pid + "/train", "POST")
    p = wait("/" + pid, lambda p: p["job"]["state"] == "SUCCEEDED")
    call("/" + pid + "/establish", "POST", {"snapshot_id": p["baseline"]["id"]})
    runs, slices = [], []
    for i in range(1, 4):
        mode = "A" if i == 2 else "B"
        run = call(
            "/" + pid + "/runs",
            "POST",
            {
                "name": f"Period {i} · Mode {mode}",
                "monitoring_date": f"2026-09-0{i}",
                "notes": (
                    "Synthetic demo data. Independent generated observations; "
                    "changes are deliberately introduced for education."
                ),
            },
        )
        rid = run["id"]
        runs.append(rid)
        run_call(f"/runs/{rid}/upload", "POST", csv=iter([sources[i][:120], sources[i][120:]]))
        assert wait_run(rid, "READY")["mode"] == mode
        run_call(f"/runs/{rid}/analyze", "POST")
        wait_run(rid, "ANALYZED")
        if mode == "B":
            analysis = run_call(f"/runs/{rid}/slices", "POST", {"feature_id": "f002"})
            for _ in range(240):
                analysis = run_call(f"/runs/{rid}/slices/{analysis['id']}")
                assert analysis["status"] != "FAILED", analysis.get("job")
                if analysis["status"] == "READY":
                    break
                time.sleep(0.25)
            else:
                raise AssertionError("Demo slice worker timeout")
            slices.append(analysis["id"])
        run_call(f"/runs/{rid}/report")
    engine, sessions = create_db(Settings())
    with sessions() as session:
        jobs = list(session.scalars(select(Job).where(Job.project_id == UUID(pid))))
        assert jobs and all(j.state == "SUCCEEDED" for j in jobs)
        job_ids = [str(j.id) for j in jobs]
    engine.dispose()
    data = {
        "versions": VERSIONS,
        "synthetic_only": True,
        "projects": [pid],
        "runs": runs,
        "jobs": job_ids,
        "slices": slices,
        "source_sha256": [sha256(s).hexdigest() for s in sources],
        "summary_hashes": [digest(run_call(f"/runs/{r}/summary")) for r in runs],
        "report_hashes": [digest(run_call(f"/runs/{r}/report")["report"]) for r in runs],
    }
    store.put(REGISTRY_KEY, json.dumps(data, sort_keys=True).encode())
    verify(store)
    print(
        f"PASS: real-pipeline synthetic demo seed {pid}; B-A-B, slices, trends, reports", flush=True
    )


def verify(store):
    data = registry(store)
    assert call("/" + data["projects"][0])["baseline"]["status"] == "ESTABLISHED"
    assert data["source_sha256"] == [sha256(source()).hexdigest()] + [
        sha256(source(i, i != 2)).hexdigest() for i in range(1, 4)
    ]
    for i, rid in enumerate(data["runs"]):
        assert digest(run_call(f"/runs/{rid}/summary")) == data["summary_hashes"][i]
        assert digest(run_call(f"/runs/{rid}/report")["report"]) == data["report_hashes"][i]
    history = run_call(
        f"/projects/{data['projects'][0]}/trends?group=performance&signal=balanced_accuracy"
    )
    assert [p["mode"] for p in history["points"]] == ["B", "A", "B"]
    assert history["points"][1]["value"] is None
    print("PASS: seed source reproducibility / immutable outputs / baseline / history", flush=True)


def regenerate(store):
    assert run_call("/runtime")["deployment_mode"] == "FULL_MODE"
    # Use the old operator-owned registry even when its version is obsolete.
    data = json.loads(store.get(REGISTRY_KEY))
    assert data["synthetic_only"] is True and len(data["projects"]) == 1
    pid = str(UUID(data["projects"][0]))
    assert call("/" + pid)["name"] == NAME
    for rid in data["runs"]:
        assert run_call("/runs/" + rid)["project_id"] == pid
        run_call("/runs/" + rid, "DELETE")
    engine, sessions = create_db(Settings())
    with sessions.begin() as session:
        project = session.get(Project, UUID(pid))
        assert project and project.name == NAME
        session.delete(project)
    engine.dispose()
    store.delete_prefix("projects/" + pid)
    store.delete(REGISTRY_KEY)
    create(store)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["create", "verify", "ensure", "regenerate"])
    action = parser.parse_args().action
    store = LocalArtifactStore(Settings().artifact_root)
    {
        "create": create,
        "verify": verify,
        "ensure": (verify if store.exists(REGISTRY_KEY) else create),
        "regenerate": regenerate,
    }[action](store)
