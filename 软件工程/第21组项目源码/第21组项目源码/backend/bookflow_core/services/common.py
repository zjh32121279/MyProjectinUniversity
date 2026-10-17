from __future__ import annotations

import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from bookflow_core.models import AuditEvent, CopyStatusEvent, BookCopy, ActionSnapshot, AdminUser
from bookflow_core.core.time import now


def as_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, default=str, sort_keys=True)


def utc_text() -> datetime:
    """Return a Python datetime for SQLAlchemy DateTime columns.

    SQLAlchemy SQLite DateTime fields require Python date/datetime objects
    on INSERT/UPDATE; serializing happens at the dialect layer.
    """
    return now()


def _admin_id_from_code(db: Session, actor_id: str | None) -> int | None:
    if not actor_id:
        return None
    from sqlalchemy import select as _select
    row = db.scalar(_select(AdminUser).where(AdminUser.admin_code == str(actor_id)))
    return row.id if row else None


def _next_id(db: Session, model) -> int:
    from sqlalchemy import func, select as _select

    persisted = int(db.scalar(_select(func.max(model.id))) or 0)
    pending = [
        int(getattr(row, "id", 0) or 0)
        for row in db.new
        if isinstance(row, model) and getattr(row, "id", None)
    ]
    return max([persisted, *pending]) + 1


def write_audit(db: Session, *, actor_type: str, actor_id: str, action: str, target_table: str = "", target_id: str = "", result: str = "success", detail: dict | None = None) -> AuditEvent:
    code = f"AUD-{int(datetime.now(timezone.utc).timestamp() * 1000000)}"
    row = AuditEvent(
        id=_next_id(db, AuditEvent),
        audit_code=code,
        actor_type=actor_type,
        actor_admin_id=_admin_id_from_code(db, actor_id) if actor_type == "admin" else None,
        actor_code=str(actor_id or ""),
        action=action,
        target_entity_type=target_table,
        target_entity_id=str(target_id),
        result=result,
        detail_json=as_json(detail or {}),
        created_at=now(),
    )
    db.add(row)
    return row


def write_status_event(db: Session, copy: BookCopy, old_status: str, new_status: str, reason: str, actor_type: str, actor_id: str) -> CopyStatusEvent:
    row = CopyStatusEvent(
        copy_id=copy.id,
        old_status=old_status,
        new_status=new_status,
        reason=reason,
        actor_admin_id=_admin_id_from_code(db, actor_id) if actor_type == "admin" else None,
        actor_code=str(actor_id or ""),
        created_at=now(),
    )
    db.add(row)
    return row


def create_snapshot(db: Session, *, action_type: str, target_table: str, target_id: str, before: dict, after: dict, actor_type: str, actor_id: str, can_rollback: bool = True) -> ActionSnapshot:
    code = f"SNAP-{int(datetime.now(timezone.utc).timestamp() * 1000000)}"
    row = ActionSnapshot(
        id=_next_id(db, ActionSnapshot),
        snapshot_code=code,
        action_type=action_type,
        target_entity_type=target_table,
        target_entity_id=str(target_id),
        before_json=as_json(before),
        after_json=as_json(after),
        can_rollback=can_rollback,
        rolled_back=False,
        created_at=now(),
        updated_at=now(),
    )
    db.add(row)
    return row
