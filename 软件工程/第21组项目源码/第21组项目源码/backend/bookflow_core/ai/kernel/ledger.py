from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from bookflow_core.core.time import now
from bookflow_core.models import AIExecutionLedger, WorkTask
from bookflow_core.services.common import as_json


COMPLETED_LEDGER_STATUS = "completed"


def _code() -> str:
    return f"LEDGER-{int(datetime.now(timezone.utc).timestamp() * 1000000)}"


def _stable_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def default_idempotency_key(task: WorkTask, *, sop_id: str, phase: str, tool_name: str, arguments: dict[str, Any]) -> str:
    return _stable_json(
        {
            "task_code": task.task_code,
            "sop_id": sop_id,
            "phase": phase,
            "tool_name": tool_name,
            "arguments": arguments,
        }
    )


def completed_execution(db: Session, idempotency_key: str) -> AIExecutionLedger | None:
    if not idempotency_key:
        return None
    return db.scalar(
        select(AIExecutionLedger).where(
            AIExecutionLedger.idempotency_key == idempotency_key,
            AIExecutionLedger.status == COMPLETED_LEDGER_STATUS,
        )
    )


def ledger_to_skipped_result(row: AIExecutionLedger) -> dict:
    return {
        "status": "skipped",
        "tool_name": row.tool_name,
        "reason": "idempotency_key_already_completed",
        "ledger_code": row.ledger_code,
        "idempotency_key": row.idempotency_key,
        "target_type": row.target_type,
        "target_id": row.target_id,
    }


def record_execution_attempt(
    db: Session,
    *,
    task: WorkTask,
    run_id: int | None,
    sop_id: str,
    phase: str,
    tool_name: str,
    idempotency_key: str,
    target_type: str = "",
    target_id: str = "",
    arguments: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    status: str,
    reason: str = "",
) -> AIExecutionLedger:
    existing = db.scalar(select(AIExecutionLedger).where(AIExecutionLedger.idempotency_key == idempotency_key))
    row = existing or AIExecutionLedger(
        ledger_code=_code(),
        task_id=task.id,
        task_code=task.task_code,
        run_id=run_id,
        sop_id=sop_id,
        phase=phase,
        tool_name=tool_name,
        idempotency_key=idempotency_key,
        target_type=target_type,
        target_id=target_id,
        created_at=now(),
    )
    row.status = status
    row.reason = reason
    row.request_json = as_json(arguments or {})
    row.result_json = as_json(result or {})
    row.updated_at = now()
    if existing is None:
        db.add(row)
    db.flush()
    return row
