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
    setup: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    target_feature_id: Mapped[str | None] = mapped_column(String(16))
    positive_class: Mapped[str | None]
    classifier: Mapped[str | None] = mapped_column(String(32))
    class_weight_mode: Mapped[str | None] = mapped_column(String(16))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deletion_pending: Mapped[bool] = mapped_column(server_default="false")

    @property
    def configuration(self) -> dict[str, Any]:
        if not self.setup:
            return {}
        return {
            **self.setup,
            "target_id": self.target_feature_id,
            "positive_class": self.positive_class,
            "classifier": self.classifier,
            "weighting": self.class_weight_mode,
        }

    @configuration.setter
    def configuration(self, value: dict[str, Any]) -> None:
        self.target_feature_id = value.get("target_id")
        self.positive_class = value.get("positive_class")
        self.classifier = value.get("classifier")
        self.class_weight_mode = value.get("weighting")
        self.setup = {
            k: v
            for k, v in value.items()
            if k not in {"target_id", "positive_class", "classifier", "weighting"}
        }


class Dataset(Identity, Base):
    __tablename__ = "datasets"
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16))
    original_object_key: Mapped[str]
    canonical_object_key: Mapped[str | None]
    status: Mapped[str] = mapped_column(String(32), server_default="UPLOADED")
    canonical_sha256: Mapped[str | None] = mapped_column(String(64))
    canonical_schema_version: Mapped[str | None] = mapped_column(String(32))
    profile: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    validation_report: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    original_sha256: Mapped[str | None] = mapped_column(String(64))
    uploaded_bytes: Mapped[int | None]


class BaselineSnapshot(Identity, Base):
    __tablename__ = "baseline_snapshots"
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(32))
    config_fingerprint: Mapped[str]
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    development_count: Mapped[int | None]
    heldout_count: Mapped[int | None]
    split_seed: Mapped[int | None]
    split_membership_object_key: Mapped[str | None]
    heldout_reference_object_key: Mapped[str | None]
    artifact_prefix: Mapped[str | None]
    methodology_version: Mapped[str | None]
    code_version: Mapped[str | None]
    results: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_message: Mapped[str | None]
    established_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ModelArtifact(Identity, Base):
    __tablename__ = "model_artifacts"
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("baseline_snapshots.id", ondelete="CASCADE")
    )
    storage_key: Mapped[str] = mapped_column(unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    environment_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")


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
