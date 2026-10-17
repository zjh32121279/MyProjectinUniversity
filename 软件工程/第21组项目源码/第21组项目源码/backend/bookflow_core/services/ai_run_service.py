from __future__ import annotations

import json

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from bookflow_core.core.exceptions import NotFoundError
from bookflow_core.models import AgentRun, AgentStep


def _json(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {"raw": raw}
    return data if isinstance(data, dict) else {"value": data}


def step_to_dict(row: AgentStep) -> dict:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "step_name": row.step_name,
        "status": row.status,
        "detail": _json(row.detail_json),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def run_to_dict(row: AgentRun, *, include_payload: bool = False, step_count: int | None = None) -> dict:
    data = {
        "id": row.id,
        "run_code": row.run_code,
        "actor_type": row.actor_type,
        "actor_id": row.actor_code,
        "tool_name": row.tool_name,
        "status": row.status,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
    if step_count is not None:
        data["step_count"] = step_count
    if include_payload:
        data["input"] = _json(row.input_json)
        data["output"] = _json(row.output_json)
    return data


def list_agent_runs(
    db: Session,
    *,
    status: str | None = None,
    tool_name: str | None = None,
    actor_id: str | None = None,
    include_payload: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    filters = []
    if status:
        filters.append(AgentRun.status == status)
    if tool_name:
        filters.append(AgentRun.tool_name == tool_name)
    if actor_id:
        filters.append(AgentRun.actor_code == actor_id)
    stmt = select(AgentRun)
    count_stmt = select(func.count(AgentRun.id))
    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)
    total = int(db.scalar(count_stmt) or 0)
    rows = db.scalars(stmt.order_by(AgentRun.id.desc()).offset(offset).limit(limit)).all()
    step_counts = {
        int(run_id): int(count)
        for run_id, count in db.execute(
            select(AgentStep.run_id, func.count(AgentStep.id))
            .where(AgentStep.run_id.in_([row.id for row in rows] or [-1]))
            .group_by(AgentStep.run_id)
        ).all()
    }
    return {
        "items": [run_to_dict(row, include_payload=include_payload, step_count=step_counts.get(row.id, 0)) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_agent_run(db: Session, run_code: str) -> dict:
    row = db.scalar(select(AgentRun).where(AgentRun.run_code == run_code))
    if not row:
        raise NotFoundError("Agent run not found.", code="AI_RUN_NOT_FOUND", details={"run_code": run_code})
    steps = db.scalars(select(AgentStep).where(AgentStep.run_id == row.id).order_by(AgentStep.id)).all()
    data = run_to_dict(row, include_payload=True, step_count=len(steps))
    data["steps"] = [step_to_dict(step) for step in steps]
    return data


def get_agent_run_by_id_or_code(db: Session, run_id: str | int) -> dict:
    if isinstance(run_id, int) or str(run_id).isdigit():
        row = db.get(AgentRun, int(run_id))
    else:
        row = db.scalar(select(AgentRun).where(AgentRun.run_code == str(run_id)))
    if not row:
        raise NotFoundError("Agent run not found.", code="AI_RUN_NOT_FOUND", details={"run_id": run_id})
    return get_agent_run(db, row.run_code)


def list_agent_steps(db: Session, run_code: str, *, step_name: str | None = None) -> dict:
    row = db.scalar(select(AgentRun).where(AgentRun.run_code == run_code))
    if not row:
        raise NotFoundError("Agent run not found.", code="AI_RUN_NOT_FOUND", details={"run_code": run_code})
    stmt = select(AgentStep).where(AgentStep.run_id == row.id)
    if step_name:
        stmt = stmt.where(AgentStep.step_name == step_name)
    steps = db.scalars(stmt.order_by(AgentStep.id)).all()
    return {"items": [step_to_dict(step) for step in steps], "total": len(steps), "run_code": run_code}


