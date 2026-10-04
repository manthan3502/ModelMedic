from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map = {str: Text()}


class Identity:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Project(Identity, Base):
    __tablename__ = "projects"
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None]
    state: Mapped[str] = mapped_column(String(32), server_default="DRAFT")


class Dataset(Identity, Base):
    __tablename__ = "datasets"
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16))
    original_object_key: Mapped[str]
    canonical_object_key: Mapped[str | None]


class BaselineSnapshot(Identity, Base):
    __tablename__ = "baseline_snapshots"
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(32))
    config_fingerprint: Mapped[str]


class ModelArtifact(Identity, Base):
    __tablename__ = "model_artifacts"
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("baseline_snapshots.id", ondelete="CASCADE")
    )
    storage_key: Mapped[str] = mapped_column(unique=True)
    sha256: Mapped[str] = mapped_column(String(64))


class MonitoringRun(Identity, Base):
    __tablename__ = "monitoring_runs"
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    dataset_id: Mapped[UUID | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"))
    baseline_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("baseline_snapshots.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(32), server_default="UPLOADED")


class Job(Identity, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("state IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED')", name="job_state"),
        CheckConstraint("attempt >= 0 AND max_attempts BETWEEN 1 AND 2", name="job_attempts"),
        Index(
            "uq_active_job",
            "job_type",
            "target_type",
            "target_id",
            unique=True,
            postgresql_where=text("state IN ('QUEUED', 'RUNNING')"),
        ),
        Index("ix_queue", "state", "created_at"),
    )
    job_type: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[UUID]
    project_id: Mapped[UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    state: Mapped[str] = mapped_column(String(16), server_default="QUEUED")
    stage: Mapped[str] = mapped_column(String(64), server_default="WAITING")
    attempt: Mapped[int] = mapped_column(server_default="0")
    max_attempts: Mapped[int] = mapped_column(server_default="2")
    owner_token: Mapped[UUID | None]
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None]


class WorkerStatus(Base):
    __tablename__ = "worker_status"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32))
