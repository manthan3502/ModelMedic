"""Versioned baseline attempts and immutable scientific references."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_m2"
down_revision = "0002_m1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "baseline_snapshots",
        sa.Column("configuration", JSONB(), nullable=False, server_default="{}"),
    )
    for name in ("development_count", "heldout_count", "split_seed"):
        op.add_column("baseline_snapshots", sa.Column(name, sa.Integer()))
    for name in (
        "split_membership_object_key",
        "heldout_reference_object_key",
        "artifact_prefix",
        "methodology_version",
        "code_version",
        "error_message",
    ):
        op.add_column("baseline_snapshots", sa.Column(name, sa.Text()))
    op.add_column("baseline_snapshots", sa.Column("results", JSONB()))
    op.add_column("baseline_snapshots", sa.Column("established_at", sa.DateTime(timezone=True)))
    op.add_column(
        "model_artifacts",
        sa.Column("environment_manifest", JSONB(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("model_artifacts", "environment_manifest")
    for name in (
        "configuration",
        "development_count",
        "heldout_count",
        "split_seed",
        "split_membership_object_key",
        "heldout_reference_object_key",
        "artifact_prefix",
        "methodology_version",
        "code_version",
        "results",
        "error_message",
        "established_at",
    ):
        op.drop_column("baseline_snapshots", name)
