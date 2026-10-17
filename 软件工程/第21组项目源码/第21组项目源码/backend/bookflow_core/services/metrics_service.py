from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from bookflow_core.models import DailyOperationMetric
from bookflow_core.services.common import write_audit
from bookflow_core.services.statistics_service import get_business_date
from bookflow_core.services.dashboard_service import admin_dashboard


def refresh_daily_operation_metrics(db: Session, *, metric_date: str | None = None, actor_type: str = "system", actor_id: str = "metrics", commit: bool = True) -> dict:
    """Persist dashboard counters into operation_metrics for trend queries.

    This is intentionally derived from database aggregates, not constants.
    Existing metrics for the same day/key are updated in-place, so scheduled runs are idempotent.
    """
    try:
        business_date = get_business_date(db, metric_date)
        metric_date_str = str(business_date)
        dashboard = admin_dashboard(db, business_date=metric_date_str)
        written: list[dict] = []
        for key, value in dashboard.items():
            if not isinstance(value, int):
                continue
            row = db.scalar(select(DailyOperationMetric).where(DailyOperationMetric.metric_date == business_date, DailyOperationMetric.metric_key == key))
            if not row:
                row = DailyOperationMetric(metric_date=business_date, metric_key=key, metric_value=str(value))
                db.add(row)
            else:
                row.metric_value = str(value)
            written.append({"metric_key": key, "metric_value": value})
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="refresh_daily_operation_metrics", target_table="daily_operation_metrics", target_id=metric_date_str, detail={"count": len(written)})
        if commit:
            db.commit()
        return {"metric_date": metric_date_str, "written": written, "count": len(written)}
    except Exception:
        if commit:
            db.rollback()
        raise

