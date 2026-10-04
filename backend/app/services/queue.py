from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db.models import Job, WorkerStatus
from backend.app.domain.jobs import DuplicateActiveJob, JobState, OwnershipLost


class Queue:
    def __init__(self, sessions: sessionmaker[Session], lease_seconds: int = 30):
        self.sessions = sessions
        self.lease_seconds = lease_seconds

    def enqueue(
        self, job_type: str, target_type: str, target_id: UUID, params: dict[str, Any] | None = None
    ) -> Job:
        job = Job(
            job_type=job_type, target_type=target_type, target_id=target_id, params=params or {}
        )
        try:
            with self.sessions.begin() as session:
                session.add(job)
                session.flush()
        except IntegrityError as exc:
            if getattr(getattr(exc.orig, "diag", None), "constraint_name", None) == "uq_active_job":
                raise DuplicateActiveJob from None
            raise
        return job

    def recover_stale(self) -> int:
        with self.sessions.begin() as session:
            jobs = session.scalars(
                select(Job)
                .where(
                    Job.state == JobState.RUNNING, Job.lease_expires_at <= func.clock_timestamp()
                )
                .with_for_update(skip_locked=True)
            ).all()
            for job in jobs:
                job.owner_token = None
                job.lease_expires_at = None
                if job.attempt < job.max_attempts:
                    job.state, job.stage = JobState.QUEUED, "RECOVERED"
                else:
                    job.state, job.stage = JobState.FAILED, "FAILED"
                    job.error_code = "WORKER_LOST"
                    job.error_message = "Worker lease expired; retry limit reached."
                    job.finished_at = session.scalar(select(func.now()))
            return len(jobs)

    def claim(self) -> Job | None:
        with self.sessions.begin() as session:
            job = session.scalar(
                select(Job)
                .where(Job.state == JobState.QUEUED, Job.attempt < Job.max_attempts)
                .order_by(Job.created_at, Job.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if job is None:
                return None
            now = session.scalar(select(func.now()))
            assert now is not None
            job.state, job.stage = JobState.RUNNING, "EXECUTING"
            job.attempt += 1
            job.owner_token = uuid4()
            job.started_at = now
            job.heartbeat_at = now
            job.lease_expires_at = now + timedelta(seconds=self.lease_seconds)
            session.flush()
            return job  # Context commits before the caller can compute.

    def heartbeat(self, worker_id: UUID, job: Job | None = None) -> None:
        with self.sessions.begin() as session:
            statement = insert(WorkerStatus).values(
                id=worker_id, heartbeat_at=func.now(), status="BUSY" if job else "IDLE"
            )
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=[WorkerStatus.id],
                    set_={"heartbeat_at": func.now(), "status": "BUSY" if job else "IDLE"},
                )
            )
            if job:
                owned = session.scalar(
                    update(Job)
                    .where(
                        Job.id == job.id,
                        Job.owner_token == job.owner_token,
                        Job.attempt == job.attempt,
                        Job.state == JobState.RUNNING,
                        Job.lease_expires_at > func.clock_timestamp(),
                    )
                    .values(
                        heartbeat_at=func.now(),
                        lease_expires_at=func.clock_timestamp()
                        + timedelta(seconds=self.lease_seconds),
                    )
                    .returning(Job.id)
                )
                if owned is None:
                    raise OwnershipLost

    def finalize(self, job: Job, *, failed: bool = False) -> None:
        with self.sessions.begin() as session:
            owned = session.scalar(
                update(Job)
                .where(
                    Job.id == job.id,
                    Job.state == JobState.RUNNING,
                    Job.owner_token == job.owner_token,
                    Job.attempt == job.attempt,
                    Job.lease_expires_at > func.clock_timestamp(),
                )
                .values(
                    state=JobState.FAILED if failed else JobState.SUCCEEDED,
                    stage="FAILED" if failed else "COMPLETE",
                    finished_at=func.now(),
                    lease_expires_at=None,
                    owner_token=None,
                    error_code="JOB_FAILED" if failed else None,
                    error_message="Internal job failed; inspect worker status." if failed else None,
                )
                .returning(Job.id)
            )
            if owned is None:
                raise OwnershipLost
            # Future result/state writes belong in this same fenced transaction.
