"""Run inside the API container after starting all four services."""

import json
import time
from urllib.request import urlopen
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from backend.app.core.config import Settings
from backend.app.db.models import Job
from backend.app.db.session import create_db
from backend.app.services.queue import Queue


def read(url):
    with urlopen(url, timeout=5) as response:
        assert response.status == 200
        return json.load(response)


def main():
    settings = Settings()
    engine, sessions = create_db(settings)
    queue = Queue(sessions)
    assert read("http://api:8000/api/v1/health/live")["status"] == "alive"
    assert read("http://api:8000/api/v1/health/ready")["status"] == "ready"
    assert read("http://frontend:5173/api/v1/health/ready")["status"] == "ready"
    with urlopen("http://frontend:5173", timeout=5) as response:
        assert b"ModelMedic" in response.read()
    for _ in range(30):
        if read("http://api:8000/api/v1/health/worker")["recent"]:
            break
        time.sleep(1)
    else:
        raise AssertionError("Worker heartbeat not recent")
    job = queue.enqueue("M0_DUMMY", "INTERNAL", uuid4())
    for _ in range(30):
        result = read(f"http://api:8000/api/v1/jobs/{job.id}")
        if result["state"] == "SUCCEEDED":
            break
        assert result["state"] != "FAILED", result
        time.sleep(1)
    else:
        raise AssertionError("Dummy job did not complete")
    # Uncommitted fixture is invisible to the live worker; test the database constraint.
    with sessions.begin() as session:
        target = uuid4()
        session.add(Job(job_type="M0_DUMMY", target_type="INTERNAL", target_id=target))
        session.flush()
        try:
            with session.begin_nested():
                session.add(Job(job_type="M0_DUMMY", target_type="INTERNAL", target_id=target))
                session.flush()
        except IntegrityError as exc:
            assert exc.orig.diag.constraint_name == "uq_active_job"
        else:
            raise AssertionError("Duplicate active job accepted")
    engine.dispose()
    print(
        "PASS: services, frontend-to-API, worker heartbeat, "
        "dummy success via API, duplicate rejection"
    )


if __name__ == "__main__":
    main()
