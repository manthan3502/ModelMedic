"""Draft configuration and dataset validation metadata; no trained results."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002_m1"
down_revision = "0001_m0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("setup", JSONB(), nullable=False, server_default="{}"))
    op.add_column(
        "projects",
        sa.Column("deletion_pending", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "datasets", sa.Column("status", sa.String(32), nullable=False, server_default="UPLOADED")
    )
    op.add_column("datasets", sa.Column("canonical_sha256", sa.String(64)))
    op.add_column("datasets", sa.Column("canonical_schema_version", sa.String(32)))
    op.add_column("datasets", sa.Column("profile", JSONB()))
    op.add_column("datasets", sa.Column("validation_report", JSONB()))
    op.add_column("datasets", sa.Column("original_sha256", sa.String(64)))
    op.add_column("datasets", sa.Column("uploaded_bytes", sa.Integer()))
    op.add_column("projects", sa.Column("target_feature_id", sa.String(16)))
    op.add_column("projects", sa.Column("positive_class", sa.Text()))
    op.add_column("projects", sa.Column("classifier", sa.String(32)))
    op.add_column("projects", sa.Column("class_weight_mode", sa.String(16)))
    op.add_column(
        "projects",
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    for name in (
        "validation_report",
        "profile",
        "canonical_schema_version",
        "canonical_sha256",
        "status",
    ):
        op.drop_column("datasets", name)
    op.drop_column("projects", "deletion_pending")
    op.drop_column("projects", "setup")
    for name in (
        "target_feature_id",
        "positive_class",
        "classifier",
        "class_weight_mode",
        "updated_at",
    ):
        op.drop_column("projects", name)
    op.drop_column("datasets", "original_sha256")
    op.drop_column("datasets", "uploaded_bytes")
