"""M0 relational foundation. Later milestones extend these minimal metadata tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_m0"
down_revision = None
branch_labels = None
depends_on = None


def identity() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    ]


def project_fk() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(
        "project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "projects",
        *identity(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("state", sa.String(32), nullable=False, server_default="DRAFT"),
    )
    op.create_table(
        "datasets",
        *identity(),
        project_fk(),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("original_object_key", sa.Text(), nullable=False),
        sa.Column("canonical_object_key", sa.Text()),
    )
    op.create_table(
        "baseline_snapshots",
        *identity(),
        project_fk(),
        sa.Column(
            "dataset_id",
            sa.Uuid(),
            sa.ForeignKey("datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("config_fingerprint", sa.Text(), nullable=False),
    )
    op.create_table(
        "model_artifacts",
        *identity(),
        project_fk(),
        sa.Column(
            "snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("baseline_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.Text(), nullable=False, unique=True),
        sa.Column("sha256", sa.String(64), nullable=False),
    )
    op.create_table(
        "monitoring_runs",
        *identity(),
        project_fk(),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("datasets.id", ondelete="SET NULL")),
        sa.Column(
            "baseline_snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("baseline_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default="UPLOADED"),
    )
    op.create_table(
        "jobs",
        *identity(),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE")),
        sa.Column("params", postgresql.JSONB(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="QUEUED"),
        sa.Column("stage", sa.String(64), nullable=False, server_default="WAITING"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("owner_token", sa.Uuid()),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error_message", sa.Text()),
        sa.CheckConstraint(
            "state IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED')", name="job_state"
        ),
        sa.CheckConstraint("attempt >= 0 AND max_attempts BETWEEN 1 AND 2", name="job_attempts"),
    )
    op.create_index(
        "uq_active_job",
        "jobs",
        ["job_type", "target_type", "target_id"],
        unique=True,
        postgresql_where=sa.text("state IN ('QUEUED', 'RUNNING')"),
    )
    op.create_index("ix_queue", "jobs", ["state", "created_at"])
    op.create_table(
        "worker_status",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "worker_status",
        "jobs",
        "monitoring_runs",
        "model_artifacts",
        "baseline_snapshots",
        "datasets",
        "projects",
    ):
        op.drop_table(table)
