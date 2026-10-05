from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.models import BaselineSnapshot, MonitoringRun, Project, RunReport
from backend.app.services.reporting import build_report


def save_report(session: Session, run: MonitoringRun, code_version: str) -> RunReport:
    existing = session.get(RunReport, run.id)
    if existing:
        return existing
    project = session.get(Project, run.project_id)
    snapshot = session.get(BaselineSnapshot, run.baseline_snapshot_id)
    assert project and snapshot and snapshot.results and run.results
    manifest = snapshot.results["manifest"]
    generated = session.scalar(select(func.now()))
    assert generated
    payload = build_report(
        {"name": project.name, "description": project.description},
        {
            "Snapshot ID": str(snapshot.id),
            "Classifier": {
                "logistic_regression": "Logistic Regression",
                "random_forest": "Random Forest",
                "gradient_boosting": "Gradient Boosting",
            }[manifest["classifier"]],
            "Weighting": manifest["class_weighting"].capitalize(),
            "Target": manifest["target"],
            "Positive class": manifest["positive_class"],
            "Frozen class order": manifest["class_order"],
            "Development n": snapshot.development_count,
            "Held-out reference n": snapshot.heldout_count,
            "Seed": snapshot.split_seed,
            "Source code version": snapshot.code_version,
        },
        {
            "id": str(run.id),
            "Name": run.name,
            "Monitoring date": run.monitoring_date.isoformat(),
            "Created at": run.created_at.isoformat(),
            "Notes": run.notes,
            "Rows": run.row_count,
            "Analyzed at": run.analyzed_at.isoformat() if run.analyzed_at else None,
        },
        run.results,
        generated.isoformat(),
        code_version,
    )
    row = RunReport(
        run_id=run.id,
        report_template_version=payload["report_template_version"],
        methodology_version=payload["methodology_version"],
        code_version=code_version,
        generated_at=generated,
        payload=payload,
    )
    session.add(row)
    session.flush()
    return row
