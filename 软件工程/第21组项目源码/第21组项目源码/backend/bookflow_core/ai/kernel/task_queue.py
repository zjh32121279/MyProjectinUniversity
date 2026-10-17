from __future__ import annotations

from datetime import datetime, timezone, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from bookflow_core.ai.kernel.task_policy import apply_task_policy
from bookflow_core.core.exceptions import BusinessRuleError
from bookflow_core.core.time import now
from bookflow_core.models import AITaskCheckpoint, WorkTask
from bookflow_core.services.common import as_json, write_audit
from bookflow_core.services.task_service import (
    TASK_STATUS_AI_PROCESSING,
    TASK_STATUS_ADMIN_PROCESSING,
    TASK_STATUS_CANCELLED,
    TASK_STATUS_PENDING,
    TASK_STATUS_RESOLVED,
    TASK_STATUS_WAITING_HUMAN,
    ai_start_task,
    get_task,
    record_task_event,
    task_to_dict,
)


TERMINAL_STATUSES = {TASK_STATUS_RESOLVED, TASK_STATUS_CANCELLED}


def _code(prefix: str) -> str:
    return f"{prefix}-{int(datetime.now(timezone.utc).timestamp() * 1000000)}"


def _preferred_queue(row: WorkTask, requested_queue: str | None = None) -> str | None:
    if requested_queue:
        return requested_queue
    if row.queue_name and row.queue_name != "default":
        return row.queue_name
    return None


def refresh_task_routing(db: Session, row: WorkTask, *, commit: bool = False) -> WorkTask:
    apply_task_policy(row, preferred_queue=_preferred_queue(row))
    if commit:
        db.commit()
        db.refresh(row)
    return row


def refresh_queue(db: Session, *, limit: int = 500, commit: bool = True) -> dict:
    rows = db.scalars(
        select(WorkTask)
        .where(WorkTask.status.in_([TASK_STATUS_PENDING, TASK_STATUS_AI_PROCESSING, TASK_STATUS_WAITING_HUMAN]))
        .order_by(WorkTask.id.desc())
        .limit(max(1, min(int(limit), 2000)))
    ).all()
    for row in rows:
        apply_task_policy(row, preferred_queue=_preferred_queue(row))
    if commit:
        db.commit()
    return {"refreshed": len(rows)}


def _lease_candidates(current_time):
    lease_ready = or_(
        WorkTask.status == TASK_STATUS_PENDING,
        and_(
            WorkTask.status == TASK_STATUS_AI_PROCESSING,
            WorkTask.lease_owner.isnot(None),
            WorkTask.lease_expires_at.isnot(None),
            WorkTask.lease_expires_at <= current_time,
        ),
    )
    retry_ready = or_(WorkTask.next_attempt_at.is_(None), WorkTask.next_attempt_at <= current_time)
    attempts_ready = or_(
        WorkTask.attempt_count.is_(None),
        WorkTask.max_attempts.is_(None),
        WorkTask.attempt_count < WorkTask.max_attempts,
    )
    return lease_ready, retry_ready, attempts_ready


def lease_next_task(
    db: Session,
    *,
    worker_id: str,
    queue_name: str | None = None,
    lease_seconds: int = 300,
    run_id: int | None = None,
    commit: bool = True,
) -> WorkTask | None:
    current_time = now()
    lease_ready, retry_ready, attempts_ready = _lease_candidates(current_time)
    stmt = (
        select(WorkTask)
        .where(lease_ready, retry_ready, attempts_ready)
        .order_by(WorkTask.priority_score.desc(), WorkTask.created_at.asc(), WorkTask.id.asc())
        .limit(1)
    )
    if queue_name:
        stmt = stmt.where(WorkTask.queue_name == queue_name)
    row = db.scalar(stmt)
    if row is None:
        return None

    previous_status = row.status
    apply_task_policy(row, preferred_queue=_preferred_queue(row, queue_name))
    row.lease_owner = worker_id
    row.lease_expires_at = current_time + timedelta(seconds=max(30, int(lease_seconds)))
    row.attempt_count = int(row.attempt_count or 0) + 1
    ai_start_task(db, row.task_code, run_id=run_id, actor_id=worker_id, commit=False)
    record_task_event(
        db,
        row,
        event_type="ai_kernel_lease_task",
        actor_type="ai",
        actor_id=worker_id,
        previous_status=previous_status,
        detail={"queue_name": row.queue_name, "lease_owner": worker_id, "lease_expires_at": row.lease_expires_at},
    )
    write_audit(
        db,
        actor_type="ai_admin",
        actor_id=worker_id,
        action="ai_kernel_lease_task",
        target_table="work_tasks",
        target_id=row.task_code,
        detail={"queue_name": row.queue_name, "priority_score": row.priority_score},
    )
    if commit:
        db.commit()
        db.refresh(row)
    return row


def release_task_lease(
    db: Session,
    task_code: str,
    *,
    worker_id: str,
    reason: str = "released",
    retry_delay_seconds: int | None = None,
    commit: bool = True,
) -> WorkTask:
    row = get_task(db, task_code)
    if row.lease_owner and row.lease_owner != worker_id:
        raise BusinessRuleError(
            "Task lease is owned by another worker.",
            details={"task_code": task_code, "lease_owner": row.lease_owner, "worker_id": worker_id},
        )
    previous_status = row.status
    row.lease_owner = None
    row.lease_expires_at = None
    row.status = TASK_STATUS_PENDING if row.status == TASK_STATUS_AI_PROCESSING else row.status
    if retry_delay_seconds is not None:
        row.next_attempt_at = now() + timedelta(seconds=max(0, int(retry_delay_seconds)))
    refresh_task_routing(db, row)
    record_task_event(
        db,
        row,
        event_type="ai_kernel_release_task",
        actor_type="ai",
        actor_id=worker_id,
        previous_status=previous_status,
        detail={"reason": reason, "next_attempt_at": row.next_attempt_at},
    )
    write_audit(
        db,
        actor_type="ai_admin",
        actor_id=worker_id,
        action="ai_kernel_release_task",
        target_table="work_tasks",
        target_id=row.task_code,
        detail={"reason": reason},
    )
    if commit:
        db.commit()
        db.refresh(row)
    return row


def handle_task_failure(
    db: Session,
    task_code: str,
    *,
    worker_id: str,
    reason: str,
    run_id: int | None = None,
    retry_delay_seconds: int | None = None,
    commit: bool = True,
) -> WorkTask:
    row = get_task(db, task_code)
    if row.status in TERMINAL_STATUSES or row.status == TASK_STATUS_ADMIN_PROCESSING:
        return row
    previous_status = row.status
    attempts = int(row.attempt_count or 0)
    max_attempts = int(row.max_attempts or 3)
    row.lease_owner = None
    row.lease_expires_at = None
    row.ai_error = reason
    if attempts >= max_attempts:
        stamp = now()
        row.status = TASK_STATUS_WAITING_HUMAN
        row.requires_human_confirmation = True
        row.handler_type = "mixed"
        row.claim_status = "waiting_human"
        row.interrupted_at = stamp
        row.interrupt_reason = f"max_attempts_exceeded:{reason}"
        row.ai_finished_at = stamp
        event_type = "ai_kernel_failure_handoff"
    else:
        delay = int(retry_delay_seconds) if retry_delay_seconds is not None else min(3600, 30 * (2 ** max(0, attempts - 1)))
        row.status = TASK_STATUS_PENDING
        row.next_attempt_at = now() + timedelta(seconds=max(0, delay))
        row.handler_type = "ai"
        row.claim_status = "retry_scheduled"
        event_type = "ai_kernel_failure_retry"
    refresh_task_routing(db, row)
    record_task_event(
        db,
        row,
        event_type=event_type,
        actor_type="ai",
        actor_id=worker_id,
        previous_status=previous_status,
        detail={"reason": reason, "run_id": run_id, "attempt_count": attempts, "max_attempts": max_attempts, "next_attempt_at": row.next_attempt_at},
    )
    write_audit(
        db,
        actor_type="ai_admin",
        actor_id=worker_id,
        action=event_type,
        target_table="work_tasks",
        target_id=row.task_code,
        detail={"reason": reason, "run_id": run_id, "attempt_count": attempts, "max_attempts": max_attempts},
    )
    if commit:
        db.commit()
        db.refresh(row)
    return row


def interrupt_task(
    db: Session,
    task_code: str,
    *,
    reason: str,
    actor_type: str = "ai",
    actor_id: str = "system_ai",
    commit: bool = True,
) -> WorkTask:
    row = get_task(db, task_code)
    if row.status in TERMINAL_STATUSES or row.status == TASK_STATUS_ADMIN_PROCESSING:
        raise BusinessRuleError("Task cannot be interrupted from current status.", details={"status": row.status})
    previous_status = row.status
    stamp = now()
    row.status = TASK_STATUS_WAITING_HUMAN
    row.requires_human_confirmation = True
    row.handler_type = "mixed"
    row.claim_status = "waiting_human"
    row.interrupted_at = stamp
    row.interrupt_reason = reason
    row.ai_finished_at = stamp
    row.ai_error = reason
    row.lease_owner = None
    row.lease_expires_at = None
    refresh_task_routing(db, row)
    record_task_event(
        db,
        row,
        event_type="ai_kernel_interrupt_task",
        actor_type=actor_type,
        actor_id=actor_id,
        previous_status=previous_status,
        detail={"reason": reason},
    )
    write_audit(
        db,
        actor_type="ai_admin" if actor_type == "ai" else actor_type,
        actor_id=actor_id,
        action="ai_kernel_interrupt_task",
        target_table="work_tasks",
        target_id=row.task_code,
        detail={"reason": reason},
    )
    if commit:
        db.commit()
        db.refresh(row)
    return row


def write_checkpoint(
    db: Session,
    *,
    task: WorkTask,
    run_id: int | None,
    worker_id: str,
    node_name: str,
    status: str,
    state: dict,
    resume_token: str | None = None,
) -> AITaskCheckpoint:
    row = AITaskCheckpoint(
        checkpoint_code=_code("CKPT"),
        task_id=task.id,
        run_id=run_id,
        worker_id=worker_id,
        node_name=node_name,
        status=status,
        state_json=as_json(state),
        resume_token=resume_token,
        created_at=now(),
        updated_at=now(),
    )
    db.add(row)
    return row


def queue_summary(db: Session) -> dict:
    rows = db.execute(
        select(WorkTask.queue_name, WorkTask.status, WorkTask.risk_level, func.count(WorkTask.id))
        .group_by(WorkTask.queue_name, WorkTask.status, WorkTask.risk_level)
        .order_by(WorkTask.queue_name, WorkTask.status, WorkTask.risk_level)
    ).all()
    active_total = int(
        db.scalar(
            select(func.count(WorkTask.id)).where(
                WorkTask.status.in_(
                    [
                        TASK_STATUS_PENDING,
                        TASK_STATUS_AI_PROCESSING,
                        TASK_STATUS_WAITING_HUMAN,
                        TASK_STATUS_ADMIN_PROCESSING,
                    ]
                )
            )
        )
        or 0
    )
    next_items = db.scalars(
        select(WorkTask)
        .where(WorkTask.status == TASK_STATUS_PENDING)
        .order_by(WorkTask.priority_score.desc(), WorkTask.created_at.asc(), WorkTask.id.asc())
        .limit(10)
    ).all()
    return {
        "active_total": active_total,
        "buckets": [
            {"queue_name": queue or "default", "status": status, "risk_level": risk or "low", "count": int(count)}
            for queue, status, risk, count in rows
        ],
        "next_items": [task_to_dict(row) for row in next_items],
    }
