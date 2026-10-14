import logging
import multiprocessing
import signal
import time
from threading import Event, Thread
from typing import Any
from uuid import UUID, uuid4

from backend.app.core.config import Settings
from backend.app.core.logging import configure_logging
from backend.app.db.models import Job
from backend.app.db.session import check_schema, create_db
from backend.app.domain.jobs import OwnershipLost
from backend.app.jobs.datasets import validation_result
from backend.app.jobs.monitoring import analysis_result
from backend.app.jobs.monitoring import validation_result as current_validation
from backend.app.jobs.slices import slice_result
from backend.app.jobs.training import training_result
from backend.app.services.queue import Queue
from backend.app.storage.base import ArtifactStore
from backend.app.storage.factory import artifact_store

logger = logging.getLogger("modelmedic")


def execute_dummy(job: Job) -> None:
    if job.job_type != "M0_DUMMY" or job.params.get("fail"):
        raise ValueError("Controlled internal job failure")
    # Intentionally no scientific behavior, artifacts or application mutations.


def run_once(
    queue: Queue,
    worker_id: UUID,
    heartbeat_seconds: float,
    store: ArtifactStore | None = None,
    settings: Settings | None = None,
    claimed_job: Job | None = None,
) -> bool:
    queue.heartbeat(worker_id)
    if claimed_job is None:
        queue.recover_stale()
    job = claimed_job if claimed_job is not None else queue.claim()
    if job is None:
        return False
    stop_heartbeat = Event()
    ownership_lost = Event()

    def pulse() -> None:
        while not stop_heartbeat.wait(heartbeat_seconds):
            try:
                queue.heartbeat(worker_id, job)
            except Exception:
                ownership_lost.set()
                return

    thread = Thread(target=pulse, daemon=True)
    thread.start()
    failed = False
    result = None
    canonical_key = None
    training_prefix = None
    try:
        queue.heartbeat(worker_id, job)
        if job.job_type == "DATASET_VALIDATE" and store and settings:
            if job.target_type == "RUN":
                result, canonical_key = current_validation(queue, job, store, settings)
            else:
                result, canonical_key = validation_result(queue, job, store, settings)
        elif job.job_type == "BASELINE_TRAIN" and store and settings:
            result, training_prefix, failed = training_result(queue, job, store, settings)
        elif job.job_type == "MONITORING_ANALYZE" and store and settings:
            result, training_prefix, failed = analysis_result(queue, job, store, settings)
        elif job.job_type == "SLICE_ANALYZE" and store and settings:
            result, failed = slice_result(queue, job, store, settings)
        else:
            execute_dummy(job)
    except Exception:
        failed = True
        logger.error("job_execution_failed", extra={"job_id": str(job.id)})
    finally:
        stop_heartbeat.set()
        thread.join()
    if ownership_lost.is_set():
        if store and training_prefix:
            store.delete_prefix(training_prefix)
        if store and canonical_key:
            store.delete(canonical_key)
        logger.warning("job_ownership_lost", extra={"job_id": str(job.id)})
        return True
    try:
        queue.finalize(job, failed=failed, result=result)
        logger.info("job_finalized", extra={"job_id": str(job.id)})
    except OwnershipLost:
        if store and training_prefix:
            store.delete_prefix(training_prefix)
        if store and canonical_key:
            store.delete(canonical_key)
        logger.warning("job_ownership_lost", extra={"job_id": str(job.id)})
    return True


def execute_claimed(
    settings_data: dict[str, Any],
    worker_id: UUID,
    job_id: UUID,
    owner_token: UUID | None,
    attempt: int,
) -> None:
    """A fresh process owns computation; never share SQLAlchemy connections across processes."""
    settings = Settings(**settings_data)
    engine, sessions = create_db(settings)
    try:
        with sessions() as session:
            job = session.get(Job, job_id)
            if not job or job.owner_token != owner_token or job.attempt != attempt:
                return
        run_once(
            Queue(sessions, settings.lease_seconds),
            worker_id,
            settings.heartbeat_seconds,
            artifact_store(settings),
            settings,
            claimed_job=job,
        )
    finally:
        engine.dispose()


def supervise(queue: Queue, settings: Settings, worker_id: UUID, job: Job, stop: Event) -> None:
    """Kill computation at its wall-clock budget; PostgreSQL fencing still governs publication.

    Shutdown/crash leaves an expiring lease for the existing retry policy. A timeout
    is a deterministic failure, not a loop of expensive automatic retries. Unpublished
    attempt objects stay private and are removed on retry/discard/project deletion.
    """
    child = multiprocessing.get_context("spawn").Process(
        target=execute_claimed,
        args=(settings.model_dump(), worker_id, job.id, job.owner_token, job.attempt),
    )
    queue.heartbeat(worker_id, job)
    child.start()
    deadline = time.monotonic() + settings.job_timeout_seconds
    next_heartbeat = time.monotonic() + settings.heartbeat_seconds
    timed_out = False
    try:
        while child.is_alive() and not stop.wait(0.1):
            if time.monotonic() >= deadline:
                timed_out = True
                break
            if time.monotonic() >= next_heartbeat:
                queue.heartbeat(worker_id, job)
                next_heartbeat = time.monotonic() + settings.heartbeat_seconds
    except OwnershipLost:
        stop_computation(child)
        logger.warning("job_ownership_lost", extra={"job_id": str(job.id)})
        return
    finally:
        if child.is_alive():
            stop_computation(child)
        child.join()
    if stop.is_set():
        return  # Recovery after restart uses max attempts and a new ownership token.
    if timed_out or child.exitcode != 0:

        def failure(session: Any) -> None:
            owned = session.get(Job, job.id)
            assert owned
            owned.error_code = "JOB_TIMEOUT" if timed_out else "WORKER_PROCESS_FAILED"
            owned.error_message = (
                "Job exceeded the configured execution budget. No final results were published."
                if timed_out
                else "Worker process stopped. No final results were published."
            )

        try:
            queue.finalize(job, failed=True, result=failure)
        except OwnershipLost:
            pass  # A completed/replaced worker cannot be overwritten by the supervisor.


def stop_computation(child: Any) -> None:
    child.terminate()
    child.join(timeout=5)
    if child.is_alive():
        child.kill()
        child.join()


def main() -> None:
    configure_logging()
    settings = Settings()  # type: ignore[call-arg]
    engine, sessions = create_db(settings)
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    try:
        check_schema(engine)  # Refuse unsupported schemas; never migrate on startup.
        if settings.deployment_mode == "demo":
            raise RuntimeError("Demo mode does not run the worker")
        queue = Queue(sessions, settings.lease_seconds)
        worker_id = uuid4()
        logger.info("worker_started")
        while not stop.is_set():
            queue.heartbeat(worker_id)
            queue.recover_stale()
            job = queue.claim()
            if job:
                supervise(queue, settings, worker_id, job, stop)
            stop.wait(settings.poll_seconds)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
