from __future__ import annotations

import json

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from bookflow_core.core.exceptions import BusinessRuleError, NotFoundError
from bookflow_core.core.time import now
from bookflow_core.models import AdminUser, WorkTask, WorkTaskEvent
from bookflow_core.services.common import as_json, write_audit

TASK_STATUS_PENDING = "pending"
TASK_STATUS_AI_PROCESSING = "ai_processing"
TASK_STATUS_WAITING_HUMAN = "waiting_human"
TASK_STATUS_ADMIN_PROCESSING = "admin_processing"
TASK_STATUS_RESOLVED = "resolved"
TASK_STATUS_CANCELLED = "cancelled"

ACTIVE_TASK_STATUSES = {
    TASK_STATUS_PENDING,
    TASK_STATUS_AI_PROCESSING,
    TASK_STATUS_WAITING_HUMAN,
    TASK_STATUS_ADMIN_PROCESSING,
}
HUMAN_TAKEOVER_ALLOWED_STATUSES = {
    TASK_STATUS_PENDING,
    TASK_STATUS_AI_PROCESSING,
    TASK_STATUS_WAITING_HUMAN,
}
RESOLVABLE_STATUSES = {
    TASK_STATUS_PENDING,
    TASK_STATUS_AI_PROCESSING,
    TASK_STATUS_WAITING_HUMAN,
    TASK_STATUS_ADMIN_PROCESSING,
}
AI_RUNNING_STATUSES = {TASK_STATUS_AI_PROCESSING}
COMPLETED_TASK_STATUSES = {TASK_STATUS_RESOLVED}
CANCELLED_TASK_STATUSES = {TASK_STATUS_CANCELLED}
VALID_STATUSES = ACTIVE_TASK_STATUSES | COMPLETED_TASK_STATUSES | CANCELLED_TASK_STATUSES

VALID_PRIORITIES = {"low", "normal", "high", "urgent"}
VALID_SOURCE_TYPES = {"overdue", "reservation", "shelving", "catalog", "ai", "ai_admin", "ai_review", "rule", "rule_engine", "risk", "security", "system", "circulation", "loan", "renew", "patrol", "reader_event"}
VALID_TASK_GROUPS = {"borrow", "exception", "shelving", "catalog", "reservation", "review", "ai_review", "risk", "notification", "other", "unknown"}
OTHER_TASK_GROUPS = {"shelving", "catalog", "reservation", "other", "unknown"}


def _task_code() -> str:
    from datetime import datetime, timezone

    return f"TASK-{int(datetime.now(timezone.utc).timestamp() * 1000000)}"


def _contains_any(*keywords: str):
    fields = (WorkTask.title, WorkTask.description, WorkTask.task_type, WorkTask.source_type)
    return or_(*[field.ilike(f"%{keyword}%") for field in fields for keyword in keywords])


def _get(row: WorkTask, name: str, default=None):
    return getattr(row, name, default) if hasattr(row, name) else default


def _set(row: WorkTask, name: str, value) -> None:
    if hasattr(row, name):
        setattr(row, name, value)


def _stamp(row: WorkTask, *, actor_type: str, actor_id: str, transition: str) -> None:
    stamp = now()
    _set(row, "updated_at", stamp)
    _set(row, "last_actor_type", actor_type)
    _set(row, "last_actor_id", str(actor_id or ""))
    _set(row, "last_transition", transition)
    _set(row, "last_transition_at", stamp)


def _admin_id_from_code(db: Session, actor_id: str | None) -> int | None:
    if not actor_id:
        return None
    return db.scalar(select(AdminUser.id).where(AdminUser.admin_code == str(actor_id)))


def _write_task_event(
    db: Session,
    row: WorkTask,
    *,
    event_type: str,
    actor_type: str,
    actor_id: str,
    previous_status: str | None = None,
    detail: dict | None = None,
) -> None:
    payload = {"task_code": row.task_code, **(detail or {})}
    if previous_status is not None:
        payload["from_status"] = previous_status
        payload["to_status"] = row.status
    db.add(
        WorkTaskEvent(
            task_id=row.id,
            event_type=event_type,
            actor_type=actor_type,
            actor_admin_id=_admin_id_from_code(db, actor_id) if actor_type in {"admin", "super_admin"} else None,
            detail_json=as_json(payload),
            created_at=now(),
        )
    )


def record_task_event(
    db: Session,
    row: WorkTask,
    *,
    event_type: str,
    actor_type: str,
    actor_id: str,
    previous_status: str | None = None,
    detail: dict | None = None,
) -> None:
    _write_task_event(
        db,
        row,
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_id,
        previous_status=previous_status,
        detail=detail,
    )


def _as_text(value) -> str:
    return str(value) if value else ""


def infer_task_group(*, title: str = "", description: str = "", task_type: str = "", source_type: str = "") -> str:
    text = f"{title or ''}{description or ''}{task_type or ''}{source_type or ''}"
    if any(keyword in text for keyword in ["借阅", "借书", "还书", "续借", "预约", "归还", "借出", "逾期", "超期", "到期"]):
        return "borrow"
    if source_type in {"risk", "security", "ai_review"} or task_type in {"risk", "security", "ai_review", "exception"} or any(keyword in text for keyword in ["异常", "风险", "复核", "检测", "错架", "错误", "安全", "告警"]):
        return "exception"
    if source_type == "shelving" or task_type == "shelving":
        return "shelving"
    if source_type in {"ai", "ai_admin"}:
        return "review"
    return "other"


def _task_group_filter(group: str):
    if group == "high":
        return WorkTask.priority.in_(["urgent", "high"])
    if group == "reader_ops":
        return or_(
            WorkTask.task_group.in_(["borrow", "reservation"]),
            WorkTask.queue_name == "reader_ops",
            WorkTask.related_entity_type == "circulation_service_request",
        )
    if group == "borrow":
        return WorkTask.task_group == "borrow"
    if group == "exception":
        return or_(
            WorkTask.task_group == "exception",
            WorkTask.source_type.in_(["risk", "security", "ai_review"]),
            WorkTask.status == TASK_STATUS_WAITING_HUMAN,
            WorkTask.priority.in_(["urgent", "high"]),
            WorkTask.risk_warning_code.isnot(None),
            WorkTask.risk_warning_code != "",
        )
    if group == "other":
        return WorkTask.task_group.in_(OTHER_TASK_GROUPS)
    if group in VALID_TASK_GROUPS:
        return WorkTask.task_group == group
    return None


def list_tasks(
    db: Session,
    *,
    status: str | None = None,
    source_type: str | None = None,
    priority: str | None = None,
    task_group: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    stmt = select(WorkTask)
    if status:
        stmt = stmt.where(WorkTask.status == status)
    if source_type:
        stmt = stmt.where(WorkTask.source_type == source_type)
    if priority:
        stmt = stmt.where(WorkTask.priority == priority)
    group_filter = _task_group_filter(task_group or "all")
    if group_filter is not None:
        stmt = stmt.where(group_filter)
    if keyword:
        stmt = stmt.where(_contains_any(keyword.strip()))
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    items = db.scalars(stmt.order_by(WorkTask.id.desc()).offset(offset).limit(limit)).all()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def create_task(
    db: Session,
    *,
    title: str,
    description: str = "",
    priority: str = "normal",
    source_type: str = "system",
    related_entity_type: str = "",
    related_entity_id: str = "",
    source_task_id: int | None = None,
    risk_warning_code: str = "",
    requires_human_confirmation: bool = False,
    task_group: str | None = None,
    auto_start_ai: bool = False,
    ai_run_id: int | None = None,
    ai_confidence: float | None = None,
    source_payload: dict | None = None,
    execution_context: dict | None = None,
    queue_name: str | None = None,
    max_attempts: int | None = None,
    actor_type: str = "system",
    actor_id: str = "system",
    commit: bool = True,
) -> WorkTask:
    if priority not in VALID_PRIORITIES:
        raise BusinessRuleError("Invalid task priority.", details={"priority": priority})
    if source_type not in VALID_SOURCE_TYPES:
        raise BusinessRuleError("Invalid task source_type.", details={"source_type": source_type})
    group = task_group or infer_task_group(title=title, description=description, source_type=source_type)
    if group not in VALID_TASK_GROUPS:
        raise BusinessRuleError("Invalid task_group.", details={"task_group": group})
    try:
        stamp = now()
        payload = dict(source_payload or {})
        payload.setdefault("_requested_priority", priority)
        row = WorkTask(
            task_code=_task_code(),
            title=title,
            description=description,
            status=TASK_STATUS_PENDING,
            priority=priority,
            source_type=source_type,
            source_task_id=source_task_id,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            risk_warning_code=risk_warning_code,
            requires_human_confirmation=requires_human_confirmation,
            task_group=group,
            created_at=stamp,
            updated_at=stamp,
        )
        _set(row, "handler_type", "ai")
        _set(row, "claim_status", "unclaimed")
        _set(row, "ai_run_id", ai_run_id)
        _set(row, "ai_confidence", ai_confidence)
        _set(row, "source_payload_json", as_json(payload))
        _set(row, "execution_context_json", as_json(execution_context or {}))
        _set(row, "max_attempts", max(1, int(max_attempts or 3)))
        _set(row, "attempt_count", 0)
        _stamp(row, actor_type=actor_type, actor_id=actor_id, transition="create_task")
        try:
            from bookflow_core.ai.kernel.task_policy import apply_task_policy

            apply_task_policy(row, preferred_queue=queue_name)
        except Exception:
            _set(row, "queue_name", queue_name or _get(row, "queue_name", "default") or "default")
        db.add(row)
        db.flush()
        _write_task_event(db, row, event_type="create_task", actor_type=actor_type, actor_id=actor_id, detail={"status": row.status, "priority": row.priority, "requested_priority": priority, "source_type": source_type, "task_group": group, "source_task_id": source_task_id})
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="create_task", target_table="work_tasks", target_id=row.task_code, detail={"priority": row.priority, "requested_priority": priority, "source_type": source_type, "task_group": group, "source_task_id": source_task_id, "auto_start_ai": auto_start_ai})
        if auto_start_ai:
            ai_start_task(db, row.task_code, run_id=ai_run_id, actor_id=actor_id, commit=False)
        if commit:
            db.commit()
            db.refresh(row)
        return row
    except Exception:
        if commit:
            db.rollback()
        raise


def get_task(db: Session, task_code: str) -> WorkTask:
    row = db.scalar(select(WorkTask).where(WorkTask.task_code == task_code))
    if not row:
        raise NotFoundError("Task not found.", details={"task_code": task_code})
    return row


def ai_start_task(
    db: Session,
    task_code: str,
    *,
    run_id: int | None = None,
    actor_id: str = "system_ai",
    commit: bool = True,
) -> WorkTask:
    try:
        row = get_task(db, task_code)
        previous_status = row.status
        if row.status in COMPLETED_TASK_STATUSES | CANCELLED_TASK_STATUSES:
            raise BusinessRuleError("AI cannot start a closed task.", details={"status": row.status})
        if row.status not in {TASK_STATUS_PENDING, TASK_STATUS_AI_PROCESSING}:
            raise BusinessRuleError("AI cannot start task from current status.", details={"status": row.status})
        stamp = now()
        row.status = TASK_STATUS_AI_PROCESSING
        _set(row, "handler_type", "ai")
        _set(row, "claim_status", "ai_claimed")
        _set(row, "ai_run_id", run_id)
        _set(row, "ai_started_at", stamp)
        _stamp(row, actor_type="ai", actor_id=actor_id, transition="ai_start_task")
        _write_task_event(db, row, event_type="ai_start_task", actor_type="ai", actor_id=actor_id, previous_status=previous_status, detail={"run_id": run_id})
        write_audit(db, actor_type="ai_admin", actor_id=actor_id, action="ai_start_task", target_table="work_tasks", target_id=row.task_code, detail={"run_id": run_id})
        if commit:
            db.commit()
            db.refresh(row)
        return row
    except Exception:
        if commit:
            db.rollback()
        raise


def ai_complete_task(
    db: Session,
    task_code: str,
    *,
    run_id: int | None = None,
    result: str = "resolved",
    actor_id: str = "system_ai",
    commit: bool = True,
) -> WorkTask:
    try:
        row = get_task(db, task_code)
        previous_status = row.status
        if row.status not in {TASK_STATUS_PENDING, TASK_STATUS_AI_PROCESSING}:
            raise BusinessRuleError("AI cannot complete task from current status.", details={"status": row.status})
        stamp = now()
        row.status = TASK_STATUS_RESOLVED
        row.resolved_by_code = str(actor_id or "")
        row.resolved_at = stamp
        row.resolution = result
        _set(row, "handler_type", "ai")
        _set(row, "claim_status", "ai_completed")
        _set(row, "ai_run_id", run_id if run_id is not None else _get(row, "ai_run_id"))
        _set(row, "ai_finished_at", stamp)
        _set(row, "ai_result", result)
        _set(row, "lease_owner", None)
        _set(row, "lease_expires_at", None)
        _set(row, "next_attempt_at", None)
        _stamp(row, actor_type="ai", actor_id=actor_id, transition="ai_complete_task")
        _write_task_event(db, row, event_type="ai_complete_task", actor_type="ai", actor_id=actor_id, previous_status=previous_status, detail={"run_id": run_id, "result": result})
        write_audit(db, actor_type="ai_admin", actor_id=actor_id, action="ai_complete_task", target_table="work_tasks", target_id=row.task_code, detail={"run_id": run_id, "result": result})
        if commit:
            db.commit()
            db.refresh(row)
        return row
    except Exception:
        if commit:
            db.rollback()
        raise


def ai_fail_task(
    db: Session,
    task_code: str,
    *,
    run_id: int | None = None,
    error: str = "",
    confidence: float | None = None,
    actor_id: str = "system_ai",
    commit: bool = True,
) -> WorkTask:
    try:
        row = get_task(db, task_code)
        previous_status = row.status
        if row.status not in {TASK_STATUS_PENDING, TASK_STATUS_AI_PROCESSING}:
            raise BusinessRuleError("AI cannot fail task from current status.", details={"status": row.status})
        stamp = now()
        row.status = TASK_STATUS_WAITING_HUMAN
        row.requires_human_confirmation = True
        _set(row, "handler_type", "mixed")
        _set(row, "claim_status", "waiting_human")
        _set(row, "ai_run_id", run_id if run_id is not None else _get(row, "ai_run_id"))
        _set(row, "ai_finished_at", stamp)
        _set(row, "ai_error", error)
        _set(row, "ai_confidence", confidence)
        _set(row, "lease_owner", None)
        _set(row, "lease_expires_at", None)
        _set(row, "interrupted_at", stamp)
        _set(row, "interrupt_reason", error or "ai_fail_task")
        _stamp(row, actor_type="ai", actor_id=actor_id, transition="ai_fail_task")
        _write_task_event(db, row, event_type="ai_fail_task", actor_type="ai", actor_id=actor_id, previous_status=previous_status, detail={"run_id": run_id, "error": error, "confidence": confidence})
        write_audit(db, actor_type="ai_admin", actor_id=actor_id, action="ai_fail_task", target_table="work_tasks", target_id=row.task_code, detail={"run_id": run_id, "error": error, "confidence": confidence})
        if commit:
            db.commit()
            db.refresh(row)
        return row
    except Exception:
        if commit:
            db.rollback()
        raise


def takeover_task(
    db: Session,
    task_code: str,
    *,
    admin_code: str,
    reason: str = "admin_takeover",
    actor_type: str = "admin",
    actor_id: str = "admin",
    commit: bool = True,
) -> WorkTask:
    try:
        row = get_task(db, task_code)
        if row.status not in HUMAN_TAKEOVER_ALLOWED_STATUSES:
            raise BusinessRuleError("Task cannot be taken over from current status.", details={"status": row.status})
        previous_status = row.status
        stamp = now()
        action = "admin_takeover_ai_task" if previous_status == TASK_STATUS_AI_PROCESSING else "admin_claim_task"
        row.status = TASK_STATUS_ADMIN_PROCESSING
        _set(row, "lease_owner", None)
        _set(row, "lease_expires_at", None)
        row.claimed_by_code = admin_code
        row.claimed_at = stamp
        _set(row, "handler_type", "admin")
        _set(row, "claim_status", "overridden_by_admin" if previous_status == TASK_STATUS_AI_PROCESSING else "admin_claimed")
        _set(row, "takeover_by_code", admin_code)
        _set(row, "takeover_at", stamp)
        _set(row, "takeover_reason", reason or action)
        _stamp(row, actor_type=actor_type, actor_id=actor_id, transition="takeover_task")
        _write_task_event(db, row, event_type=action, actor_type=actor_type, actor_id=actor_id, previous_status=previous_status, detail={"admin_code": admin_code, "reason": reason or action})
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action=action, target_table="work_tasks", target_id=row.task_code, detail={"admin_code": admin_code, "previous_status": previous_status, "reason": reason or action})
        if commit:
            db.commit()
            db.refresh(row)
        return row
    except Exception:
        if commit:
            db.rollback()
        raise


def claim_task(db: Session, task_code: str, *, admin_code: str, actor_type: str = "admin", actor_id: str = "admin", commit: bool = True) -> WorkTask:
    return takeover_task(db, task_code, admin_code=admin_code, reason="admin_claim_task", actor_type=actor_type, actor_id=actor_id, commit=commit)


def resolve_task(db: Session, task_code: str, *, resolution: str = "resolved", actor_type: str = "admin", actor_id: str = "admin", commit: bool = True) -> WorkTask:
    try:
        row = get_task(db, task_code)
        if row.status not in RESOLVABLE_STATUSES:
            raise BusinessRuleError("Task cannot be resolved from current status.", details={"status": row.status})
        stamp = now()
        previous_status = row.status
        resolve_from_status = previous_status
        if actor_type == "admin" and previous_status != TASK_STATUS_ADMIN_PROCESSING:
            action = "admin_takeover_ai_task" if previous_status == TASK_STATUS_AI_PROCESSING else "admin_claim_task"
            _set(row, "claim_status", "overridden_by_admin" if previous_status == TASK_STATUS_AI_PROCESSING else "admin_claimed")
            row.claimed_by_code = str(actor_id or "")
            row.claimed_at = row.claimed_at or stamp
            _set(row, "takeover_by_code", actor_id)
            _set(row, "takeover_at", stamp)
            _set(row, "takeover_reason", "admin_resolve_task")
            row.status = TASK_STATUS_ADMIN_PROCESSING
            _write_task_event(db, row, event_type=action, actor_type=actor_type, actor_id=actor_id, previous_status=previous_status, detail={"reason": "admin_resolve_task"})
            write_audit(db, actor_type=actor_type, actor_id=actor_id, action=action, target_table="work_tasks", target_id=row.task_code, detail={"previous_status": previous_status, "reason": "admin_resolve_task"})
            resolve_from_status = TASK_STATUS_ADMIN_PROCESSING
        elif actor_type == "admin" and _get(row, "claim_status") in {"", None, "unclaimed", "ai_claimed", "waiting_human"}:
            _set(row, "claim_status", "admin_claimed")
        row.status = TASK_STATUS_RESOLVED
        row.resolved_by_code = str(actor_id or "")
        row.resolved_at = stamp
        row.resolution = resolution
        if actor_type == "admin":
            _set(row, "handler_type", "admin")
        _stamp(row, actor_type=actor_type, actor_id=actor_id, transition="resolve_task")
        _write_task_event(db, row, event_type="resolve_task", actor_type=actor_type, actor_id=actor_id, previous_status=resolve_from_status, detail={"resolution": resolution, "original_status": previous_status})
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="resolve_task", target_table="work_tasks", target_id=row.task_code, detail={"resolution": resolution, "previous_status": resolve_from_status, "original_status": previous_status})
        if commit:
            db.commit()
            db.refresh(row)
        return row
    except Exception:
        if commit:
            db.rollback()
        raise


def cancel_task(db: Session, task_code: str, *, reason: str = "cancelled", actor_type: str = "admin", actor_id: str = "admin", commit: bool = True) -> WorkTask:
    try:
        row = get_task(db, task_code)
        if row.status == TASK_STATUS_RESOLVED:
            raise BusinessRuleError("Resolved task cannot be cancelled.")
        if row.status == TASK_STATUS_CANCELLED:
            return row
        previous_status = row.status
        row.status = TASK_STATUS_CANCELLED
        row.cancelled_at = now()
        row.resolution = reason
        _stamp(row, actor_type=actor_type, actor_id=actor_id, transition="cancel_task")
        _write_task_event(db, row, event_type="cancel_task", actor_type=actor_type, actor_id=actor_id, previous_status=previous_status, detail={"reason": reason})
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="cancel_task", target_table="work_tasks", target_id=row.task_code, detail={"reason": reason, "previous_status": previous_status})
        if commit:
            db.commit()
            db.refresh(row)
        return row
    except Exception:
        if commit:
            db.rollback()
        raise


def task_to_dict(row: WorkTask) -> dict:
    return {
        "task_code": row.task_code,
        "source_task_id": row.source_task_id,
        "title": row.title,
        "description": row.description,
        "status": row.status,
        "priority": row.priority,
        "task_group": row.task_group,
        "source_type": row.source_type,
        "handler_type": _get(row, "handler_type", ""),
        "claim_status": _get(row, "claim_status", ""),
        "ai_run_id": _get(row, "ai_run_id"),
        "ai_started_at": _as_text(_get(row, "ai_started_at")),
        "ai_finished_at": _as_text(_get(row, "ai_finished_at")),
        "ai_error": _get(row, "ai_error", ""),
        "ai_confidence": _get(row, "ai_confidence"),
        "ai_result": _get(row, "ai_result", ""),
        "takeover_by_code": _get(row, "takeover_by_code", ""),
        "takeover_at": _as_text(_get(row, "takeover_at")),
        "takeover_reason": _get(row, "takeover_reason", ""),
        "last_actor_type": _get(row, "last_actor_type", ""),
        "last_actor_id": _get(row, "last_actor_id", ""),
        "last_transition": _get(row, "last_transition", ""),
        "last_transition_at": _as_text(_get(row, "last_transition_at")),
        "claimed_by_code": row.claimed_by_code,
        "related_entity_type": row.related_entity_type,
        "related_entity_id": row.related_entity_id,
        "risk_warning_code": row.risk_warning_code,
        "sla_due_at": _as_text(row.sla_due_at),
        "claimed_at": _as_text(row.claimed_at),
        "resolved_at": _as_text(row.resolved_at),
        "cancelled_at": _as_text(row.cancelled_at),
        "resolved_by_code": row.resolved_by_code,
        "resolution": row.resolution,
        "requires_human_confirmation": row.requires_human_confirmation,
        "queue_name": _get(row, "queue_name", "default"),
        "priority_score": _get(row, "priority_score", 0),
        "risk_level": _get(row, "risk_level", "low"),
        "urgency_reason": _get(row, "urgency_reason", ""),
        "lease_owner": _get(row, "lease_owner", ""),
        "lease_expires_at": _as_text(_get(row, "lease_expires_at")),
        "attempt_count": _get(row, "attempt_count", 0),
        "max_attempts": _get(row, "max_attempts", 3),
        "next_attempt_at": _as_text(_get(row, "next_attempt_at")),
        "interrupted_at": _as_text(_get(row, "interrupted_at")),
        "interrupt_reason": _get(row, "interrupt_reason", ""),
        "created_at": _as_text(row.created_at),
        "updated_at": _as_text(row.updated_at),
    }


def _json_obj(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {"raw": raw}
    return data if isinstance(data, dict) else {"value": data}


def task_detail_to_dict(row: WorkTask) -> dict:
    data = task_to_dict(row)
    data.update(
        {
            "source_payload": _json_obj(_get(row, "source_payload_json", "")),
            "execution_context": _json_obj(_get(row, "execution_context_json", "")),
            "ai_plan": _json_obj(_get(row, "ai_plan_json", "")),
            "ai_trace": _json_obj(_get(row, "ai_trace_json", "")),
        }
    )
    return data
