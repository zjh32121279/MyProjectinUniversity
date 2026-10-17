from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from bookflow_core.models import (
    ReaderAccount,
    Loan,
    OverdueCase,
    Reservation,
    NotificationDelivery,
    NotificationMessage,
    WorkTask,
    RiskWarning,
    CirculationRule,
    SystemSetting,
    CirculationPolicy,
    Book,
    BookCopy,
)
from bookflow_core.services.statistics_service import ACTIVE_RESERVATION_STATUSES, ACTIVE_TASK_STATUSES, get_business_date
from bookflow_core.services.dashboard_service import (
    admin_dashboard,
    analytics_overview,
    collection_health,
    circulation_analytics,
    reader_analytics,
    risk_analytics,
    ai_efficiency,
)
from bookflow_core.services.notification_service import message_to_dict
from bookflow_core.services.reader_service import reader_borrow_suspended


def _count(db: Session, stmt) -> int:
    return int(db.scalar(stmt) or 0)


def overdue_summary(db: Session, *, limit: int = 10) -> dict:
    """Return active overdue structure with concrete records and risk reasons."""
    active_overdue_cases = db.scalars(
        select(OverdueCase)
        .where(OverdueCase.status == "active")
        .order_by(OverdueCase.overdue_days.desc(), OverdueCase.id.desc())
        .limit(limit)
    ).all()
    items: list[dict] = []
    for row in active_overdue_cases:
        reader = db.get(ReaderAccount, row.reader_id)
        borrow = db.get(Loan, row.loan_id)
        copy = db.get(BookCopy, row.copy_id)
        book = db.get(Book, borrow.book_id) if borrow else None
        items.append(
            {
                "overdue_id": row.id,
                "reader_code": reader.reader_code if reader else "",
                "reader_name": reader.name if reader else "",
                "book_code": book.book_code if book else "",
                "title": book.title if book else "",
                "copy_code": copy.copy_code if copy else "",
                "overdue_days": row.overdue_days,
                "penalty_score": row.penalty_score,
                "status": row.status,
            }
        )
    borrowed_overdue_count = _count(db, select(func.count(Loan.id)).where(Loan.status == "overdue"))
    active_overdue_count = _count(db, select(func.count(OverdueCase.id)).where(OverdueCase.status == "active"))
    severe_count = _count(db, select(func.count(OverdueCase.id)).where(OverdueCase.status == "active", OverdueCase.overdue_days >= 15))
    return {
        "active_overdue_count": active_overdue_count,
        "loan_overdue_count": borrowed_overdue_count,
        "severe_overdue_count": severe_count,
        "items": items,
        "reason": "存在 15 天以上逾期记录，应优先生成管理员任务和读者提醒。" if severe_count else "当前逾期主要为普通逾期，按规则提醒即可。",
    }


def notification_summary(db: Session) -> dict:
    as_of = get_business_date(db)
    pending_send = _count(
        db,
        select(func.count(NotificationMessage.id)).where(
            NotificationMessage.lifecycle_status.in_(["draft", "queued"])
        ),
    )
    scheduled = _count(
        db,
        select(func.count(NotificationMessage.id)).where(
            NotificationMessage.scheduled_at != None,
            NotificationMessage.lifecycle_status.in_(["draft", "queued"]),
        ),
    )
    sent = _count(
        db,
        select(func.count(NotificationDelivery.id)).where(
            NotificationDelivery.delivery_status == "sent"
        ),
    )
    unread = _count(
        db,
        select(func.count(NotificationDelivery.id)).where(
            NotificationDelivery.delivery_status == "sent",
            NotificationDelivery.read_status == "unread",
            NotificationDelivery.archived_at == None,
        ),
    )
    read = _count(
        db,
        select(func.count(NotificationDelivery.id)).where(
            NotificationDelivery.delivery_status == "sent",
            NotificationDelivery.read_status == "read",
        ),
    )
    sent_today = _count(
        db,
        select(func.count(NotificationDelivery.id)).where(
            NotificationDelivery.delivery_status == "sent",
            func.date(NotificationDelivery.sent_at) == str(as_of),
        ),
    )
    by_type = {}
    for ntype, aliases in {
        "system": ["system"],
        "reservation": ["reservation", "reservation_ready"],
        "task": ["admin_task", "task", "risk_task"],
        "due": ["due", "due_reminder"],
        "overdue": ["overdue", "overdue_reminder"],
        "ai": ["ai", "ai_review"],
        "general": ["general"],
    }.items():
        by_type[ntype] = _count(
            db,
            select(func.count(NotificationMessage.id)).where(
                NotificationMessage.notification_type.in_(aliases)
            ),
        )
    latest = db.scalars(select(NotificationMessage).order_by(NotificationMessage.id.desc()).limit(10)).all()
    return {
        "business_date": str(as_of),
        "pending_count": unread,
        "unread_count": unread,
        "read_count": read,
        "sent_count": sent,
        "pending_send_count": pending_send,
        "scheduled_count": scheduled,
        "sent_today_count": sent_today,
        "by_type": by_type,
        "latest": [message_to_dict(n, db) for n in latest],
    }


def task_summary(db: Session) -> dict:
    by_status = {
        status: _count(db, select(func.count(WorkTask.id)).where(WorkTask.status == status))
        for status in ["pending", "ai_processing", "waiting_human", "admin_processing", "claimed", "resolved", "cancelled"]
    }
    by_priority = {
        priority: _count(db, select(func.count(WorkTask.id)).where(WorkTask.priority == priority, WorkTask.status.in_(ACTIVE_TASK_STATUSES)))
        for priority in ["low", "normal", "high", "urgent"]
    }
    by_group = {
        group: _count(db, select(func.count(WorkTask.id)).where(WorkTask.task_group == group, WorkTask.status.in_(ACTIVE_TASK_STATUSES)))
        for group in ["borrow", "exception", "shelving", "review", "notification", "other", "unknown"]
    }
    latest = db.scalars(select(WorkTask).order_by(WorkTask.id.desc()).limit(10)).all()
    return {
        **by_status,
        "high_priority": by_priority["high"] + by_priority["urgent"],
        "pending_borrow_review": by_group["borrow"],
        "pending_return_confirm": by_group["shelving"] + by_group["other"] + by_group["unknown"],
        "exception_count": by_group["exception"] + by_status["waiting_human"],
        "today_completed": by_status["resolved"],
        "by_status": by_status,
        "by_group": by_group,
        "active_priority": by_priority,
        "latest": [
            {
                "task_code": t.task_code,
                "title": t.title,
                "status": t.status,
                "priority": t.priority,
                "task_group": t.task_group,
                "source_type": t.source_type,
            }
            for t in latest
        ],
    }


def rule_summary(db: Session) -> dict:
    rules = db.scalars(select(CirculationRule).where(CirculationRule.is_active == True).order_by(CirculationRule.reader_type_code, CirculationRule.circulation_type)).all()
    system_settings = db.scalars(select(SystemSetting).where(SystemSetting.is_active == True).order_by(SystemSetting.setting_key)).all()
    policy = db.scalar(select(CirculationPolicy).where(CirculationPolicy.is_active == True).order_by(CirculationPolicy.id.desc()))
    return {
        "borrow_rules": [
            {
                "reader_type_code": r.reader_type_code,
                "circulation_type": r.circulation_type,
                "max_borrow_count": r.max_borrow_count,
                "borrow_days": r.borrow_days,
                "max_renewals": r.max_renewals,
            }
            for r in rules
        ],
        "system_settings": [{"setting_key": r.setting_key, "setting_value": r.setting_value, "value_type": r.value_type} for r in system_settings],
        "circulation_policy": {
            "hot_borrow_90d_threshold": policy.hot_borrow_90d_threshold if policy else None,
            "hot_reserve_90d_threshold": policy.hot_reserve_90d_threshold if policy else None,
            "cold_borrow_365d_threshold": policy.cold_borrow_365d_threshold if policy else None,
            "cold_days_since_last_borrow_threshold": policy.cold_days_since_last_borrow_threshold if policy else None,
        },
    }


def reader_detail_summary(db: Session, *, reader_code: str) -> dict:
    reader = db.scalar(select(ReaderAccount).where(ReaderAccount.reader_code == reader_code))
    if not reader:
        return {"found": False, "reader_code": reader_code}
    active_borrow = _count(db, select(func.count(Loan.id)).where(Loan.reader_id == reader.id, Loan.status.in_(["active", "overdue"])))
    returned = _count(db, select(func.count(Loan.id)).where(Loan.reader_id == reader.id, Loan.status == "returned"))
    reservations = _count(db, select(func.count(Reservation.id)).where(Reservation.reader_id == reader.id, Reservation.status.in_(ACTIVE_RESERVATION_STATUSES)))
    return {
        "found": True,
        "reader_code": reader.reader_code,
        "name": reader.name,
        "reader_type_code": reader.reader_type_code,
        "credit_score": reader.credit_score,
        "borrow_suspended_until": reader.borrow_suspended_until,
        "borrow_suspended": reader_borrow_suspended(reader),
        "status": reader.status,
        "active_borrow_count": active_borrow,
        "returned_count": returned,
        "active_reservation_count": reservations,
    }


def dashboard_explanation(db: Session) -> dict:
    dash = admin_dashboard(db)
    health = collection_health(db)
    circulation = circulation_analytics(db)
    risks = risk_analytics(db)
    reasons: list[dict] = []
    if dash["overdue_count"] > 0:
        reasons.append({"level": "high", "area": "circulation", "reason": f"当前仍有 {dash['overdue_count']} 条逾期借阅记录。", "action": "先执行逾期扫描与逾期提醒，再处理长期逾期读者。"})
    if dash["unavailable_copy_count"] > 0:
        reasons.append({"level": "medium", "area": "collection", "reason": f"当前有 {dash['unavailable_copy_count']} 册处于 S04 暂不可借。", "action": "检查编目、修复、下架等原因，必要时生成待处理任务。"})
    if health["available_rate"] < 0.75:
        reasons.append({"level": "medium", "area": "availability", "reason": f"当前可借率为 {health['available_rate']:.2%}。", "action": "优先检查热门书副本状态和预约保留副本。"})
    if risks["active_count"] > 0:
        reasons.append({"level": "high", "area": "risk", "reason": f"当前存在 {risks['active_count']} 条活跃风险预警。", "action": "进入风险中心逐条解决或转待处理任务。"})
    if not reasons:
        reasons.append({"level": "normal", "area": "overall", "reason": "当前主要指标处于正常范围。", "action": "保持每日巡检和到期提醒。"})
    return {
        "dashboard": dash,
        "collection_health": health,
        "circulation_status": circulation["borrow_status"],
        "risk_status": risks,
        "explanations": reasons,
    }


def full_operational_brief(db: Session) -> dict:
    return {
        "overview": analytics_overview(db),
        "dashboard": admin_dashboard(db),
        "collection_health": collection_health(db),
        "circulation": circulation_analytics(db),
        "readers": reader_analytics(db),
        "risks": risk_analytics(db),
        "ai_efficiency": ai_efficiency(db),
        "overdue": overdue_summary(db, limit=5),
        "notifications": notification_summary(db),
        "tasks": task_summary(db),
    }



