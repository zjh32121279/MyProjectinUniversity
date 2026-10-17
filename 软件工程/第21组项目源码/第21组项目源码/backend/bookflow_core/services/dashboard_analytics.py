from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import Integer, case, cast, func, select
from sqlalchemy.orm import Session

from bookflow_core.models import (
    AgentRun,
    AgentStep,
    AuditEvent,
    Book,
    BookCirculationStats,
    BookCategory,
    BookCopy,
    LibraryProfile,
    Loan,
    NotificationDelivery,
    ReaderAccount,
    Reservation,
    RiskWarning,
    Shelf,
    ShelfPosition,
    LibraryZone,
    WorkTask,
)
from bookflow_core.services.dashboard_core import (
    _count_shelves_for_zone,
    _metric_series,
    _metric_value,
    chart,
    library_profile,
    operation_snapshot,
)
from bookflow_core.services.statistics_service import (
    ACTIVE_TASK_STATUSES,
    OPEN_RISK_STATUSES,
    UNAVAILABLE_COPY_STATUSES,
    date_window,
    get_business_date,
)


def _int_value(value: object, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def analytics_overview(db: Session, *, business_date: date | str | None = None) -> dict:
    as_of = get_business_date(db, business_date)
    # 每次请求自动刷新今日指标，确保趋势图数据实时
    from bookflow_core.services.metrics_service import refresh_daily_operation_metrics
    refresh_daily_operation_metrics(db, metric_date=str(as_of), commit=False)
    profile = library_profile(db)
    operations = operation_snapshot(db, business_date=as_of)
    unread_notifications = int(
        db.scalar(
            select(func.count(NotificationDelivery.id)).where(
                NotificationDelivery.delivery_status == "sent",
                NotificationDelivery.read_status == "unread",
                NotificationDelivery.archived_at == None,
            )
        )
        or 0
    )
    write_audits = int(db.scalar(select(func.count(AuditEvent.id)).where(AuditEvent.result == "success")) or 0)
    date_objs = date_window(as_of, 30)
    labels = [str(day) for day in date_objs]
    borrow_fallback = [0 for _day in date_objs]
    return_fallback = [0 for _day in date_objs]
    borrow_data = _metric_series(db, "today_borrow_count", labels, borrow_fallback)
    return_data = _metric_series(db, "today_return_count", labels, return_fallback)
    categories = db.execute(select(BookCategory.category_name, func.count(Book.id)).join(Book, Book.category_id == BookCategory.id).group_by(BookCategory.id).order_by(BookCategory.sort_order)).all()
    circulation_rows = dict(
        db.execute(select(BookCirculationStats.circulation_type, func.count(BookCirculationStats.id)).group_by(BookCirculationStats.circulation_type)).all()
    )
    readers_by_type = dict(db.execute(select(ReaderAccount.reader_type_code, func.count(ReaderAccount.id)).group_by(ReaderAccount.reader_type_code)).all())
    risk_by_level = dict(db.execute(select(RiskWarning.severity, func.count(RiskWarning.id)).where(RiskWarning.status.in_(OPEN_RISK_STATUSES)).group_by(RiskWarning.severity)).all())
    task_status_rows = dict(db.execute(select(WorkTask.status, func.count(WorkTask.id)).group_by(WorkTask.status)).all())
    base = {
        **operations,
        "total_books": profile["book_species_count"],
        "total_copies": profile["paper_collection_count"],
        "available_copies": profile["lendable_collection_count"],
        "availability_rate": round(profile["lendable_collection_count"] / profile["paper_collection_count"], 4) if profile["paper_collection_count"] else 0,
        "reader_count": profile["registered_reader_count"],
        "unread_notifications": unread_notifications,
        "audit_success_count": write_audits,
        "circulation_distribution": {
            "hot": operations["hot_book_count"],
            "normal": max(profile["book_species_count"] - operations["hot_book_count"] - operations["cold_book_count"], 0),
            "cold": operations["cold_book_count"],
        },
    }
    base.update(
        {
            "last_30_days_borrow_return_trend": chart(labels, [{"name": "borrow", "data": borrow_data}, {"name": "return", "data": return_data}]),
            "task_status_distribution": {
                "items": [
                    {
                        "name": name,
                        "label": {
                            "pending": "待处理",
                            "ai_processing": "AI处理中",
                            "waiting_human": "待人工介入",
                            "admin_processing": "人工处理中",
                            "resolved": "已完成",
                            "cancelled": "已取消",
                        }[name],
                        "count": int(task_status_rows.get(name, 0)),
                    }
                    for name in ["pending", "ai_processing", "waiting_human", "admin_processing", "resolved", "cancelled"]
                ]
            },
            "category_collection_distribution": {"items": [{"name": name or "unknown", "count": int(count)} for name, count in categories]},
            "circulation_type_distribution": {"items": [{"name": name, "label": name, "count": int(circulation_rows.get(name, 0))} for name in ["热门", "普通", "冷门"]]},
            "reader_type_distribution": {"items": [{"name": name, "label": {"child": "儿童读者", "teen": "青少年读者", "adult": "成人读者", "senior": "老年读者", "institution": "机构账号"}[name], "count": int(readers_by_type.get(name, 0))} for name in ["child", "teen", "adult", "senior", "institution"]]},
            "overdue_trend": chart(labels, [{"name": "overdue", "data": [0 for _day in date_objs]}]),
            "ai_task_trend": chart(labels, [{"name": "ai_runs", "data": [0 for _day in date_objs]}]),
            "risk_level_distribution": {"items": [{"name": name, "label": {"low": "低", "medium": "中", "high": "高", "critical": "严重"}[name], "count": int(risk_by_level.get(name, 0))} for name in ["low", "medium", "high", "critical"]]},
        }
    )
    return base


def collection_health(db: Session, *, business_date: date | str | None = None) -> dict:
    profile = library_profile(db)
    operations = operation_snapshot(db, business_date=business_date)
    total_books = int(db.scalar(select(func.count(Book.id))) or 0)
    total_copies = int(db.scalar(select(func.count(BookCopy.id))) or 0)
    available_count = int(db.scalar(select(func.count(BookCopy.id)).where(BookCopy.copy_status == "available")) or 0)
    borrowed_count = int(db.scalar(select(func.count(BookCopy.id)).where(BookCopy.copy_status == "borrowed")) or 0)
    reserved_count = int(db.scalar(select(func.count(BookCopy.id)).where(BookCopy.copy_status == "reserved")) or 0)
    unavailable_count = int(db.scalar(select(func.count(BookCopy.id)).where(BookCopy.copy_status.in_(UNAVAILABLE_COPY_STATUSES))) or 0)
    by_status = {
        "available": available_count,
        "borrowed": borrowed_count,
        "reserved": reserved_count,
        "unavailable": unavailable_count,
    }
    circulation = {
        ctype: int(db.scalar(select(func.count(BookCirculationStats.id)).where(BookCirculationStats.circulation_type == ctype)) or 0)
        for ctype in ["热门", "普通", "冷门"]
    }
    s04_rate = round(unavailable_count / total_copies, 4) if total_copies else 0
    available_rate = round(by_status["available"] / total_copies, 4) if total_copies else 0
    copy_count_by_book = select(BookCopy.book_id.label("book_id"), func.count(BookCopy.id).label("copy_count")).group_by(BookCopy.book_id).subquery()
    category_rows = db.execute(
        select(Book.category_id, func.count(Book.id), func.sum(func.coalesce(copy_count_by_book.c.copy_count, 0)))
        .outerjoin(copy_count_by_book, copy_count_by_book.c.book_id == Book.id)
        .group_by(Book.category_id)
    ).all()
    shelf_rows = db.execute(
        select(
            LibraryZone.id,
            LibraryZone.zone_code,
            LibraryZone.zone_name,
            func.count(BookCopy.id),
            func.sum(case((BookCopy.copy_status == "available", 1), else_=0)),
            func.sum(case((BookCopy.copy_status == "borrowed", 1), else_=0)),
            func.sum(case((BookCopy.copy_status == "reserved", 1), else_=0)),
            func.sum(case((BookCopy.copy_status.in_(UNAVAILABLE_COPY_STATUSES), 1), else_=0)),
            func.sum(case((BookCirculationStats.days_since_last_borrow >= 180, 1), else_=0)),
        )
        .join(Shelf, BookCopy.current_shelf_id == Shelf.id)
        .join(LibraryZone, Shelf.zone_id == LibraryZone.id)
        .join(Book, BookCopy.book_id == Book.id)
        .join(BookCirculationStats, BookCirculationStats.book_id == Book.id)
        .group_by(LibraryZone.id, LibraryZone.zone_code, LibraryZone.zone_name, LibraryZone.sort_order)
        .order_by(LibraryZone.sort_order, LibraryZone.id)
        .limit(20)
    ).all()
    status_summary = dict(by_status)
    unavailable_rate = s04_rate
    return {
        "total_books": total_books,
        "total_copies": total_copies,
        "available_copies": available_count,
        "borrowed_copies": borrowed_count,
        "reserved_copies": reserved_count,
        "unavailable_copies": unavailable_count,
        "pending_shelving_count": operations["pending_shelving_count"],
        "hot_books": circulation["热门"],
        "cold_books": circulation["冷门"],
        "stale_books": int(db.scalar(select(func.count(BookCirculationStats.id)).where(BookCirculationStats.days_since_last_borrow >= 180)) or 0),
        "by_status": status_summary,
        "copy_status_counts": by_status,
        "book_database_total": total_books,
        "copy_database_total": total_copies,
        "available_rate": available_rate,
        "unavailable_rate": unavailable_rate,
        "profile_snapshot": {
            "book_species_count": profile["book_species_count"],
            "paper_collection_count": profile["paper_collection_count"],
            "lendable_collection_count": profile["lendable_collection_count"],
        },
        "circulation_distribution": circulation,
        "circulation_database_distribution": circulation,
        "health_level": "warning" if unavailable_rate >= 0.08 else "normal",
        "category_health": {"items": [{"category_id": cid, "book_count": int(book_count), "copy_count": int(copy_count or 0)} for cid, book_count, copy_count in category_rows]},
        "shelf_utilization": {
            "items": [
                {
                    "zone_id": zone_id,
                    "zone_code": zone_code,
                    "zone_name": zone_name,
                    "copy_count": int(copy_count or 0),
                    "available_count": int(available_count or 0),
                    "borrowed_count": int(borrowed_count or 0),
                    "reserved_count": int(reserved_count or 0),
                    "unavailable_count": int(unavailable_count or 0),
                    "stale_count": int(stale_count or 0),
                    "in_rack_rate": round((int(available_count or 0) / int(copy_count or 1)) * 100, 1) if int(copy_count or 0) else 0,
                    "use_rate": round((int(borrowed_count or 0) / int(copy_count or 1)) * 100, 1) if int(copy_count or 0) else 0,
                    "stale_rate": round((int(stale_count or 0) / int(copy_count or 1)) * 100, 1) if int(copy_count or 0) else 0,
                }
                for zone_id, zone_code, zone_name, copy_count, available_count, borrowed_count, reserved_count, unavailable_count, stale_count in shelf_rows
            ]
        },
        "suggestions": [
            {"type": "unavailable", "message": "请核查暂不可借馆藏并完成修复、下架或重新上架。", "count": unavailable_count},
            {"type": "cold", "message": "冷门馆藏可结合主题展示和架位调整提升流通。", "count": circulation["冷门"]},
        ],
    }


def circulation_analytics(db: Session, *, business_date: date | str | None = None, limit: int = 10) -> dict:
    as_of = get_business_date(db, business_date)
    borrow_status = {
        "active": int(db.scalar(select(func.count(Loan.id)).where(Loan.status == "active")) or 0),
        "borrowed": int(db.scalar(select(func.count(Loan.id)).where(Loan.status == "active")) or 0),
        "returned": int(db.scalar(select(func.count(Loan.id)).where(Loan.status.in_(["returned", "returned_overdue"]))) or 0),
        "overdue": int(db.scalar(select(func.count(Loan.id)).where(Loan.status == "overdue")) or 0),
    }
    reservation_status = {
        status: int(db.scalar(select(func.count(Reservation.id)).where(Reservation.status == status)) or 0)
        for status in ["waiting", "ready_for_pickup", "cancelled", "expired", "fulfilled"]
    }
    top_hot_books = db.execute(
        select(Book, BookCirculationStats)
        .join(BookCirculationStats, BookCirculationStats.book_id == Book.id)
        .order_by(BookCirculationStats.borrow_90d.desc(), BookCirculationStats.reserve_90d.desc())
        .limit(limit)
    ).all()
    top_cold_books = db.execute(
        select(Book, BookCirculationStats)
        .join(BookCirculationStats, BookCirculationStats.book_id == Book.id)
        .where(BookCirculationStats.circulation_type == "冷门")
        .order_by(BookCirculationStats.days_since_last_borrow.desc())
        .limit(limit)
    ).all()
    copy_count_by_book = select(BookCopy.book_id.label("book_id"), func.count(BookCopy.id).label("copy_count")).group_by(BookCopy.book_id).subquery()
    category_rows = db.execute(
        select(
            BookCategory.id,
            BookCategory.category_name,
            func.count(Book.id),
            func.sum(func.coalesce(copy_count_by_book.c.copy_count, 0)),
            func.sum(BookCirculationStats.borrow_90d),
            func.sum(BookCirculationStats.reserve_90d),
            func.sum(case((BookCirculationStats.circulation_type == "热门", 1), else_=0)),
            func.sum(case((BookCirculationStats.circulation_type == "冷门", 1), else_=0)),
        )
        .join(Book, Book.category_id == BookCategory.id)
        .join(BookCirculationStats, BookCirculationStats.book_id == Book.id)
        .outerjoin(copy_count_by_book, copy_count_by_book.c.book_id == Book.id)
        .group_by(BookCategory.id, BookCategory.category_name, BookCategory.sort_order)
        .order_by(BookCategory.sort_order, BookCategory.id)
    ).all()
    total_category_books = sum(int(book_count or 0) for _category_id, _name, book_count, *_rest in category_rows)
    return {
        "business_date": str(as_of),
        "page_size": limit,
        "borrow_status": borrow_status,
        "reservation_status": reservation_status,
        "top_hot_books": [
            {"book_code": book.book_code, "title": book.title, "author": book.author, "category_id": book.category_id, "cover_url": book.cover_url, "total_copies": _int_value(stats.total_copies, _int_value(book.copy_count_snapshot)), "borrow_90d": stats.borrow_90d, "reserve_90d": stats.reserve_90d}
            for book, stats in top_hot_books
        ],
        "top_cold_books": [
            {"book_code": book.book_code, "title": book.title, "author": book.author, "category_id": book.category_id, "cover_url": book.cover_url, "total_copies": _int_value(stats.total_copies, _int_value(book.copy_count_snapshot)), "borrow_365d": stats.borrow_365d, "days_since_last_borrow": stats.days_since_last_borrow, "days_since_last_borrow_unit": "days"}
            for book, stats in top_cold_books
        ],
        "category_heat_distribution": {
            "items": [
                {"category_id": category_id, "name": name, "book_count": int(book_count or 0), "copy_count": int(copy_count or 0), "borrow_90d": int(borrow_90d or 0), "reserve_90d": int(reserve_90d or 0), "hot_count": int(hot_count or 0), "cold_count": int(cold_count or 0), "percentage": round((int(book_count or 0) / total_category_books), 4) if total_category_books else 0}
                for category_id, name, book_count, copy_count, borrow_90d, reserve_90d, hot_count, cold_count in category_rows
            ]
        },
    }


def reader_analytics(db: Session, *, business_date: date | str | None = None) -> dict:
    as_of = get_business_date(db, business_date)
    profile = library_profile(db)
    operations = operation_snapshot(db, business_date=as_of)
    by_type = {}
    for rtype in ["child", "teen", "adult", "senior", "institution"]:
        by_type[rtype] = int(db.scalar(select(func.count(ReaderAccount.id)).where(ReaderAccount.reader_type_code == rtype)) or 0)
    suspended = int(db.scalar(select(func.count(ReaderAccount.id)).where(ReaderAccount.status == "suspended")) or 0)
    credit_score = cast(ReaderAccount.credit_score, Integer)
    credit_90_100 = int(db.scalar(select(func.count(ReaderAccount.id)).where(credit_score >= 90)) or 0)
    credit_80_89 = int(db.scalar(select(func.count(ReaderAccount.id)).where(credit_score >= 80, credit_score < 90)) or 0)
    credit_70_79 = int(db.scalar(select(func.count(ReaderAccount.id)).where(credit_score >= 70, credit_score < 80)) or 0)
    credit_60_69 = int(db.scalar(select(func.count(ReaderAccount.id)).where(credit_score >= 60, credit_score < 70)) or 0)
    credit_below_60 = int(db.scalar(select(func.count(ReaderAccount.id)).where(credit_score < 60)) or 0)
    credit_limited = credit_60_69 + credit_below_60 + suspended
    registered_count = int(db.scalar(select(func.count(ReaderAccount.id))) or 0)
    active_reader_ids = db.scalars(select(Loan.reader_id).where(func.date(Loan.borrowed_at) >= str(as_of - timedelta(days=30)), func.date(Loan.borrowed_at) <= str(as_of)).distinct()).all()
    top_rows = db.execute(select(ReaderAccount, func.count(Loan.id).label("borrow_count")).join(Loan, ReaderAccount.id == Loan.reader_id).group_by(ReaderAccount.id).order_by(func.count(Loan.id).desc()).limit(10)).all()
    overdue_rows = db.execute(select(ReaderAccount, func.count(Loan.id).label("overdue_count"), func.min(Loan.due_at).label("oldest_due_date")).join(Loan, ReaderAccount.id == Loan.reader_id).where(Loan.status == "overdue").group_by(ReaderAccount.id).order_by(func.count(Loan.id).desc()).limit(10)).all()
    activity_count_rows = db.execute(select(ReaderAccount.id, func.count(Loan.id).label("borrow_count")).outerjoin(Loan, ReaderAccount.id == Loan.reader_id).group_by(ReaderAccount.id)).all()
    activity_levels = [
        {"name": "楂橀娲昏穬锛堚墺10娆★級", "count": 0},
        {"name": "涓椿璺冿紙3-9娆★級", "count": 0},
        {"name": "浣庢椿璺冿紙1-2娆★級", "count": 0},
        {"name": "娌夌潯锛?娆★級", "count": 0},
    ]
    for _reader_id, borrow_count in activity_count_rows:
        count = int(borrow_count or 0)
        if count >= 10:
            activity_levels[0]["count"] += 1
        elif count >= 3:
            activity_levels[1]["count"] += 1
        elif count >= 1:
            activity_levels[2]["count"] += 1
        else:
            activity_levels[3]["count"] += 1
    for item in activity_levels:
        item["percent"] = (item["count"] / registered_count) if registered_count else 0
    preference_rows = db.execute(
        select(BookCategory.id, BookCategory.category_name, func.count(Loan.id).label("borrow_count"))
        .join(Book, Book.category_id == BookCategory.id)
        .join(Loan, Loan.book_id == Book.id)
        .where(func.date(Loan.borrowed_at) >= str(as_of - timedelta(days=90)), func.date(Loan.borrowed_at) <= str(as_of))
        .group_by(BookCategory.id, BookCategory.category_name)
        .order_by(func.count(Loan.id).desc())
        .limit(5)
    ).all()
    preference_total = sum(int(count or 0) for _category_id, _name, count in preference_rows)
    trend_dates = date_window(as_of, 7)
    new_reader_trend = [
        int(db.scalar(select(func.count(ReaderAccount.id)).where(func.date(ReaderAccount.created_at) == str(day))) or 0)
        for day in trend_dates
    ]
    active_reader_trend = [
        int(db.scalar(select(func.count(func.distinct(Loan.reader_id))).where(func.date(Loan.borrowed_at) >= str(day - timedelta(days=30)), func.date(Loan.borrowed_at) <= str(day))) or 0)
        for day in trend_dates
    ]
    overdue_payload = []
    for reader, count, oldest_due_date in overdue_rows:
        if isinstance(oldest_due_date, datetime):
            oldest_due_date = oldest_due_date.date()
        overdue_days = max((as_of - oldest_due_date).days, 0) if oldest_due_date else 0
        overdue_payload.append({"reader_id": reader.id, "reader_code": reader.reader_code, "name": reader.name, "overdue_count": int(count), "overdue_days": overdue_days})
    return {
        "business_date": str(as_of),
        "registered_reader_count": profile["registered_reader_count"],
        "monthly_active_reader_count": profile["monthly_active_reader_count"],
        "today_new_reader_count": operations["today_new_reader_count"],
        "registered_reader_database_count": registered_count,
        "monthly_active_reader_database_count": len(active_reader_ids),
        "reader_type_distribution": {"items": [{"name": key, "label": {"child": "儿童读者", "teen": "青少年读者", "adult": "成人读者", "senior": "老年读者", "institution": "机构账号"}[key], "count": value, "percentage": round(value / registered_count, 4) if registered_count else 0} for key, value in by_type.items()]},
        "credit_score_distribution": {"items": [
            {"name": "very_high", "label": "90-100", "count": credit_90_100, "percentage": round(credit_90_100 / registered_count, 4) if registered_count else 0},
            {"name": "high", "label": "80-89", "count": credit_80_89, "percentage": round(credit_80_89 / registered_count, 4) if registered_count else 0},
            {"name": "good", "label": "70-79", "count": credit_70_79, "percentage": round(credit_70_79 / registered_count, 4) if registered_count else 0},
            {"name": "mid", "label": "60-69", "count": credit_60_69, "percentage": round(credit_60_69 / registered_count, 4) if registered_count else 0},
            {"name": "low", "label": "60 浠ヤ笅", "count": credit_below_60, "percentage": round(credit_below_60 / registered_count, 4) if registered_count else 0},
        ]},
        "top_active_readers": [{"reader_id": reader.id, "reader_code": reader.reader_code, "name": reader.name, "borrow_count": int(count)} for reader, count in top_rows],
        "readers_with_overdue_risk": overdue_payload,
        "reader_activity_levels": {"items": activity_levels},
        "activity_levels": activity_levels,
        "reader_preference_top5": {"items": [{"category_id": category_id, "name": name, "borrow_count": int(count or 0), "percent": (int(count or 0) / preference_total) if preference_total else 0} for category_id, name, count in preference_rows]},
        "reader_activity_trend": chart([str(day) for day in trend_dates], [{"name": "new_readers", "label": "新增读者", "data": new_reader_trend}, {"name": "active_readers", "label": "活跃读者", "data": active_reader_trend}]),
        "by_type": by_type,
        "credit_buckets": {"low": credit_below_60, "mid": credit_60_69 + credit_70_79, "high": credit_80_89 + credit_90_100},
        "credit_limited_count": credit_limited,
        "normal_reader_count": max(profile["registered_reader_count"] - credit_limited - suspended, 0),
        "suspended_count": suspended,
    }


def risk_analytics(db: Session, *, business_date: date | str | None = None) -> dict:
    operations = operation_snapshot(db, business_date=business_date)
    by_severity = {}
    for severity in ["low", "normal", "medium", "high", "critical"]:
        by_severity[severity] = int(db.scalar(select(func.count(RiskWarning.id)).where(RiskWarning.severity == severity, RiskWarning.status.in_(OPEN_RISK_STATUSES))) or 0)
    pending_tasks = int(db.scalar(select(func.count(WorkTask.id)).where(WorkTask.status.in_(ACTIVE_TASK_STATUSES))) or 0)
    ai_tasks = int(db.scalar(select(func.count(WorkTask.id)).where(WorkTask.source_type.in_(["ai", "ai_admin", "ai_review"]))) or 0)
    return {"active_count": operations["risk_warning_count"], "by_severity": by_severity, "pending_task_count": pending_tasks, "ai_task_count": ai_tasks}
