from __future__ import annotations

from sqlalchemy import Integer, cast, select, func
from sqlalchemy.orm import Session
from bookflow_core.models import RiskWarning, Book, BookCirculationStats, BookCopy, ReaderAccount, Loan
from bookflow_core.services.common import write_audit
from bookflow_core.services.statistics_service import OPEN_RISK_STATUSES, UNAVAILABLE_COPY_STATUSES


def _risk_code(prefix: str) -> str:
    from datetime import datetime, timezone
    return f"{prefix}-{int(datetime.now(timezone.utc).timestamp() * 1000000)}"


def list_risk_warnings(db: Session, *, status: str | None = None, severity: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    stmt = select(RiskWarning)
    if status:
        stmt = stmt.where(RiskWarning.status.in_(OPEN_RISK_STATUSES) if status == "active" else RiskWarning.status == status)
    if severity:
        stmt = stmt.where(RiskWarning.severity == severity)
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    items = db.scalars(stmt.order_by(RiskWarning.id.desc()).offset(offset).limit(limit)).all()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def create_risk_warning(
    db: Session,
    *,
    warning_type: str,
    severity: str,
    title: str,
    description: str = "",
    source_type: str = "system",
    related_entity_type: str = "",
    related_entity_id: str = "",
    created_task_id: int | None = None,
    actor_type: str = "system",
    actor_id: str = "system",
    commit: bool = True,
) -> RiskWarning:
    try:
        row = RiskWarning(
            warning_code=_risk_code("RISK"),
            warning_type=warning_type,
            severity=severity,
            title=title,
            description=description,
            status="open",
            source_type=source_type,
            related_entity_type=related_entity_type,
            related_entity_id=int(related_entity_id) if str(related_entity_id).isdigit() else None,
            created_task_id=created_task_id,
        )
        db.add(row)
        db.flush()
        from bookflow_core.services.task_service import create_task

        priority = "urgent" if severity in {"critical", "high"} else "high" if severity == "medium" else "normal"
        task = create_task(
            db,
            title=title,
            description=description,
            priority=priority,
            source_type="risk",
            task_group="risk",
            related_entity_type=related_entity_type or "risk_warning",
            related_entity_id=related_entity_id or row.warning_code,
            risk_warning_code=row.warning_code,
            requires_human_confirmation=severity in {"critical", "high"},
            source_payload={
                "kernel_intent": "risk_warning",
                "warning_code": row.warning_code,
                "warning_type": warning_type,
                "severity": severity,
                "related_entity_type": related_entity_type,
                "related_entity_id": related_entity_id,
            },
            execution_context={"entrypoint": "create_risk_warning"},
            actor_type=actor_type,
            actor_id=actor_id,
            commit=False,
        )
        row.created_task_id = task.id
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="create_risk_warning", target_table="risk_warnings", target_id=row.warning_code, detail={"warning_type": warning_type, "severity": severity})
        if commit:
            db.commit()
            db.refresh(row)
        return row
    except Exception:
        if commit:
            db.rollback()
        raise


def resolve_risk_warning(db: Session, warning_code: str, *, reason: str = "resolved", actor_type: str = "admin", actor_id: str = "admin", commit: bool = True) -> RiskWarning:
    from bookflow_core.core.exceptions import NotFoundError, BusinessRuleError
    try:
        row = db.scalar(select(RiskWarning).where(RiskWarning.warning_code == warning_code))
        if not row:
            raise NotFoundError("Risk warning not found.", details={"warning_code": warning_code})
        if row.status not in OPEN_RISK_STATUSES:
            raise BusinessRuleError("Only open warning can be resolved.", details={"status": row.status})
        row.status = "resolved"
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="resolve_risk_warning", target_table="risk_warnings", target_id=warning_code, detail={"reason": reason})
        if commit:
            db.commit()
            db.refresh(row)
        return row
    except Exception:
        if commit:
            db.rollback()
        raise


def refresh_risk_warnings(db: Session, *, actor_type: str = "system", actor_id: str = "system", commit: bool = True) -> dict:
    try:
        created = 0
        unavailable = int(db.scalar(select(func.count(BookCopy.id)).where(BookCopy.copy_status.in_(UNAVAILABLE_COPY_STATUSES))) or 0)
        if unavailable >= 1:
            create_risk_warning(db, warning_type="unavailable_copy", severity="low" if unavailable < 10 else "medium", title="存在暂不可借副本", description=f"当前 S04 副本数量：{unavailable}", actor_type=actor_type, actor_id=actor_id, commit=False)
            created += 1
        hot_low = db.execute(
            select(Book, BookCirculationStats.available_copies)
            .join(BookCirculationStats, BookCirculationStats.book_id == Book.id)
            .where(Book.circulation_type == "hot", BookCirculationStats.available_copies <= 1)
            .limit(5)
        ).all()
        for book, available_copies in hot_low:
            create_risk_warning(db, warning_type="hot_book_low_inventory", severity="medium", title="热门书可借副本不足", description=f"{book.title} 当前可借副本 {available_copies} 册。", actor_type=actor_type, actor_id=actor_id, commit=False)
            created += 1
        low_credit = int(db.scalar(select(func.count(ReaderAccount.id)).where(cast(ReaderAccount.credit_score, Integer) < 60)) or 0)
        if low_credit:
            create_risk_warning(db, warning_type="low_credit_reader", severity="medium", title="存在低信用读者", description=f"低于 60 分读者数量：{low_credit}", actor_type=actor_type, actor_id=actor_id, commit=False)
            created += 1
        overdue = int(db.scalar(select(func.count(Loan.id)).where(Loan.status == "overdue")) or 0)
        if overdue:
            create_risk_warning(db, warning_type="active_overdue", severity="high", title="存在当前逾期借阅", description=f"当前逾期借阅记录数量：{overdue}", actor_type=actor_type, actor_id=actor_id, commit=False)
            created += 1
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="refresh_risk_warnings", target_table="risk_warnings", target_id="batch", detail={"created": created})
        if commit:
            db.commit()
        return {"created": created}
    except Exception:
        if commit:
            db.rollback()
        raise


def risk_to_dict(row: RiskWarning) -> dict:
    return {
        "warning_code": row.warning_code,
        "warning_type": row.warning_type,
        "severity": row.severity,
        "title": row.title,
        "description": row.description,
        "status": row.status,
        "source_type": row.source_type,
        "related_entity_type": row.related_entity_type,
        "related_entity_id": row.related_entity_id,
        "created_task_id": row.created_task_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }



