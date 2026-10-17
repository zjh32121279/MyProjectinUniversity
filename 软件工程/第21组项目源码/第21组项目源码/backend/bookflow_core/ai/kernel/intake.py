from __future__ import annotations

from sqlalchemy.orm import Session

from bookflow_core.ai.kernel.agent import process_task
from bookflow_core.models import ReaderAccount, WorkTask
from bookflow_core.services.task_service import create_task, task_to_dict


PATROL_TOOLS = {
    "daily": ("ai_get_operational_brief", {"limit": 30}, "normal", "review"),
    "overdue": ("ai_get_overdue_summary", {"limit": 50}, "high", "borrow"),
    "collection-health": ("ai_get_collection_health", {}, "normal", "catalog"),
    "reservations": ("ai_get_task_summary", {}, "normal", "reservation"),
    "s04": ("ai_get_admin_security_summary", {}, "high", "risk"),
}


def create_kernel_task(
    db: Session,
    *,
    title: str,
    description: str = "",
    priority: str = "normal",
    source_type: str = "ai_admin",
    task_group: str = "review",
    related_entity_type: str = "",
    related_entity_id: str = "",
    source_task_id: int | None = None,
    source_payload: dict | None = None,
    execution_context: dict | None = None,
    requires_human_confirmation: bool = False,
    queue_name: str | None = None,
    actor_type: str = "ai",
    actor_id: str = "system_ai",
    commit: bool = True,
) -> WorkTask:
    return create_task(
        db,
        title=title,
        description=description,
        priority=priority,
        source_type=source_type,
        task_group=task_group,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        source_task_id=source_task_id,
        source_payload=source_payload or {},
        execution_context=execution_context or {},
        requires_human_confirmation=requires_human_confirmation,
        queue_name=queue_name,
        actor_type=actor_type,
        actor_id=actor_id,
        commit=commit,
    )


def create_patrol_task(
    db: Session,
    *,
    scenario: str = "daily",
    actor_id: str = "system_ai_admin",
    commit: bool = True,
) -> WorkTask:
    tool_name, arguments, priority, task_group = PATROL_TOOLS.get(scenario, PATROL_TOOLS["daily"])
    return create_kernel_task(
        db,
        title=f"AI patrol task: {scenario}",
        description=f"AI Kernel patrol for {scenario}",
        priority=priority,
        source_type="patrol",
        task_group=task_group,
        source_payload={
            "kernel_intent": "patrol",
            "scenario": scenario,
            "tool_name": tool_name,
            "arguments": arguments,
        },
        execution_context={"entrypoint": "ai_kernel_patrol"},
        actor_type="ai",
        actor_id=actor_id,
        commit=commit,
    )


def process_patrol(
    db: Session,
    *,
    scenario: str = "daily",
    actor_id: str = "system_ai_admin",
    commit: bool = True,
    llm_client=None,
) -> dict:
    task = create_patrol_task(db, scenario=scenario, actor_id=actor_id, commit=False)
    result = process_task(db, task.task_code, worker_id=actor_id, commit=False, llm_client=llm_client)
    if commit:
        db.commit()
        db.refresh(task)
    return {
        "status": result["status"],
        "scenario": scenario,
        "run_id": result.get("run_id"),
        "run_code": result.get("run_code"),
        "task_code": task.task_code,
        "task": task_to_dict(task),
        "kernel": True,
    }


def create_reader_request_task(
    db: Session,
    reader: ReaderAccount,
    *,
    message: str,
    history: list[dict] | None = None,
    answer: str | None = None,
    tool_calls: list[dict] | None = None,
    llm_plan: dict | None = None,
    actor_id: str | None = None,
    commit: bool = True,
) -> WorkTask:
    reader_code = actor_id or reader.reader_code
    source_payload = {
        "kernel_intent": "reader_ai_chat",
        "reader_code": reader.reader_code,
        "message": message,
        "history": history or [],
        "answer": answer or "",
    }
    if tool_calls:
        source_payload["tool_calls"] = tool_calls
        if len(tool_calls) > 1:
            source_payload["process_subtasks_immediately"] = True
    if llm_plan:
        source_payload["llm_plan"] = llm_plan
    return create_kernel_task(
        db,
        title="Reader AI request",
        description=message[:500],
        priority="normal",
        source_type="reader_event",
        task_group="review",
        related_entity_type="reader",
        related_entity_id=str(reader.id),
        source_payload=source_payload,
        execution_context={"entrypoint": "reader_ai_chat", "reader_code": reader.reader_code},
        queue_name="reader_ops",
        actor_type="reader",
        actor_id=reader_code,
        commit=commit,
    )


def create_business_event_task(
    db: Session,
    *,
    action: str,
    title: str,
    description: str = "",
    priority: str = "normal",
    task_group: str = "review",
    related_entity_type: str = "",
    related_entity_id: str = "",
    payload: dict | None = None,
    actor_type: str = "system",
    actor_id: str = "system",
    commit: bool = True,
) -> WorkTask:
    source_type = "system"
    if actor_type == "reader":
        source_type = "reader_event"
    elif actor_type != "system":
        source_type = "ai_admin"
    return create_kernel_task(
        db,
        title=title,
        description=description,
        priority=priority,
        source_type=source_type,
        task_group=task_group,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        source_payload={"kernel_intent": "business_event", "action": action, "payload": payload or {}},
        execution_context={"entrypoint": "business_event", "action": action},
        actor_type=actor_type,
        actor_id=actor_id,
        commit=commit,
    )
