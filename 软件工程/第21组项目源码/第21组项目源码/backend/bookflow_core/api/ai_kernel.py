from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from bookflow_core.ai.kernel.agent import process_next_task, process_task
from bookflow_core.ai.kernel.intake import create_patrol_task, process_patrol
from bookflow_core.ai.kernel.task_queue import (
    interrupt_task,
    lease_next_task,
    queue_summary,
    refresh_queue,
    release_task_lease,
)
from bookflow_core.ai.kernel.worker import (
    run_ai_kernel_worker_once,
    start_ai_kernel_worker,
    stop_ai_kernel_worker,
    worker_status,
)
from bookflow_core.api.deps import require_permission
from bookflow_core.core.database import get_db
from bookflow_core.services.ai_run_service import list_agent_runs
from bookflow_core.services.task_service import task_to_dict

router = APIRouter(prefix="/ai/kernel", tags=["ai-kernel"])


@router.get("/queue")
def get_queue_summary(db: Session = Depends(get_db), current_admin=Depends(require_permission("ai:chat"))):
    return {"success": True, "data": queue_summary(db), "message": None}


@router.post("/queue/refresh")
def refresh_task_queue(
    body: dict | None = Body(default=None),
    db: Session = Depends(get_db),
    current_admin=Depends(require_permission("ai:chat")),
):
    body = body or {}
    return {"success": True, "data": refresh_queue(db, limit=int(body.get("limit") or 500)), "message": None}


@router.get("/runs")
def kernel_runs(
    status: str | None = None,
    actor_id: str | None = None,
    include_payload: bool = False,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_admin=Depends(require_permission("ai:chat")),
):
    return {"success": True, "data": list_agent_runs(db, status=status, tool_name="ai_kernel_task_agent", actor_id=actor_id, include_payload=include_payload, limit=limit, offset=offset), "message": None}


@router.get("/worker")
def get_worker_status(current_admin=Depends(require_permission("ai:chat"))):
    return {"success": True, "data": worker_status(), "message": None}


@router.post("/worker/run-once")
def run_worker_once(body: dict | None = Body(default=None), current_admin=Depends(require_permission("ai:chat"))):
    body = body or {}
    data = run_ai_kernel_worker_once(
        worker_id=str(body.get("worker_id") or current_admin.admin_code or "ai-kernel-worker"),
        queue_names=body.get("queue_names"),
        batch_size=body.get("batch_size"),
        lease_seconds=body.get("lease_seconds"),
    )
    return {"success": True, "data": data, "message": None}


@router.post("/worker/start")
def start_worker(body: dict | None = Body(default=None), current_admin=Depends(require_permission("ai:chat"))):
    body = body or {}
    started = start_ai_kernel_worker(
        worker_id=str(body.get("worker_id") or "ai-kernel-worker"),
        queue_names=body.get("queue_names"),
        interval_seconds=body.get("interval_seconds"),
        batch_size=body.get("batch_size"),
        lease_seconds=body.get("lease_seconds"),
    )
    return {"success": True, "data": {"started": started, **worker_status()}, "message": None}


@router.post("/worker/stop")
def stop_worker(current_admin=Depends(require_permission("ai:chat"))):
    stop_ai_kernel_worker()
    return {"success": True, "data": worker_status(), "message": None}


@router.post("/patrol/{scenario}")
def kernel_patrol(
    scenario: str,
    body: dict | None = Body(default=None),
    db: Session = Depends(get_db),
    current_admin=Depends(require_permission("ai:chat")),
):
    body = body or {}
    auto_process = bool(body.get("auto_process", True))
    worker_id = str(body.get("worker_id") or current_admin.admin_code or "ai-kernel-worker")
    if auto_process:
        data = process_patrol(db, scenario=scenario, actor_id=worker_id)
    else:
        task = create_patrol_task(db, scenario=scenario, actor_id=worker_id)
        data = {"status": "queued", "scenario": scenario, "task_code": task.task_code, "task": task_to_dict(task), "kernel": True}
    return {"success": True, "data": data, "message": None}


@router.post("/tasks/lease-next")
def lease_next(
    body: dict | None = Body(default=None),
    db: Session = Depends(get_db),
    current_admin=Depends(require_permission("ai:chat")),
):
    body = body or {}
    row = lease_next_task(
        db,
        worker_id=str(body.get("worker_id") or current_admin.admin_code or "ai-kernel-worker"),
        queue_name=body.get("queue_name"),
        lease_seconds=int(body.get("lease_seconds") or 300),
    )
    return {"success": True, "data": task_to_dict(row) if row else None, "message": None}


@router.post("/tasks/process-next")
def process_next(
    body: dict | None = Body(default=None),
    db: Session = Depends(get_db),
    current_admin=Depends(require_permission("ai:chat")),
):
    body = body or {}
    data = process_next_task(
        db,
        worker_id=str(body.get("worker_id") or current_admin.admin_code or "ai-kernel-worker"),
        queue_name=body.get("queue_name"),
        lease_seconds=int(body.get("lease_seconds") or 300),
    )
    return {"success": True, "data": data, "message": None}


@router.post("/tasks/{task_code}/process")
def process_specific_task(
    task_code: str,
    body: dict | None = Body(default=None),
    db: Session = Depends(get_db),
    current_admin=Depends(require_permission("ai:chat")),
):
    body = body or {}
    data = process_task(
        db,
        task_code,
        worker_id=str(body.get("worker_id") or current_admin.admin_code or "ai-kernel-worker"),
        lease_seconds=int(body.get("lease_seconds") or 300),
    )
    return {"success": True, "data": data, "message": None}


@router.post("/tasks/{task_code}/interrupt")
def interrupt_specific_task(
    task_code: str,
    body: dict | None = Body(default=None),
    db: Session = Depends(get_db),
    current_admin=Depends(require_permission("ai:chat")),
):
    body = body or {}
    row = interrupt_task(
        db,
        task_code,
        reason=str(body.get("reason") or "manual_kernel_interrupt"),
        actor_type="admin",
        actor_id=current_admin.admin_code,
    )
    return {"success": True, "data": task_to_dict(row), "message": None}


@router.post("/tasks/{task_code}/release")
def release_specific_task(
    task_code: str,
    body: dict | None = Body(default=None),
    db: Session = Depends(get_db),
    current_admin=Depends(require_permission("ai:chat")),
):
    body = body or {}
    row = release_task_lease(
        db,
        task_code,
        worker_id=str(body.get("worker_id") or current_admin.admin_code or "ai-kernel-worker"),
        reason=str(body.get("reason") or "manual_release"),
        retry_delay_seconds=body.get("retry_delay_seconds"),
    )
    return {"success": True, "data": task_to_dict(row), "message": None}
