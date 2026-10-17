from __future__ import annotations

import json
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from bookflow_core.models import AuditEvent


def audit_to_dict(row: AuditEvent) -> dict:
    try:
        detail = json.loads(row.detail_json or '{}')
    except json.JSONDecodeError:
        detail = {"raw": row.detail_json}
    return {
        "id": row.id,
        "actor_type": row.actor_type,
        "actor_id": row.actor_code,
        "action": row.action,
        "target_table": row.target_entity_type,
        "target_id": row.target_entity_id,
        "result": row.result,
        "detail": detail,
        "created_at": row.created_at,
    }


def list_audit_logs(
    db: Session,
    *,
    actor_type: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    target_table: str | None = None,
    result: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    stmt = select(AuditEvent)
    count_stmt = select(func.count(AuditEvent.id))
    filters = []
    if actor_type:
        filters.append(AuditEvent.actor_type == actor_type)
    if actor_id:
        filters.append(AuditEvent.actor_code == actor_id)
    if action:
        filters.append(AuditEvent.action == action)
    if target_table:
        filters.append(AuditEvent.target_entity_type == target_table)
    if result:
        filters.append(AuditEvent.result == result)
    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(AuditEvent.id.desc()).limit(limit).offset(offset)).all()
    return {"items": [audit_to_dict(r) for r in rows], "total": int(total), "limit": limit, "offset": offset}


def audit_summary(db: Session) -> dict:
    by_actor = {k or "": int(v) for k, v in db.execute(select(AuditEvent.actor_type, func.count(AuditEvent.id)).group_by(AuditEvent.actor_type)).all()}
    by_result = {k or "": int(v) for k, v in db.execute(select(AuditEvent.result, func.count(AuditEvent.id)).group_by(AuditEvent.result)).all()}
    top_actions = [
        {"action": action, "count": int(count)}
        for action, count in db.execute(select(AuditEvent.action, func.count(AuditEvent.id)).group_by(AuditEvent.action).order_by(func.count(AuditEvent.id).desc()).limit(10)).all()
    ]
    total = db.scalar(select(func.count(AuditEvent.id))) or 0
    return {"total": int(total), "by_actor_type": by_actor, "by_result": by_result, "top_actions": top_actions}


