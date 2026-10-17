from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from bookflow_core.core.database import get_db
from bookflow_core.api.deps import require_permission
from bookflow_core.models import CirculationServiceRequest
from bookflow_core.schemas import AITaskCompleteRequest, AITaskFailRequest, AITaskStartRequest, CancelTaskRequest, ClaimTaskRequest, ResolveTaskRequest, TakeoverTaskRequest, TaskRequest
from bookflow_core.services.circulation_request_service import service_request_to_dict
from bookflow_core.services.task_service import ai_complete_task, ai_fail_task, ai_start_task, cancel_task, claim_task, create_task, get_task, list_tasks, resolve_task, takeover_task, task_detail_to_dict, task_to_dict

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.get("")
def tasks(
    status: str | None = None,
    source_type: str | None = None,
    priority: str | None = None,
    task_group: str | None = None,
    keyword: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    result = list_tasks(db, status=status, source_type=source_type, priority=priority, task_group=task_group, keyword=keyword, limit=limit, offset=offset)
    return {"success": True, "data": {**result, "items": [task_to_dict(t) for t in result["items"]]}, "message": None}

@router.get("/{task_code}")
def task_detail(task_code: str, db: Session = Depends(get_db), current_admin=Depends(require_permission("tasks:read"))):
    row = get_task(db, task_code)
    data = task_detail_to_dict(row)
    if row.related_entity_type == "circulation_service_request" and row.related_entity_id:
        try:
            request_id = int(row.related_entity_id)
        except (TypeError, ValueError):
            request_id = 0
        request = db.scalar(select(CirculationServiceRequest).where(CirculationServiceRequest.id == request_id)) if request_id else None
        if request:
            data["service_request"] = service_request_to_dict(request)
    return {"success": True, "data": data, "message": None}

@router.post("")
def create(req: TaskRequest, db: Session = Depends(get_db), current_admin=Depends(require_permission("tasks:write"))):
    row = create_task(
        db,
        title=req.title,
        description=req.description,
        priority=req.priority,
        task_group=req.task_group,
        source_type=req.source_type,
        related_entity_type=req.related_entity_type,
        related_entity_id=req.related_entity_id,
        risk_warning_code=req.risk_warning_code,
        requires_human_confirmation=req.requires_human_confirmation,
        auto_start_ai=req.auto_start_ai,
        source_payload=req.source_payload,
        execution_context=req.execution_context,
        queue_name=req.queue_name,
        max_attempts=req.max_attempts,
        actor_id=current_admin.admin_code,
    )
    return {"success": True, "data": task_to_dict(row), "message": None}

@router.post("/{task_code}/claim")
def claim(task_code: str, req: ClaimTaskRequest, db: Session = Depends(get_db), current_admin=Depends(require_permission("tasks:write"))):
    row = claim_task(db, task_code, admin_code=req.admin_code, actor_id=current_admin.admin_code)
    return {"success": True, "data": task_to_dict(row), "message": None}

@router.post("/{task_code}/takeover")
def takeover(task_code: str, req: TakeoverTaskRequest, db: Session = Depends(get_db), current_admin=Depends(require_permission("tasks:write"))):
    row = takeover_task(db, task_code, admin_code=req.admin_code or current_admin.admin_code, reason=req.reason, actor_id=current_admin.admin_code)
    return {"success": True, "data": task_to_dict(row), "message": None}

@router.post("/{task_code}/ai-start")
def ai_start(task_code: str, req: AITaskStartRequest, db: Session = Depends(get_db), current_admin=Depends(require_permission("tasks:write"))):
    row = ai_start_task(db, task_code, run_id=req.run_id, actor_id=current_admin.admin_code)
    return {"success": True, "data": task_to_dict(row), "message": None}

@router.post("/{task_code}/ai-complete")
def ai_complete(task_code: str, req: AITaskCompleteRequest, db: Session = Depends(get_db), current_admin=Depends(require_permission("tasks:write"))):
    row = ai_complete_task(db, task_code, run_id=req.run_id, result=req.result, actor_id=current_admin.admin_code)
    return {"success": True, "data": task_to_dict(row), "message": None}

@router.post("/{task_code}/ai-fail")
def ai_fail(task_code: str, req: AITaskFailRequest, db: Session = Depends(get_db), current_admin=Depends(require_permission("tasks:write"))):
    row = ai_fail_task(db, task_code, run_id=req.run_id, error=req.error, confidence=req.confidence, actor_id=current_admin.admin_code)
    return {"success": True, "data": task_to_dict(row), "message": None}

@router.post("/{task_code}/resolve")
def resolve(task_code: str, req: ResolveTaskRequest, db: Session = Depends(get_db), current_admin=Depends(require_permission("tasks:write"))):
    row = resolve_task(db, task_code, resolution=req.resolution, actor_id=current_admin.admin_code)
    return {"success": True, "data": task_to_dict(row), "message": None}

@router.post("/{task_code}/cancel")
def cancel(task_code: str, req: CancelTaskRequest, db: Session = Depends(get_db), current_admin=Depends(require_permission("tasks:write"))):
    row = cancel_task(db, task_code, reason=req.reason, actor_id=current_admin.admin_code)
    return {"success": True, "data": task_to_dict(row), "message": None}
