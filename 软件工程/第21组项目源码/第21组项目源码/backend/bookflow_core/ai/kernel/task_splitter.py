from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from bookflow_core.models import WorkTask
from bookflow_core.services.common import as_json, write_audit
from bookflow_core.services.task_service import create_task, record_task_event, task_to_dict

MAX_SPLIT_SUBTASKS = 10


def json_dict(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {"raw": raw}
    return data if isinstance(data, dict) else {"value": data}


def extract_tool_steps(payload: dict[str, Any], *, limit: int = MAX_SPLIT_SUBTASKS) -> list[dict[str, Any]]:
    raw_steps = payload.get("tool_calls") or payload.get("steps") or payload.get("tools") or []
    if not isinstance(raw_steps, list):
        return []
    steps: list[dict[str, Any]] = []
    for index, item in enumerate(raw_steps[:limit]):
        if not isinstance(item, dict):
            continue
        tool_name = item.get("tool_name") or item.get("name") or item.get("requested_tool")
        arguments = item.get("arguments")
        if arguments is None:
            arguments = item.get("payload") if isinstance(item.get("payload"), dict) else item.get("args", {})
        if not isinstance(tool_name, str) or not tool_name.strip():
            continue
        steps.append(
            {
                "tool_name": tool_name.strip(),
                "arguments": arguments if isinstance(arguments, dict) else {},
                "reason": str(item.get("reason") or f"subtask_{index + 1}"),
                "stop_on_failure": bool(item.get("stop_on_failure", True)),
            }
        )
    return steps


def should_split_task(payload: dict[str, Any]) -> bool:
    if payload.get("_task_package_child") or payload.get("_disable_task_split"):
        return False
    return len(extract_tool_steps(payload)) > 1


def _existing_children(db: Session, parent: WorkTask, package_id: str) -> list[WorkTask]:
    rows = db.scalars(
        select(WorkTask)
        .where(WorkTask.source_task_id == parent.id)
        .order_by(WorkTask.id.asc())
    ).all()
    result: list[WorkTask] = []
    for row in rows:
        payload = json_dict(row.source_payload_json)
        if payload.get("task_package_id") == package_id:
            result.append(row)
    return result


def create_task_package_children(
    db: Session,
    parent: WorkTask,
    *,
    actor_id: str,
    limit: int = MAX_SPLIT_SUBTASKS,
) -> dict[str, Any]:
    payload = json_dict(parent.source_payload_json)
    steps = extract_tool_steps(payload, limit=limit)
    package_id = str(payload.get("task_package_id") or f"PKG-{parent.task_code}")
    existing = _existing_children(db, parent, package_id)
    if existing:
        return {
            "status": "existing",
            "task_package_id": package_id,
            "parent_task_code": parent.task_code,
            "children": [task_to_dict(row) for row in existing],
            "created_count": 0,
        }

    original_intent = payload.get("message") or payload.get("admin_message") or payload.get("original_intent") or parent.description or parent.title
    children: list[WorkTask] = []
    previous_code = ""
    for index, step in enumerate(steps, start=1):
        child_payload = {
            "kernel_intent": "task_package_child",
            "_task_package_child": True,
            "_disable_task_split": True,
            "task_package_id": package_id,
            "parent_task_code": parent.task_code,
            "package_index": index,
            "depends_on_task_code": previous_code,
            "original_intent": original_intent,
            "tool_name": step["tool_name"],
            "arguments": step["arguments"],
            "reason": step["reason"],
            "stop_on_failure": step["stop_on_failure"],
        }
        child = create_task(
            db,
            title=f"{parent.title} / subtask {index}: {step['tool_name']}",
            description=str(step["reason"] or original_intent)[:500],
            priority=parent.priority or "normal",
            source_type=parent.source_type or "ai_admin",
            task_group=parent.task_group or "review",
            related_entity_type=parent.related_entity_type or "",
            related_entity_id=parent.related_entity_id or "",
            source_task_id=parent.id,
            source_payload=child_payload,
            execution_context={
                "entrypoint": "task_package_child",
                "task_package_id": package_id,
                "parent_task_code": parent.task_code,
                "depends_on_task_code": previous_code,
            },
            queue_name=parent.queue_name,
            max_attempts=parent.max_attempts,
            actor_type="ai",
            actor_id=actor_id,
            commit=False,
        )
        children.append(child)
        previous_code = child.task_code

    package_state = {
        "task_package_id": package_id,
        "parent_task_code": parent.task_code,
        "original_intent": original_intent,
        "children": [task_to_dict(row) for row in children],
        "created_count": len(children),
    }
    payload["task_package_id"] = package_id
    payload["split_child_task_codes"] = [row.task_code for row in children]
    parent.source_payload_json = as_json(payload)
    record_task_event(
        db,
        parent,
        event_type="ai_split_task_package",
        actor_type="ai",
        actor_id=actor_id,
        detail=package_state,
    )
    write_audit(
        db,
        actor_type="ai_admin",
        actor_id=actor_id,
        action="ai_split_task_package",
        target_table="work_tasks",
        target_id=parent.task_code,
        detail=package_state,
    )
    return {"status": "created", **package_state}
