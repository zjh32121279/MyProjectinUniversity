from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bookflow_core.models import (
    AgentRun,
    Book,
    BookCopy,
    LibraryProfile,
    Loan,
    ReaderAccount,
    RiskWarning,
    Shelf,
    LibraryZone,
    SystemSetting,
    WorkTask,
)
from bookflow_core.services.statistics_service import (
    ACTIVE_TASK_STATUSES,
    OPEN_RISK_STATUSES,
    get_business_date,
    operation_metric_series,
    operation_metric_value,
    operation_statistics,
)


def chart(labels: list[str], series: list[dict]) -> dict:
    return {"labels": labels, "series": series}


def _metric_value(db: Session, key: str, fallback: int = 0, *, metric_date: str | date | None = None) -> int:
    return operation_metric_value(db, key, fallback, metric_date=metric_date)


def _metric_series(db: Session, key: str, labels: list[str], fallback: list[int]) -> list[int]:
    return operation_metric_series(db, key, labels, fallback)


def _count_shelves_for_zone(db: Session, zone_code: str) -> int:
    return int(db.scalar(select(func.count(Shelf.id)).join(LibraryZone, Shelf.zone_id == LibraryZone.id).where(LibraryZone.zone_code == zone_code)) or 0)


def _trend_text(current: int, previous: int) -> dict:
    if previous <= 0:
        return {"text": "无昨日基线", "direction": "flat", "percentage": 0}
    ratio = (current - previous) / previous
    direction = "up" if ratio > 0 else "down" if ratio < 0 else "flat"
    prefix = "up" if ratio > 0 else "down" if ratio < 0 else "flat"
    return {"text": f"{prefix} {abs(ratio) * 100:.0f}%" if ratio else "flat", "direction": direction, "percentage": round(ratio, 4)}


def _dashboard_trends(db: Session, operations: dict) -> dict:
    as_of = get_business_date(db, operations.get("business_date"))
    previous = as_of - timedelta(days=1)
    fallback = {
        "today_borrow_count": int(db.scalar(select(func.count(Loan.id)).where(func.date(Loan.borrowed_at) == str(previous))) or 0),
        "today_return_count": int(db.scalar(select(func.count(Loan.id)).where(func.date(Loan.returned_at) == str(previous))) or 0),
        "current_visit_reader_count": 0,
        "overdue_count": int(db.scalar(select(func.count(Loan.id)).where(Loan.status == "overdue")) or 0),
    }
    keys = ["today_borrow_count", "today_return_count", "current_visit_reader_count", "overdue_count"]
    return {key: _trend_text(int(operations.get(key, 0)), _metric_value(db, key, fallback[key], metric_date=previous)) for key in keys}



def _setting_value(db: Session, key: str, fallback: str | None = None) -> str | None:
    value = db.scalar(select(SystemSetting.setting_value).where(SystemSetting.setting_key == key, SystemSetting.is_active == True))
    return value if value not in (None, "") else fallback

def library_profile(db: Session) -> dict:
    profile = db.scalar(select(LibraryProfile).order_by(LibraryProfile.id))
    total_books = int(db.scalar(select(func.count(Book.id))) or 0)
    total_copies = int(db.scalar(select(func.count(BookCopy.id))) or 0)
    available_copies = int(db.scalar(select(func.count(BookCopy.id)).where(BookCopy.copy_status == "available")) or 0)
    registered_readers = int(db.scalar(select(func.count(ReaderAccount.id))) or 0)
    zone_count = int(db.scalar(select(func.count(LibraryZone.id))) or 0)
    shelf_count = int(db.scalar(select(func.count(Shelf.id))) or 0)

    return {
        "library_name": profile.library_name if profile else "",
        "name": profile.library_name if profile else "",
        "library_type": profile.library_type if profile else "",
        "service_population": profile.service_population if profile else "",
        "building_area_sqm": profile.building_area_sqm if profile else 0,
        "open_floors": profile.open_floors if profile else "",
        "address": _setting_value(db, "library.address", "天津市滨海新区文化路 18 号"),
        "opening_hours": _setting_value(db, "library.open_hours", "周一至周日 08:30-20:30"),
        "phone": _setting_value(db, "library.phone", "022-8899-3200"),
        "service_phone": _setting_value(db, "library.phone", "022-8899-3200"),
        "service_email": _setting_value(db, "library.service_email", "service@bookflow.local"),
        "paper_collection_count": profile.paper_collection_count if profile and profile.paper_collection_count is not None else total_copies,
        "book_species_count": _metric_value(db, "book_species_count", total_books),
        "lendable_collection_count": profile.lendable_collection_count if profile and profile.lendable_collection_count is not None else available_copies,
        "in_library_reference_count": profile.in_library_reference_count if profile else 0,
        "periodical_count": profile.periodical_count if profile else 0,
        "reading_seat_count": profile.reading_seat_count if profile else 0,
        "shelf_count": profile.shelf_count if profile and profile.shelf_count is not None else shelf_count,
        "registered_reader_count": profile.registered_reader_count if profile and profile.registered_reader_count is not None else registered_readers,
        "monthly_active_reader_count": profile.monthly_active_reader_count if profile else 0,
        "weekday_daily_visits": profile.weekday_daily_visits if profile else 0,
        "weekend_daily_visits": profile.weekend_daily_visits if profile else 0,
        "zone_count": _metric_value(db, "zone_count", zone_count),
        "reservation_shelf_count": _metric_value(db, "reservation_shelf_count", _count_shelves_for_zone(db, "Z02")),
        "turnover_shelf_count": _metric_value(db, "turnover_shelf_count", _count_shelves_for_zone(db, "Z11")),
        "updated_at": str(profile.updated_at) if profile else "",
    }


def operation_snapshot(db: Session, *, business_date: date | str | None = None) -> dict:
    return operation_statistics(db, business_date=business_date)


def admin_dashboard(db: Session, *, business_date: date | str | None = None, generate_home_ai_summary: bool = False) -> dict:
    from bookflow_core.services.dashboard_ai import _home_ai_summary, _dashboard_ai_insights

    total_copies = int(db.scalar(select(func.count(BookCopy.id))) or 0)
    available = int(db.scalar(select(func.count(BookCopy.id)).where(BookCopy.copy_status == "available")) or 0)
    borrowed = int(db.scalar(select(func.count(BookCopy.id)).where(BookCopy.copy_status == "borrowed")) or 0)
    reserved = int(db.scalar(select(func.count(BookCopy.id)).where(BookCopy.copy_status == "reserved")) or 0)
    ai_runs = int(db.scalar(select(func.count(AgentRun.id))) or 0)
    ai_success = int(db.scalar(select(func.count(AgentRun.id)).where(AgentRun.status.in_(["success", "completed", "succeeded"]))) or 0)
    recent_tasks = db.scalars(select(WorkTask).order_by(WorkTask.id.desc()).limit(5)).all()
    recent_risks = db.scalars(select(RiskWarning).where(RiskWarning.status.in_(OPEN_RISK_STATUSES)).order_by(RiskWarning.id.desc()).limit(5)).all()
    profile = library_profile(db)
    operations = operation_snapshot(db, business_date=business_date)
    return {
        **operations,
        "pending_task_count": int(db.scalar(select(func.count(WorkTask.id)).where(WorkTask.status.in_(ACTIVE_TASK_STATUSES))) or 0),
        "collection_total": profile["paper_collection_count"],
        "book_species_count": profile["book_species_count"],
        "available_copy_count": profile["lendable_collection_count"],
        "registered_reader_count": profile["registered_reader_count"],
        "monthly_active_reader_count": profile["monthly_active_reader_count"],
        "library_profile": profile,
        "collection_database_total": total_copies,
        "available_copy_database_count": available,
        "borrowed_copy_count": borrowed,
        "reserved_copy_count": reserved,
        "collection_in_library_rate": round(profile["lendable_collection_count"] / profile["paper_collection_count"], 4) if profile["paper_collection_count"] else 0.0,
        "ai_success_rate": round(ai_success / ai_runs, 4) if ai_runs else 0.0,
        "recent_tasks": [{"task_code": row.task_code, "title": row.title, "description": row.description, "status": row.status, "priority": row.priority, "source_type": row.source_type, "created_at": str(row.created_at)} for row in recent_tasks],
        "recent_risks": [{"warning_code": row.warning_code, "warning_type": row.warning_type, "title": row.title, "description": row.description, "severity": row.severity, "status": row.status, "created_at": str(row.created_at)} for row in recent_risks],
        "home_ai_summary": _home_ai_summary(db, operations, generate=generate_home_ai_summary),
        "dashboard_trends": _dashboard_trends(db, operations),
        "ai_insights": _dashboard_ai_insights(db, operations),
    }

