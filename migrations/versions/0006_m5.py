"""Additive immutable slice analyses and versioned stored report payloads."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0006_m5"
down_revision = "0005_m4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "slice_analyses",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "run_id",
            UUID(),
            sa.ForeignKey("monitoring_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("feature_id", sa.String(16), nullable=False),
        sa.Column("feature_name", sa.Text(), nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("code_version", sa.String(40)),
        sa.Column("status", sa.String(16), server_default="PENDING", nullable=False),
        sa.Column("limitation", sa.Text()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "run_id", "feature_id", "methodology_version", name="uq_slice_analysis"
        ),
    )
    op.create_table(
        "slice_results",
        sa.Column(
            "slice_analysis_id",
            UUID(),
            sa.ForeignKey("slice_analyses.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("slice_key", sa.String(32), primary_key=True),
        sa.Column("slice_value", sa.Text()),
        sa.Column("is_overall", sa.Boolean(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("class_support", JSONB(), nullable=False),
        sa.Column("metrics", JSONB(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text()),
    )
    op.create_table(
        "run_reports",
        sa.Column(
            "run_id",
            UUID(),
            sa.ForeignKey("monitoring_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("report_template_version", sa.String(32), nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("code_version", sa.String(40), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
    )
    op.execute("""
        CREATE FUNCTION mm_slice_analysis_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF (OLD.status = 'READY' AND to_jsonb(NEW) IS DISTINCT FROM to_jsonb(OLD))
             OR NEW.run_id IS DISTINCT FROM OLD.run_id
             OR NEW.feature_id IS DISTINCT FROM OLD.feature_id
             OR NEW.methodology_version IS DISTINCT FROM OLD.methodology_version THEN
            RAISE EXCEPTION 'Slice analysis binding/results are immutable';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER mm_slice_analysis_immutable BEFORE UPDATE ON slice_analyses
        FOR EACH ROW EXECUTE FUNCTION mm_slice_analysis_immutable();
        CREATE FUNCTION mm_slice_result_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'UPDATE' OR EXISTS (SELECT 1 FROM slice_analyses
              WHERE id = NEW.slice_analysis_id AND status = 'READY') THEN
            RAISE EXCEPTION 'Slice results are immutable';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER mm_slice_result_immutable BEFORE INSERT OR UPDATE ON slice_results
        FOR EACH ROW EXECUTE FUNCTION mm_slice_result_immutable();
        CREATE FUNCTION mm_report_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Stored report payload is immutable'; END $$;
        CREATE TRIGGER mm_report_immutable BEFORE UPDATE ON run_reports
        FOR EACH ROW EXECUTE FUNCTION mm_report_immutable();
    """)


def downgrade() -> None:
    op.drop_table("run_reports")
    op.drop_table("slice_results")
    op.drop_table("slice_analyses")
    for function in (
        "mm_report_immutable",
        "mm_slice_result_immutable",
        "mm_slice_analysis_immutable",
    ):
        op.execute(f"DROP FUNCTION {function}()")
