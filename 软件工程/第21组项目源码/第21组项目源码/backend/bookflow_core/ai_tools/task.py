from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from bookflow_core.models import WorkTask
from bookflow_core.services.common import create_snapshot, write_audit
from bookflow_core.services.task_service import (
    ai_complete_task,
    ai_fail_task,
    ai_start_task,
    create_task,
    list_tasks,
    resolve_task,
    takeover_task,
    task_to_dict,
)


def _apply_ai_lifecycle(db: Session, task: WorkTask, payload: dict, *, actor_id: str) -> WorkTask:
    run_id = payload.get("run_id")
    if not payload.get("disable_auto_ai", False):
        task = ai_start_task(db, task.task_code, run_id=run_id, actor_id=actor_id, commit=False)
    fail_reason = str(payload.get("fail_reason") or payload.get("ai_error") or "").strip()
    if payload.get("requires_human_confirmation") or fail_reason:
        return ai_fail_task(db, task.task_code, run_id=run_id, error=fail_reason or "requires_human_confirmation", confidence=payload.get("ai_confidence"), actor_id=actor_id, commit=False)
    if payload.get("auto_complete"):
        return ai_complete_task(db, task.task_code, run_id=run_id, result=str(payload.get("result") or "resolved"), actor_id=actor_id, commit=False)
    return task


def ai_create_work_task(db: Session, payload: dict, *, actor_id: str) -> dict:
    task = create_task(
        db,
        title=payload["title"],
        description=payload.get("description", ""),
        priority=payload.get("priority", "normal"),
        source_type="ai_admin",
        requires_human_confirmation=bool(payload.get("requires_human_confirmation", False)),
        actor_type="ai_admin",
        actor_id=actor_id,
        commit=False,
    )
    task = _apply_ai_lifecycle(db, task, payload, actor_id=actor_id)
    after = task_to_dict(task)
    create_snapshot(db, action_type="ai_create_work_task", target_table="work_tasks", target_id=task.task_code, before={}, after=after, actor_type="ai_admin", actor_id=actor_id, can_rollback=False)
    return after


def ai_get_tasks(db: Session, payload: dict, *, actor_id: str) -> dict:
    result = list_tasks(
        db,
        status=payload.get("status"),
        source_type=payload.get("source_type"),
        priority=payload.get("priority"),
        task_group=payload.get("task_group"),
        keyword=payload.get("keyword"),
        limit=int(payload.get("limit", 50)),
        offset=int(payload.get("offset", 0)),
    )
    return {**result, "items": [task_to_dict(row) for row in result["items"]]}


def ai_assign_task_to_admin(db: Session, payload: dict, *, actor_id: str) -> dict:
    task = takeover_task(
        db,
        payload["task_code"],
        admin_code=payload["admin_code"],
        reason=payload.get("reason", "ai_assign_task_to_admin"),
        actor_type="ai_admin",
        actor_id=actor_id,
        commit=False,
    )
    return task_to_dict(task)


def ai_resolve_work_task(db: Session, payload: dict, *, actor_id: str) -> dict:
    task = resolve_task(
        db,
        payload["task_code"],
        resolution=payload.get("resolution", "resolved_by_ai_tool"),
        actor_type="ai_admin",
        actor_id=actor_id,
        commit=False,
    )
    return task_to_dict(task)


def ai_batch_create_tasks(db: Session, payload: dict, *, actor_id: str) -> dict:
    created = []
    disable_auto_ai = bool(payload.get("disable_auto_ai", False))
    for item in payload["tasks"]:
        item_payload = {**item, "disable_auto_ai": disable_auto_ai or bool(item.get("disable_auto_ai", False))}
        task = create_task(
            db,
            title=item["title"],
            description=item.get("description", ""),
            priority=item.get("priority", "normal"),
            source_type="ai_admin",
            requires_human_confirmation=bool(item.get("requires_human_confirmation", False)),
            actor_type="ai_admin",
            actor_id=actor_id,
            commit=False,
        )
        task = _apply_ai_lifecycle(db, task, item_payload, actor_id=actor_id)
        created.append(task_to_dict(task))
    batch_id = payload.get("batch_id") or (created[0]["task_code"] if created else "")
    create_snapshot(db, action_type="ai_batch_create_tasks", target_table="work_tasks", target_id=batch_id, before={}, after={"items": created, "created_count": len(created)}, actor_type="ai_admin", actor_id=actor_id, can_rollback=False)
    write_audit(db, actor_type="ai_admin", actor_id=actor_id, action="ai_batch_create_tasks", target_table="work_tasks", target_id=batch_id, detail={"created_count": len(created), "disable_auto_ai": disable_auto_ai})
    return {"batch_id": batch_id, "created_count": len(created), "items": created}


def ai_batch_mark_low_risk_tasks(db: Session, payload: dict, *, actor_id: str) -> dict:
    limit = int(payload.get("limit", 20))
    rows = db.scalars(select(WorkTask).where(WorkTask.priority == "low", WorkTask.status.in_(["pending", "ai_processing"])).order_by(WorkTask.id).limit(limit)).all()
    before = [task_to_dict(row) for row in rows]
    updated = []
    for row in rows:
        updated_row = ai_complete_task(db, row.task_code, run_id=payload.get("run_id"), result=str(payload.get("result") or "low_risk_auto_resolved"), actor_id=actor_id, commit=False)
        updated.append(task_to_dict(updated_row))
    batch_id = payload.get("batch_id") or f"LOW-RISK-{len(rows)}"
    create_snapshot(db, action_type="ai_batch_mark_low_risk_tasks", target_table="work_tasks", target_id=batch_id, before={"items": before}, after={"items": updated}, actor_type="ai_admin", actor_id=actor_id, can_rollback=False)
    write_audit(db, actor_type="ai_admin", actor_id=actor_id, action="ai_batch_mark_low_risk_tasks", target_table="work_tasks", target_id=batch_id, detail={"updated_count": len(rows)})
    return {"batch_id": batch_id, "updated_count": len(rows), "items": updated}
