import logging
import signal
from threading import Event, Thread
from uuid import UUID, uuid4

from backend.app.core.config import Settings
from backend.app.core.logging import configure_logging
from backend.app.db.models import Job
from backend.app.db.session import check_schema, create_db
from backend.app.domain.jobs import OwnershipLost
from backend.app.services.queue import Queue

logger = logging.getLogger("modelmedic")


def execute_dummy(job: Job) -> None:
    if job.job_type != "M0_DUMMY" or job.params.get("fail"):
        raise ValueError("Controlled internal job failure")
    # Intentionally no scientific behavior, artifacts or application mutations.


def run_once(queue: Queue, worker_id: UUID, heartbeat_seconds: float) -> bool:
    queue.heartbeat(worker_id)
    queue.recover_stale()
    job = queue.claim()
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
    try:
        queue.heartbeat(worker_id, job)
        execute_dummy(job)
    except Exception:
        failed = True
        logger.error("job_execution_failed", extra={"job_id": str(job.id)})
    finally:
        stop_heartbeat.set()
        thread.join()
    if ownership_lost.is_set():
        logger.warning("job_ownership_lost", extra={"job_id": str(job.id)})
        return True
    try:
        queue.finalize(job, failed=failed)
        logger.info("job_finalized", extra={"job_id": str(job.id)})
    except OwnershipLost:
        logger.warning("job_ownership_lost", extra={"job_id": str(job.id)})
    return True


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
            run_once(queue, worker_id, settings.heartbeat_seconds)
            stop.wait(settings.poll_seconds)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
