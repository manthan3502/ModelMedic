"""Real-stack demo denial, scoped reads, worker omission and immutable facts."""

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from sqlalchemy import func, select

from backend.app.core.config import Settings
from backend.app.db.models import Job, MonitoringRun, Project, RunReport, SliceAnalysis
from backend.app.main import create_app
from backend.app.services.demo import REGISTRY_KEY
from backend.app.storage.factory import artifact_store
from scripts.seed_demo import digest, verify
from scripts.smoke_m3 import ROOT, run_call


def main():
    settings = Settings()
    store = artifact_store(settings)
    seed = json.loads(store.get(REGISTRY_KEY))
    engine, sessions = create_db_for_checks(settings)
    tables = (Project, MonitoringRun, Job, SliceAnalysis, RunReport)
    with sessions() as session:
        before = [session.scalar(select(func.count()).select_from(t)) for t in tables]
    assert run_call("/runtime")["deployment_mode"] == "DEMO_MODE"
    assert run_call("/health/ready")["status"] == "ready"
    assert run_call("/health/worker")["status"] == "NOT_REQUIRED"
    verify(store)
    app = create_app(settings)
    tested = 0
    paths = app.openapi()["paths"]
    assert len(paths) >= 30
    for path in paths:
        for key, ids in (
            ("project_id", "projects"),
            ("run_id", "runs"),
            ("job_id", "jobs"),
            ("slice_id", "slices"),
        ):
            path = path.replace("{" + key + "}", seed[ids][0])
        path = path.replace("{section}", "summary").replace("{feature_id}", "f000")
        for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"):
            try:
                with urlopen(
                    Request(ROOT + path.removeprefix("/api/v1"), method=method), timeout=10
                ):
                    raise AssertionError((path, method, "mutation admitted"))
            except HTTPError as exc:
                assert exc.code == 403, (path, method, exc.code)
                assert exc.headers["X-Request-ID"]
            tested += 1
    for path in (
        "/future-export",
        "/projects/" + str(uuid4()),
        "/runs/" + str(uuid4()) + "/summary",
    ):
        try:
            run_call(path)
        except HTTPError as exc:
            assert exc.code in {403, 404}
        else:
            raise AssertionError("Unregistered demo data admitted")
    for rid in seed["runs"]:
        for endpoint in (
            "features/f000",
            "predictions",
            "confidence",
            "metrics",
            "calibration",
            "errors",
            "slices",
            "report",
            "presentation",
        ):
            assert run_call(f"/runs/{rid}/{endpoint}")
    with sessions() as session:
        assert before == [session.scalar(select(func.count()).select_from(t)) for t in tables]
    verify(store)
    assert digest(run_call(f"/runs/{seed['runs'][0]}/summary")) == seed["summary_hashes"][0]
    engine.dispose()
    print(
        f"PASS: real demo {tested} denied method/route pairs; "
        "safe GETs; no worker; no DB/result changes",
        flush=True,
    )


def create_db_for_checks(settings):
    from backend.app.db.session import create_db

    return create_db(settings)


if __name__ == "__main__":
    main()
