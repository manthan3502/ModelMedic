"""Frozen monitoring bindings, atomic outputs and database immutability."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0004_m3"
down_revision = "0003_m2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "monitoring_runs",
        sa.Column(
            "monitoring_date", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")
        ),
    )
    op.alter_column("monitoring_runs", "monitoring_date", server_default=None)
    for name in ("notes", "result_object_key"):
        op.add_column("monitoring_runs", sa.Column(name, sa.Text()))
    for name, size in (
        ("mode", 1),
        ("methodology_version", 32),
        ("code_version", 40),
        ("result_sha256", 64),
    ):
        op.add_column("monitoring_runs", sa.Column(name, sa.String(size)))
    op.add_column("monitoring_runs", sa.Column("row_count", sa.Integer()))
    op.add_column("monitoring_runs", sa.Column("analyzed_at", sa.DateTime(timezone=True)))
    op.add_column("monitoring_runs", sa.Column("results", JSONB()))
    op.add_column(
        "monitoring_runs",
        sa.Column("deletion_pending", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index(
        "ix_run_history", "monitoring_runs", ["project_id", "monitoring_date", "created_at", "id"]
    )
    op.create_table(
        "run_feature_results",
        sa.Column(
            "run_id",
            UUID(),
            sa.ForeignKey("monitoring_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("feature_id", sa.String(16), primary_key=True),
        sa.Column("feature_name", sa.Text(), nullable=False),
        sa.Column("feature_type", sa.String(16), nullable=False),
        sa.Column("distribution_status", sa.String(32), nullable=False),
        sa.Column("missingness_status", sa.String(32), nullable=False),
        sa.Column("raw_p_value", sa.Float()),
        sa.Column("adjusted_p_value", sa.Float()),
        sa.Column("missing_p_value", sa.Float()),
        sa.Column("missing_adjusted_p_value", sa.Float()),
        sa.Column("baseline_valid_n", sa.Integer(), nullable=False),
        sa.Column("current_valid_n", sa.Integer(), nullable=False),
        sa.Column("evidence", JSONB(), nullable=False),
    )
    op.execute("""
        CREATE FUNCTION mm_monitoring_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.baseline_snapshot_id IS DISTINCT FROM OLD.baseline_snapshot_id
             OR NEW.project_id IS DISTINCT FROM OLD.project_id
             OR (OLD.state = 'ANALYZED' AND
                 (to_jsonb(NEW) - 'deletion_pending') IS DISTINCT FROM
                 (to_jsonb(OLD) - 'deletion_pending')) THEN
            RAISE EXCEPTION 'Monitoring binding/results are immutable';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER mm_monitoring_immutable BEFORE UPDATE ON monitoring_runs
        FOR EACH ROW EXECUTE FUNCTION mm_monitoring_immutable();
        CREATE FUNCTION mm_feature_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'UPDATE' OR EXISTS (
            SELECT 1 FROM monitoring_runs WHERE id = NEW.run_id AND state = 'ANALYZED'
          ) THEN
            RAISE EXCEPTION 'Monitoring feature results are immutable';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER mm_feature_immutable BEFORE INSERT OR UPDATE ON run_feature_results
        FOR EACH ROW EXECUTE FUNCTION mm_feature_immutable();
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION mm_feature_immutable() CASCADE")
    op.execute("DROP FUNCTION mm_monitoring_immutable() CASCADE")
    op.drop_table("run_feature_results")
    op.drop_index("ix_run_history", "monitoring_runs")
    for name in (
        "monitoring_date",
        "notes",
        "mode",
        "row_count",
        "methodology_version",
        "code_version",
        "analyzed_at",
        "results",
        "result_object_key",
        "result_sha256",
        "deletion_pending",
    ):
        op.drop_column("monitoring_runs", name)
