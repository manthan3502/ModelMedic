from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select, text, update

from backend.app.core.config import Settings
from backend.app.db.models import Base, Job, WorkerStatus
from backend.app.db.session import check_schema
from backend.app.domain.jobs import DuplicateActiveJob, OwnershipLost
from backend.app.jobs.worker import main as worker_main
from backend.app.jobs.worker import run_once
from backend.app.main import create_app
from backend.app.services.queue import Queue

pytestmark = pytest.mark.integration


def expire(sessions, job):
    with sessions.begin() as session:
        session.execute(
            update(Job)
            .where(Job.id == job.id)
            .values(lease_expires_at=func.now() - timedelta(seconds=1))
        )


def test_empty_database_migrated_and_metadata_matches(db):
    engine, _ = db
    check_schema(engine)
    assert set(Base.metadata.tables) <= set(inspect(engine).get_table_names())
    with engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        assert differences == []


def test_readiness_and_job_observation(database_url, db):
    _, sessions = db
    queue = Queue(sessions)
    job = queue.enqueue("M0_DUMMY", "INTERNAL", uuid4())
    with TestClient(create_app(Settings(database_url=database_url))) as client:
        assert client.get("/api/v1/health/ready").status_code == 200
        assert client.get(f"/api/v1/jobs/{job.id}").json()["state"] == "QUEUED"
        assert run_once(queue, uuid4(), 1)
        result = client.get(f"/api/v1/jobs/{job.id}").json()
        assert result["state"] == "SUCCEEDED"
        assert result["attempt"] == 1
        assert "params" not in result and "owner_token" not in result
        assert client.get("/api/v1/health/worker").json()["recent"] is True


def test_incompatible_schema_blocks_readiness_and_worker(database_url, db):
    engine, _ = db
    try:
        with engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = 'unsupported'"))
        with TestClient(create_app(Settings(database_url=database_url))) as client:
            assert client.get("/api/v1/health/ready").status_code == 503
        with pytest.raises(RuntimeError, match="Unsupported database schema"):
            worker_main()
    finally:
        with engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = '0001_m0'"))


def test_duplicate_active_job_and_completed_target_can_be_requeued(db):
    _, sessions = db
    queue = Queue(sessions)
    target = uuid4()
    queue.enqueue("M0_DUMMY", "INTERNAL", target)
    with pytest.raises(DuplicateActiveJob):
        queue.enqueue("M0_DUMMY", "INTERNAL", target)
    claimed = queue.claim()
    with pytest.raises(DuplicateActiveJob):
        queue.enqueue("M0_DUMMY", "INTERNAL", target)
    queue.finalize(claimed)
    assert queue.enqueue("M0_DUMMY", "INTERNAL", target).id != claimed.id


def test_claim_skips_locked_row_and_commits_before_computation(db):
    _, sessions = db
    queue = Queue(sessions)
    first = queue.enqueue("M0_DUMMY", "INTERNAL", uuid4())
    second = queue.enqueue("M0_DUMMY", "INTERNAL", uuid4())
    with sessions.begin() as blocker:
        blocker.scalar(select(Job).where(Job.id == first.id).with_for_update())
        claimed = queue.claim()
        assert claimed.id == second.id
        # A different transaction can immediately lock the claimed row.
        with sessions.begin() as observer:
            visible = observer.scalar(
                select(Job).where(Job.id == second.id).with_for_update(nowait=True)
            )
            assert visible.state == "RUNNING"
    assert queue.claim().id == first.id


def test_concurrent_workers_cannot_claim_same_job(db):
    _, sessions = db
    queue = Queue(sessions)
    queue.enqueue("M0_DUMMY", "INTERNAL", uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: queue.claim(), range(2)))
    assert sum(job is not None for job in results) == 1


def test_stale_retry_and_exhaustion(db):
    _, sessions = db
    queue = Queue(sessions)
    created = queue.enqueue("M0_DUMMY", "INTERNAL", uuid4())
    first = queue.claim()
    impostor = Job(id=first.id, owner_token=uuid4(), attempt=first.attempt)
    with pytest.raises(OwnershipLost):
        queue.finalize(impostor)
    expire(sessions, first)
    assert queue.recover_stale() == 1
    second = queue.claim()
    assert second.attempt == 2 and second.owner_token != first.owner_token
    expire(sessions, second)
    assert queue.recover_stale() == 1
    assert queue.claim() is None
    with sessions() as session:
        job = session.get(Job, created.id)
        assert job.state == "FAILED" and job.error_code == "WORKER_LOST"
        assert job.finished_at is not None


def test_fencing_blocks_expired_replaced_and_double_finalization(db):
    _, sessions = db
    queue = Queue(sessions)
    queue.enqueue("M0_DUMMY", "INTERNAL", uuid4())
    first = queue.claim()
    expire(sessions, first)
    with pytest.raises(OwnershipLost):
        queue.finalize(first)
    with pytest.raises(OwnershipLost):
        queue.heartbeat(uuid4(), first)
    queue.recover_stale()
    second = queue.claim()
    with pytest.raises(OwnershipLost):
        queue.finalize(first)
    queue.finalize(second)
    with pytest.raises(OwnershipLost):
        queue.finalize(second)


def test_worker_heartbeat_is_independent_of_jobs(db):
    _, sessions = db
    worker_id = uuid4()
    assert not run_once(Queue(sessions), worker_id, 1)
    with sessions() as session:
        assert session.get(WorkerStatus, worker_id).status == "IDLE"
        assert session.scalar(select(func.count()).select_from(Job)) == 0


def test_worker_renews_lease_during_computation(db, monkeypatch):
    _, sessions = db
    queue = Queue(sessions, lease_seconds=3)
    job = queue.enqueue("M0_DUMMY", "INTERNAL", uuid4())
    heartbeat_seen = Event()
    original = queue.heartbeat
    pulses = []

    def heartbeat(worker_id, active=None):
        original(worker_id, active)
        if active:
            pulses.append(active.id)
            if len(pulses) >= 2:
                heartbeat_seen.set()

    def computation(active):
        assert heartbeat_seen.wait(5), "No periodic heartbeat while computing"

    monkeypatch.setattr(queue, "heartbeat", heartbeat)
    monkeypatch.setattr("backend.app.jobs.worker.execute_dummy", computation)
    assert run_once(queue, uuid4(), 0.1)
    with sessions() as session:
        assert session.get(Job, job.id).state == "SUCCEEDED"


def test_controlled_failure_is_sanitized_and_not_retried(db):
    _, sessions = db
    queue = Queue(sessions)
    job = queue.enqueue("M0_DUMMY", "INTERNAL", uuid4(), {"fail": True})
    run_once(queue, uuid4(), 1)
    with sessions() as session:
        saved = session.get(Job, job.id)
        assert saved.state == "FAILED" and saved.attempt == 1
        assert saved.error_code == "JOB_FAILED"
        assert "Traceback" not in saved.error_message
    assert queue.claim() is None
