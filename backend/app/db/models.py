from datetime import date, datetime
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
    __table_args__ = (Index("ix_run_history", "project_id", "monitoring_date", "created_at", "id"),)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    dataset_id: Mapped[UUID | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"))
    baseline_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("baseline_snapshots.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(32), server_default="UPLOADED")
    monitoring_date: Mapped[date]
    notes: Mapped[str | None]
    mode: Mapped[str | None] = mapped_column(String(1))
    row_count: Mapped[int | None]
    methodology_version: Mapped[str | None] = mapped_column(String(32))
    code_version: Mapped[str | None] = mapped_column(String(40))
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deletion_pending: Mapped[bool] = mapped_column(server_default="false")
    results: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    result_object_key: Mapped[str | None]
    result_sha256: Mapped[str | None] = mapped_column(String(64))


class RunFeatureResult(Base):
    __tablename__ = "run_feature_results"
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("monitoring_runs.id", ondelete="CASCADE"), primary_key=True
    )
    feature_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    feature_name: Mapped[str]
    feature_type: Mapped[str] = mapped_column(String(16))
    distribution_status: Mapped[str] = mapped_column(String(32))
    missingness_status: Mapped[str] = mapped_column(String(32))
    raw_p_value: Mapped[float | None]
    adjusted_p_value: Mapped[float | None]
    missing_p_value: Mapped[float | None]
    missing_adjusted_p_value: Mapped[float | None]
    baseline_valid_n: Mapped[int]
    current_valid_n: Mapped[int]
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB)


class RunMetric(Base):
    __tablename__ = "run_metrics"
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("monitoring_runs.id", ondelete="CASCADE"), primary_key=True
    )
    scope: Mapped[str] = mapped_column(String(16), primary_key=True)
    class_label: Mapped[str] = mapped_column(primary_key=True)
    metric_name: Mapped[str] = mapped_column(String(32), primary_key=True)
    baseline_value: Mapped[float | None]
    current_value: Mapped[float | None]
    delta: Mapped[float | None]
    baseline_support: Mapped[int]
    current_support: Mapped[int]
    status: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None]
    note: Mapped[str | None]


class RunCalibrationResult(Base):
    __tablename__ = "run_calibration_results"
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("monitoring_runs.id", ondelete="CASCADE"), primary_key=True
    )
    class_label: Mapped[str] = mapped_column(primary_key=True)
    baseline_n: Mapped[int]
    current_n: Mapped[int]
    status: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None]
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB)


class RunErrorResult(Base):
    __tablename__ = "run_error_results"
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("monitoring_runs.id", ondelete="CASCADE"), primary_key=True
    )
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB)


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
