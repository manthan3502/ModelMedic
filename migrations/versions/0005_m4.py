"""Immutable labeled metrics, calibration evidence and error references."""

from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0005_m4"
down_revision = "0004_m3"
branch_labels = None
depends_on = None


def binding() -> sa.Column[Any]:
    return sa.Column(
        "run_id", UUID(), sa.ForeignKey("monitoring_runs.id", ondelete="CASCADE"), primary_key=True
    )


def upgrade() -> None:
    op.create_table(
        "run_metrics",
        binding(),
        sa.Column("scope", sa.String(16), primary_key=True),
        sa.Column("class_label", sa.Text(), primary_key=True),
        sa.Column("metric_name", sa.String(32), primary_key=True),
        *[sa.Column(n, sa.Float()) for n in ("baseline_value", "current_value", "delta")],
        sa.Column("baseline_support", sa.Integer(), nullable=False),
        sa.Column("current_support", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("note", sa.Text()),
    )
    op.create_table(
        "run_calibration_results",
        binding(),
        sa.Column("class_label", sa.Text(), primary_key=True),
        sa.Column("baseline_n", sa.Integer(), nullable=False),
        sa.Column("current_n", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("evidence", JSONB(), nullable=False),
    )
    op.create_table("run_error_results", binding(), sa.Column("evidence", JSONB(), nullable=False))
    for table in ("run_metrics", "run_calibration_results", "run_error_results"):
        op.execute(
            f"CREATE TRIGGER mm_labeled_immutable BEFORE INSERT OR UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION mm_feature_immutable()"
        )


def downgrade() -> None:
    for table in ("run_error_results", "run_calibration_results", "run_metrics"):
        op.drop_table(table)
