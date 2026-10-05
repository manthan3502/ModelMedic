from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import Job, MonitoringRun, SliceAnalysis, SliceResult


def eligible_features(run: MonitoringRun) -> list[dict[str, str]]:
    assert run.results
    return [
        {"feature_id": f["feature_id"], "name": f["name"], "type": f["type"]}
        for f in run.results["features"]
        if f["type"] == "categorical"
    ]


def slice_view(session: Session, analysis: SliceAnalysis) -> dict[str, Any]:
    job = session.scalar(
        select(Job)
        .where(Job.target_type == "SLICE", Job.target_id == analysis.id)
        .order_by(Job.created_at.desc(), Job.id.desc())
        .limit(1)
    )
    rows = (
        list(
            session.scalars(
                select(SliceResult)
                .where(SliceResult.slice_analysis_id == analysis.id)
                .order_by(
                    SliceResult.is_overall.desc(),
                    SliceResult.slice_value.collate("C").asc().nulls_first(),
                    SliceResult.slice_key,
                )
            )
        )
        if analysis.status == "READY"
        else []
    )
    return {
        "id": str(analysis.id),
        "run_id": str(analysis.run_id),
        "feature_id": analysis.feature_id,
        "feature_name": analysis.feature_name,
        "methodology_version": analysis.methodology_version,
        "code_version": analysis.code_version,
        "status": analysis.status,
        "created_at": analysis.created_at.isoformat(),
        "published_at": analysis.published_at.isoformat() if analysis.published_at else None,
        "limitation": analysis.limitation,
        "job": {
            "id": str(job.id),
            "state": job.state,
            "stage": job.stage,
            "error_message": job.error_message,
        }
        if job
        else None,
        "rows": [
            {
                k: getattr(row, k)
                for k in (
                    "slice_key",
                    "slice_value",
                    "is_overall",
                    "row_count",
                    "class_support",
                    "metrics",
                    "status",
                    "reason",
                )
            }
            for row in rows
        ],
    }
