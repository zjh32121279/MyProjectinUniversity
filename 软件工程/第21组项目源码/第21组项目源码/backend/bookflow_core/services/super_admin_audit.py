from __future__ import annotations

from datetime import datetime, time

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from bookflow_core.models import (
    AuditEvent,
)
from bookflow_core.services.audit_service import audit_to_dict
from bookflow_core.services.super_admin_common import (
    risk_label,
    risk_from_text,
    result_label,
)


def _date_bound(value: str | None, *, end: bool = False) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text[:10])
    except ValueError:
        return None
    return datetime.combine(parsed.date(), time.max if end else time.min)


def audit_event_to_dict(row: AuditEvent) -> dict:
    item = audit_to_dict(row)
    risk_level = risk_from_text(row.action, row.result, row.detail_json)
    item.update(
        {
            "riskLevel": risk_level,
            "riskLabel": risk_label(risk_level),
            "eventType": row.action,
            "eventTypeLabel": readable_audit_action(row.action),
            "actor": row.actor_code,
            "targetLabel": f"{row.target_entity_type} {row.target_entity_id}".strip() or "-",
            "resultLabel": result_label(row.result),
            "ip_address": row.ip_address or "",
            "user_agent": row.user_agent or "",
            "request_id": row.request_id or "",
        }
    )
    return item


def readable_audit_action(action: str | None) -> str:
    value = action or ""
    return {
        "scan_overdues": "逾期借阅扫描",
        "admin_login_success": "管理员登录成功",
        "admin_login_failed": "管理员登录失败",
        "login_success": "管理员登录成功",
        "login_failed": "管理员登录失败",
        "audit_export": "导出审计摘要",
        "data_export": "导出数据",
        "update_borrow_rule": "修改借阅规则",
        "update_system_setting": "修改系统规则",
        "update_circulation_policy": "修改流通策略",
        "set_admin_status": "调整管理员状态",
        "create_risk_warning": "创建风险预警",
        "resolve_risk_warning": "处理风险预警",
    }.get(value, value.replace("_", " ") or "-")


def audit_events(db: Session, *, limit: int = 50, offset: int = 0, actor_id: str | None = None, result: str | None = None, risk_level: str | None = None, date_from: str | None = None, date_to: str | None = None, keyword: str | None = None, module: str | None = None) -> dict:
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    stmt = select(AuditEvent)
    count_stmt = select(func.count(AuditEvent.id))
    filters = []
    if actor_id:
        filters.append(AuditEvent.actor_code == actor_id)
    if result:
        filters.append(AuditEvent.result == result)
    if module:
        text = module.strip()
        filters.append(or_(AuditEvent.action.contains(text), AuditEvent.target_entity_type.contains(text)))
    if keyword:
        text = keyword.strip()
        filters.append(
            or_(
                AuditEvent.actor_code.contains(text),
                AuditEvent.action.contains(text),
                AuditEvent.target_entity_type.contains(text),
                cast(AuditEvent.target_entity_id, String).contains(text),
                AuditEvent.result.contains(text),
            )
        )
    start = _date_bound(date_from)
    end = _date_bound(date_to, end=True)
    if start:
        filters.append(AuditEvent.created_at >= start)
    if end:
        filters.append(AuditEvent.created_at <= end)
    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)
    total = int(db.scalar(count_stmt) or 0)
    rows = [audit_event_to_dict(row) for row in db.scalars(stmt.order_by(AuditEvent.id.desc()).offset(offset).limit(limit)).all()]
    if risk_level:
        rows = [row for row in rows if row.get("riskLevel") == risk_level]
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


