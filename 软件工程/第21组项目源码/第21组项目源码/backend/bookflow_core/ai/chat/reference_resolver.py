from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from bookflow_core.models import AgentRun, WorkTask
from bookflow_core.services.task_service import task_to_dict


def _json(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {"raw": raw}
    return data if isinstance(data, dict) else {"value": data}


def recent_kernel_runs(db: Session, *, limit: int = 5) -> list[dict]:
    rows = db.scalars(
        select(AgentRun)
        .where(AgentRun.tool_name == "ai_kernel_task_agent")
        .order_by(AgentRun.id.desc())
        .limit(max(1, min(int(limit), 20)))
    ).all()
    return [
        {
            "run_code": row.run_code,
            "status": row.status,
            "actor_id": row.actor_code,
            "input": _json(row.input_json),
            "output": _json(row.output_json),
            "created_at": row.created_at,
        }
        for row in rows
    ]


def unresolved_ai_tasks(db: Session, *, limit: int = 10) -> list[dict]:
    rows = db.scalars(
        select(WorkTask)
        .where(WorkTask.status.in_(["pending", "ai_processing", "waiting_human"]))
        .order_by(WorkTask.priority_score.desc(), WorkTask.id.desc())
        .limit(max(1, min(int(limit), 50)))
    ).all()
    return [task_to_dict(row) for row in rows]


def build_reference_context(db: Session) -> dict:
    return {
        "recent_kernel_runs": recent_kernel_runs(db, limit=5),
        "unresolved_ai_tasks": unresolved_ai_tasks(db, limit=10),
    }
