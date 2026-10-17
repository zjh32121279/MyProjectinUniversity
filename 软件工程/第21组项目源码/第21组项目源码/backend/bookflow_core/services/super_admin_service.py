from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from bookflow_core.core.time import now
from bookflow_core.models import (
    AICapability,
    AdminLoginEvent,
    AuditEvent,
    Book,
    BookCirculationStats,
    BookCopy,
    CirculationRule,
    Loan,
    ReaderAccount,
    Reservation,
    SystemSetting,
)
from bookflow_core.services.super_admin_ai_rules import (
    ai_rule_management,
)
from bookflow_core.services.super_admin_audit import (
    audit_events,
    readable_audit_action,
)
from bookflow_core.services.super_admin_common import (
    _count,
    ai_rule_enabled_rate,
    today_window,
)

__all__ = [
    "governance_overview",
    "audit_events",
    "ai_rule_management",
]

CLOSED_LOAN_STATUSES = {"returned", "closed", "cancelled", "completed", "lost"}
CLOSED_RESERVATION_STATUSES = {"cancelled", "expired", "completed", "fulfilled", "closed"}


def _date_count(db: Session, model, column, start, end) -> int:
    return _count(db, select(func.count(model.id)).where(column >= start, column < end))


def _active_loan_filter():
    return Loan.returned_at.is_(None), or_(Loan.status.is_(None), ~Loan.status.in_(CLOSED_LOAN_STATUSES))


def _active_reservation_filter():
    return or_(Reservation.status.is_(None), ~Reservation.status.in_(CLOSED_RESERVATION_STATUSES))


def _delta_pair(db: Session, model, column, day_start, day_end) -> dict:
    yesterday_start = day_start - timedelta(days=1)
    today_value = _date_count(db, model, column, day_start, day_end)
    yesterday_value = _date_count(db, model, column, yesterday_start, day_start)
    return {"value": today_value, "delta": today_value - yesterday_value}


def _trend_7d(db: Session, day_start) -> list[dict]:
    rows: list[dict] = []
    for index in range(6, -1, -1):
        start = day_start - timedelta(days=index)
        end = start + timedelta(days=1)
        rows.append(
            {
                "date": start.strftime("%m-%d"),
                "borrow": _date_count(db, Loan, Loan.borrowed_at, start, end),
                "return": _date_count(db, Loan, Loan.returned_at, start, end),
            }
        )
    return rows


def _copy_status_distribution(db: Session) -> list[dict]:
    rows = db.execute(
        select(BookCopy.copy_status, BookCopy.status_name, func.count(BookCopy.id))
        .group_by(BookCopy.copy_status, BookCopy.status_name)
        .order_by(func.count(BookCopy.id).desc())
    ).all()
    return [
        {
            "key": status or name or f"status_{index}",
            "label": name or status or "未标记",
            "value": int(count or 0),
        }
        for index, (status, name, count) in enumerate(rows)
        if int(count or 0) > 0
    ]


def _hot_books(db: Session, limit: int = 5) -> list[dict]:
    rows = db.execute(
        select(BookCirculationStats, Book)
        .join(Book, Book.id == BookCirculationStats.book_id)
        .order_by(BookCirculationStats.borrow_90d.desc(), BookCirculationStats.reserve_90d.desc(), Book.title)
        .limit(limit)
    ).all()
    if rows:
        return [
            {
                "rank": index + 1,
                "book_id": book.id,
                "title": book.title or stats.title_snapshot or "未命名图书",
                "author": book.author or "",
                "publisher": book.publisher or "",
                "cover_url": book.cover_url or "",
                "borrow_count": int(stats.borrow_90d or 0),
                "reservation_count": int(stats.reserve_90d or 0),
            }
            for index, (stats, book) in enumerate(rows)
        ]

    fallback = db.execute(
        select(Book, func.count(Loan.id))
        .join(Loan, Loan.book_id == Book.id)
        .group_by(Book.id)
        .order_by(func.count(Loan.id).desc(), Book.title)
        .limit(limit)
    ).all()
    return [
        {
            "rank": index + 1,
            "book_id": book.id,
            "title": book.title or "未命名图书",
            "author": book.author or "",
            "publisher": book.publisher or "",
            "cover_url": book.cover_url or "",
            "borrow_count": int(count or 0),
            "reservation_count": 0,
        }
        for index, (book, count) in enumerate(fallback)
    ]


def _reader_activity(db: Session, day_start, day_end) -> dict:
    total = _count(db, select(func.count(ReaderAccount.id)))
    active_statuses = {"active", "normal", "enabled"}
    active_accounts = _count(
        db,
        select(func.count(ReaderAccount.id)).where(
            or_(ReaderAccount.status.in_(active_statuses), ReaderAccount.active_90d.in_({"1", "true", "yes", "Y", "y"}))
        ),
    )
    today_borrow_readers = _count(
        db,
        select(func.count(func.distinct(Loan.reader_id))).where(Loan.borrowed_at >= day_start, Loan.borrowed_at < day_end),
    )
    new_readers = _count(
        db,
        select(func.count(ReaderAccount.id)).where(ReaderAccount.registered_at >= day_start, ReaderAccount.registered_at < day_end),
    )
    return {
        "total": total,
        "active": active_accounts,
        "active_ratio": round(active_accounts * 100 / total) if total else 0,
        "today_active": today_borrow_readers,
        "today_new": new_readers,
    }


def _activity_actor_label(value: str | None) -> str:
    text = str(value or "").strip()
    return {
        "overdue_scheduler": "逾期调度器",
        "system": "系统",
        "admin": "管理员",
        "super_admin": "超级管理员",
    }.get(text, text or "-")


def _activity_result(value: str | None) -> str:
    text = str(value or "").strip()
    if text in {"login_success", "admin_login_success"}:
        return "success"
    if text in {"login_failed", "admin_login_failed"}:
        return "failed"
    return text or "-"


def _recent_activities(db: Session, limit: int = 8) -> list[dict]:
    audit_rows = db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)).all()
    login_rows = db.scalars(select(AdminLoginEvent).order_by(AdminLoginEvent.id.desc()).limit(limit)).all()
    activities: list[dict] = []
    for row in audit_rows:
        activities.append(
            {
                "id": f"audit-{row.id}",
                "kind": "audit",
                "title": readable_audit_action(row.action),
                "actor": _activity_actor_label(row.actor_code or row.actor_type),
                "result": _activity_result(row.result),
                "created_at": row.created_at,
            }
        )
    for row in login_rows:
        title = "管理员登录成功" if row.event_type == "login_success" else "管理员登录事件"
        if row.event_type == "login_failed":
            title = "管理员登录失败"
        activities.append(
            {
                "id": f"login-{row.id}",
                "kind": "login",
                "title": title,
                "actor": _activity_actor_label(row.admin_code),
                "result": _activity_result(row.result or row.event_type),
                "created_at": row.created_at,
            }
        )
    return sorted(activities, key=lambda item: str(item.get("created_at") or ""), reverse=True)[:limit]


def _system_health(db: Session) -> dict:
    db_ok = _count(db, select(func.count(Book.id))) >= 0
    ai_total = _count(db, select(func.count(AICapability.id)))
    ai_enabled = _count(db, select(func.count(AICapability.id)).where(AICapability.is_enabled == True))
    rules_total = (
        _count(db, select(func.count(CirculationRule.id)))
        + _count(db, select(func.count(SystemSetting.id)))
        + ai_total
    )
    rules_enabled = (
        _count(db, select(func.count(CirculationRule.id)).where(CirculationRule.is_active == True))
        + _count(db, select(func.count(SystemSetting.id)).where(SystemSetting.is_active == True))
        + ai_enabled
    )
    export_root = (Path(__file__).resolve().parents[3] / "artifacts").resolve()
    services = [
        {"key": "database", "label": "数据库", "status": "normal" if db_ok else "warning", "text": "正常" if db_ok else "需检查"},
        {
            "key": "rules",
            "label": "规则配置",
            "status": "normal" if rules_total == 0 or rules_enabled > 0 else "warning",
            "text": f"{rules_enabled}/{rules_total} 生效" if rules_total else "暂无规则",
        },
        {
            "key": "ai",
            "label": "AI 服务",
            "status": "normal" if ai_total == 0 or ai_enabled > 0 else "warning",
            "text": f"{ai_enabled}/{ai_total} 启用" if ai_total else "未配置",
        },
        {
            "key": "export",
            "label": "导出目录",
            "status": "normal" if export_root.parent.exists() else "warning",
            "text": "可用" if export_root.parent.exists() else "需检查",
        },
    ]
    normal_count = sum(1 for item in services if item["status"] == "normal")
    return {
        "status": "normal" if normal_count == len(services) else "warning",
        "score": round(normal_count * 100 / len(services)),
        "services": services,
    }


def governance_overview(db: Session) -> dict:
    day_start, day_end = today_window()
    yesterday_start = day_start - timedelta(days=1)

    total_books = _count(db, select(func.count(Book.id)))
    total_books_yesterday = _count(db, select(func.count(Book.id)).where(Book.created_at < day_start))
    total_copies = _count(db, select(func.count(BookCopy.id)))
    total_copies_yesterday = _count(db, select(func.count(BookCopy.id)).where(BookCopy.created_at < day_start))
    readers_total = _count(db, select(func.count(ReaderAccount.id)))
    readers_yesterday = _count(db, select(func.count(ReaderAccount.id)).where(ReaderAccount.created_at < day_start))

    current_borrowed = _count(db, select(func.count(Loan.id)).where(*_active_loan_filter()))
    current_borrowed_yesterday = _count(
        db,
        select(func.count(Loan.id)).where(
            Loan.borrowed_at < day_start,
            or_(Loan.returned_at.is_(None), Loan.returned_at >= day_start),
            or_(Loan.status.is_(None), ~Loan.status.in_(CLOSED_LOAN_STATUSES)),
        ),
    )
    today_borrow = _delta_pair(db, Loan, Loan.borrowed_at, day_start, day_end)
    today_return = _delta_pair(db, Loan, Loan.returned_at, day_start, day_end)

    reservation_count = _count(db, select(func.count(Reservation.id)).where(_active_reservation_filter()))
    reservation_yesterday = _count(
        db,
        select(func.count(Reservation.id)).where(
            Reservation.created_at < day_start,
            or_(Reservation.status.is_(None), ~Reservation.status.in_(CLOSED_RESERVATION_STATUSES)),
        ),
    )
    overdue_count = _count(
        db,
        select(func.count(Loan.id)).where(
            *_active_loan_filter(),
            or_(Loan.status == "overdue", Loan.due_at < day_end),
        ),
    )
    overdue_yesterday = _count(
        db,
        select(func.count(Loan.id)).where(
            Loan.borrowed_at < day_start,
            or_(Loan.returned_at.is_(None), Loan.returned_at >= day_start),
            or_(Loan.status.is_(None), ~Loan.status.in_(CLOSED_LOAN_STATUSES)),
            or_(Loan.status == "overdue", Loan.due_at < day_start),
        ),
    )

    audit_events_today = _count(
        db,
        select(func.count(AuditEvent.id)).where(AuditEvent.created_at >= day_start, AuditEvent.created_at < day_end),
    )
    audit_events_yesterday = _count(
        db,
        select(func.count(AuditEvent.id)).where(AuditEvent.created_at >= yesterday_start, AuditEvent.created_at < day_start),
    )

    return {
        "updated_at": now(),
        "kpis": {
            "totalBooks": {"value": total_books, "delta": total_books - total_books_yesterday},
            "totalCopies": {"value": total_copies, "delta": total_copies - total_copies_yesterday},
            "readersTotal": {"value": readers_total, "delta": readers_total - readers_yesterday},
            "currentBorrowed": {"value": current_borrowed, "delta": current_borrowed - current_borrowed_yesterday},
            "todayBorrow": today_borrow,
            "todayReturn": today_return,
            "reservationCount": {"value": reservation_count, "delta": reservation_count - reservation_yesterday},
            "overdueCount": {"value": overdue_count, "delta": overdue_count - overdue_yesterday},
            "auditEventsToday": {"value": audit_events_today, "delta": audit_events_today - audit_events_yesterday},
            "aiRuleEnabledRate": {"value": ai_rule_enabled_rate(db), "delta": 0},
        },
        "borrowReturnTrend": _trend_7d(db, day_start),
        "copyStatusDistribution": _copy_status_distribution(db),
        "hotBooks": _hot_books(db),
        "readerActivity": _reader_activity(db, day_start, day_end),
        "systemActivities": _recent_activities(db),
        "systemHealth": _system_health(db),
    }
