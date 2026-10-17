from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy import desc
from sqlalchemy.orm import Session

from bookflow_core.core.time import today
from bookflow_core.models import (
    BookCirculationStats,
    BookCopy,
    Loan,
    WorkTask,
    DailyOperationMetric,
    ReaderAccount,
    Reservation,
    RiskWarning,
    SystemSetting,
)

ACTIVE_RESERVATION_STATUSES = {"waiting", "ready_for_pickup"}
ACTIVE_TASK_STATUSES = {"pending", "ai_processing", "waiting_human", "admin_processing"}
HUMAN_TAKEOVER_ALLOWED_STATUSES = {"pending", "ai_processing", "waiting_human"}
AI_RUNNING_STATUSES = {"ai_processing"}
COMPLETED_TASK_STATUSES = {"resolved"}
CANCELLED_TASK_STATUSES = {"cancelled"}
AI_TASK_SOURCE_TYPES = {"ai", "ai_admin", "ai_review"}
UNAVAILABLE_COPY_STATUSES = {"maintenance", "unavailable"}
OPEN_RISK_STATUSES = {"active", "open", "reviewing"}

METRIC_ALIASES = {
    "today_borrow_count": ("today_borrow_count", "borrow_count"),
    "today_return_count": ("today_return_count", "return_count"),
    "today_new_reader_count": ("today_new_reader_count", "new_reader_count"),
    "due_today_count": ("due_today_count", "today_due_book_count"),
}

SNAPSHOT_DISPLAY_KEYS = {
    "today_new_reader_count",
    "current_visit_reader_count",
}


def parse_business_date(value: date | str | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def get_business_date(db: Session, requested_date: date | str | None = None) -> date:
    parsed = parse_business_date(requested_date)
    if parsed:
        return parsed
    return today()


def date_window(end_date: date, days: int) -> list[date]:
    return [end_date - timedelta(days=idx) for idx in range(days - 1, -1, -1)]


def _metric_keys(key: str) -> tuple[str, ...]:
    return METRIC_ALIASES.get(key, (key,))


def operation_metric_value(db: Session, key: str, fallback: int = 0, *, metric_date: str | date | None = None) -> int:
    resolved_date = parse_business_date(metric_date) or get_business_date(db)
    value = db.scalar(
        select(DailyOperationMetric.metric_value)
        .where(DailyOperationMetric.metric_date == str(resolved_date), DailyOperationMetric.metric_key.in_(_metric_keys(key)))
        .order_by(DailyOperationMetric.id.desc())
    )
    if value is None and metric_date is None:
        value = db.scalar(
            select(DailyOperationMetric.metric_value)
            .where(DailyOperationMetric.metric_key.in_(_metric_keys(key)))
            .order_by(DailyOperationMetric.metric_date.desc(), DailyOperationMetric.id.desc())
        )
    return int(value if value is not None else fallback)


def operation_metric_series(db: Session, key: str, labels: list[str], fallback: list[int]) -> list[int]:
    rows = db.scalars(
        select(DailyOperationMetric)
        .where(DailyOperationMetric.metric_key.in_(_metric_keys(key)), DailyOperationMetric.metric_date.in_(labels))
        .order_by(DailyOperationMetric.id)
    ).all()
    values = {str(row.metric_date): int(row.metric_value) for row in rows}
    return [values.get(metric_date, fallback[index]) for index, metric_date in enumerate(labels)]


def count_active_reservations(db: Session) -> int:
    return int(db.scalar(select(func.count(Reservation.id)).where(Reservation.status.in_(ACTIVE_RESERVATION_STATUSES))) or 0)


def count_pending_shelving_tasks(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count(WorkTask.id)).where(
                WorkTask.status.in_(ACTIVE_TASK_STATUSES),
                WorkTask.source_type.in_(["shelving", "catalog"]),
            )
        )
        or 0
    )


def count_ai_pending_tasks(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count(WorkTask.id)).where(
                WorkTask.status.in_(ACTIVE_TASK_STATUSES),
                or_(
                    WorkTask.source_type.in_(AI_TASK_SOURCE_TYPES),
                    WorkTask.handler_type.in_(["ai", "mixed"]),
                    WorkTask.claim_status.in_(["ai_claimed", "waiting_human"]),
                ),
            )
        )
        or 0
    )


def count_pending_tasks(db: Session) -> int:
    return int(db.scalar(select(func.count(WorkTask.id)).where(WorkTask.status.in_(ACTIVE_TASK_STATUSES))) or 0)


def real_time_operation_counts(db: Session, *, business_date: date | str | None = None) -> dict[str, int]:
    as_of = get_business_date(db, business_date)
    return {
        "today_borrow_count": int(db.scalar(select(func.count(Loan.id)).where(func.date(Loan.borrowed_at) == str(as_of))) or 0),
        "today_return_count": int(db.scalar(select(func.count(Loan.id)).where(func.date(Loan.returned_at) == str(as_of))) or 0),
        "today_new_reader_count": int(db.scalar(select(func.count(ReaderAccount.id)).where(func.date(ReaderAccount.created_at) == str(as_of))) or 0),
        "due_today_count": int(
            db.scalar(
                select(func.count(Loan.id)).where(
                    func.date(Loan.due_at) == str(as_of),
                    Loan.status.in_(["active", "overdue"]),
                )
            )
            or 0
        ),
        "overdue_count": int(db.scalar(select(func.count(Loan.id)).where(Loan.status == "overdue")) or 0),
        "reservation_count": count_active_reservations(db),
        "pending_shelving_count": count_pending_shelving_tasks(db),
        "unavailable_copy_count": int(db.scalar(select(func.count(BookCopy.id)).where(BookCopy.copy_status.in_(UNAVAILABLE_COPY_STATUSES))) or 0),
        "hot_book_count": int(db.scalar(select(func.count(BookCirculationStats.id)).where(BookCirculationStats.circulation_type == "鐑棬")) or 0),
        "cold_book_count": int(db.scalar(select(func.count(BookCirculationStats.id)).where(BookCirculationStats.circulation_type == "鍐烽棬")) or 0),
        "ai_pending_task_count": count_ai_pending_tasks(db),
        "risk_warning_count": int(db.scalar(select(func.count(RiskWarning.id)).where(RiskWarning.status.in_(OPEN_RISK_STATUSES))) or 0),
        "current_visit_reader_count": 0,
        "today_ai_processed_count": int(
            db.scalar(
                select(func.count(WorkTask.id)).where(
                    WorkTask.status.in_(COMPLETED_TASK_STATUSES),
                    or_(WorkTask.handler_type == "ai", WorkTask.claim_status == "ai_completed"),
                    func.date(WorkTask.resolved_at) == str(as_of),
                )
            )
            or 0
        ),
    }


def latest_snapshot_date(db: Session) -> date | None:
    value = db.scalar(select(DailyOperationMetric.metric_date).order_by(DailyOperationMetric.metric_date.desc(), DailyOperationMetric.id.desc()))
    return parse_business_date(value)


def snapshot_date_for(db: Session, *, business_date: date | str | None = None) -> date:
    as_of = get_business_date(db, business_date)
    exists = db.scalar(select(func.count(DailyOperationMetric.id)).where(DailyOperationMetric.metric_date == str(as_of)))
    if exists:
        return as_of
    return latest_snapshot_date(db) or as_of


def daily_snapshot_counts(db: Session, *, business_date: date | str | None = None) -> dict[str, int]:
    as_of = snapshot_date_for(db, business_date=business_date)
    rows = db.scalars(select(DailyOperationMetric).where(DailyOperationMetric.metric_date == str(as_of))).all()
    values: dict[str, int] = {}
    for row in rows:
        key = "due_today_count" if row.metric_key == "today_due_book_count" else row.metric_key
        values[key] = int(row.metric_value)
    return values


def operation_statistics(db: Session, *, business_date: date | str | None = None) -> dict:
    as_of = get_business_date(db, business_date)
    snap_date = snapshot_date_for(db, business_date=as_of)
    real_time = real_time_operation_counts(db, business_date=as_of)
    snapshot = daily_snapshot_counts(db, business_date=snap_date)
    selected: dict[str, int] = {}
    source: dict[str, str] = {}
    for key, real_value in real_time.items():
        if key in SNAPSHOT_DISPLAY_KEYS and key in snapshot:
            selected[key] = snapshot[key]
            source[key] = "daily_snapshot"
        else:
            selected[key] = real_value
            source[key] = "real_time"

    return {
        **selected,
        "business_date": str(as_of),
        "snapshot_date": str(snap_date),
        "system_date": str(today()),
        "metric_source": source,
        "real_time": real_time,
        "daily_snapshot": snapshot,
    }


