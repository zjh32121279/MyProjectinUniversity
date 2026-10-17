from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from bookflow_core.ai.tools.policy_guard import normalize_tool_call
from bookflow_core.ai.tools.permissions import ToolPermissionDecision, decide_tool_permission
from bookflow_core.ai.tools.registry import get_tool_definition
from bookflow_core.core.exceptions import BookFlowError, BusinessRuleError, PermissionDeniedError, ValidationError
from bookflow_core.models import AgentRun, AgentStep, AIApprovalRequest, WorkTask
from bookflow_core.services.common import as_json, write_audit


def _run_code(tool_name: str) -> str:
    return f"RUN-{tool_name}-{int(datetime.now(timezone.utc).timestamp() * 1000000)}"


def _approval_code(tool_name: str) -> str:
    return f"GRANT-{tool_name}-{int(datetime.now(timezone.utc).timestamp() * 1000000)}"


def _create_approval(
    db: Session,
    *,
    run_id: int | None,
    tool_name: str,
    payload: dict,
    actor_id: str,
    decision: ToolPermissionDecision,
) -> dict:
    approval = AIApprovalRequest(
        approval_code=_approval_code(tool_name),
        run_id=run_id,
        requested_action=tool_name,
        payload_json=as_json(payload),
        status="waiting",
        requested_by_agent_run_id=run_id,
    )
    db.add(approval)
    db.flush()
    write_audit(
        db,
        actor_type="ai_admin",
        actor_id=actor_id,
        action="ai_tool_waiting_authorization",
        target_table="ai_approval_requests",
        target_id=approval.approval_code,
        detail={"tool_name": tool_name, "reason": decision.reason, "policy": decision.details},
    )
    return {
        "status": "waiting_authorization",
        "tool_name": tool_name,
        "approval_code": approval.approval_code,
        "reason": decision.reason,
        "policy": decision.details,
    }


def _missing_fields(details: dict) -> list[str]:
    missing = details.get("missing") or []
    if isinstance(missing, str):
        return [missing]
    if isinstance(missing, list):
        return [str(item) for item in missing if item not in (None, "")]
    field = details.get("field")
    return [str(field)] if field else []


def _clarification_result(db: Session, *, tool_name: str, payload: dict, actor_id: str, details: dict) -> dict:
    result = {
        "status": "needs_clarification",
        "tool_name": tool_name,
        "reason": details.get("reason") or "missing_required_information",
        "message": "执行前还需要补充必要信息，AI不能猜测关键字段并直接写入。",
        "missing_fields": _missing_fields(details),
        "details": details,
        "payload": payload,
    }
    write_audit(
        db,
        actor_type="ai_admin",
        actor_id=actor_id,
        action="ai_tool_needs_clarification",
        target_table="ai_capabilities",
        target_id=tool_name,
        detail=result,
    )
    return result


def dispatch_tool(
    db: Session,
    tool_name: str,
    payload: dict,
    *,
    actor_id: str,
    run_id: int | None = None,
    planner_context: bool = False,
    task: WorkTask | None = None,
    autonomous: bool = True,
) -> dict:
    definition = get_tool_definition(db, tool_name)
    try:
        normalized = normalize_tool_call(db, {"tool_name": tool_name, "arguments": payload}, planner_context=planner_context)
    except (BookFlowError, ValidationError) as exc:
        details = dict(getattr(exc, "details", {}) or {})
        if details.get("incomplete"):
            details.setdefault("tool_name", tool_name)
            return _clarification_result(db, tool_name=tool_name, payload=payload, actor_id=actor_id, details=details)
        raise

    decision = decide_tool_permission(definition, actor_id=actor_id, task=task, autonomous=autonomous)
    if decision.decision == "deny":
        raise PermissionDeniedError("This AI tool is forbidden.", code="AI_FORBIDDEN_OPERATION", details=decision.details)
    if decision.decision == "handoff":
        raise BusinessRuleError("AI tool requires human takeover.", details=decision.details)
    if decision.decision == "waiting_authorization":
        return _create_approval(db, run_id=run_id, tool_name=tool_name, payload=normalized["arguments"], actor_id=actor_id, decision=decision)
    if not definition.callable:
        raise BusinessRuleError("Tool dispatcher not implemented for this capability.", details={"tool_name": tool_name})
    result: dict = definition.callable(db, normalized["arguments"], actor_id=actor_id)
    write_audit(
        db,
        actor_type="ai_admin",
        actor_id=actor_id,
        action="ai_tool_success",
        target_table="ai_capabilities",
        target_id=tool_name,
        detail={"writes_db": definition.writes_db, "policy": decision.details},
    )
    return {"status": "success", "tool_name": tool_name, "data": result}


def invoke_tool(db: Session, tool_name: str, payload: dict, *, actor_id: str = "system_ai_admin", commit: bool = True) -> dict:
    try:
        run = AgentRun(
            run_code=_run_code(tool_name),
            actor_type="ai_admin",
            actor_code=actor_id,
            tool_name=tool_name,
            status="running",
            input_json=as_json(payload),
        )
        db.add(run)
        db.flush()
        try:
            result = dispatch_tool(db, tool_name, payload, actor_id=actor_id, run_id=run.id)
        except PermissionDeniedError:
            run.status = "rejected"
            db.add(AgentStep(run_id=run.id, step_name="permission_guard", status="rejected", detail_json=as_json({"permission_level": "L5"})))
            write_audit(db, actor_type="ai_admin", actor_id=actor_id, action="ai_tool_rejected", target_table="ai_capabilities", target_id=tool_name, result="rejected")
            if commit:
                db.commit()
            raise
        run.status = result["status"] if result["status"] in {"waiting_authorization", "needs_clarification"} else "success"
        run.output_json = as_json(result)
        step_name = (
            "create_super_admin_approval"
            if result["status"] == "waiting_authorization"
            else "needs_clarification"
            if result["status"] == "needs_clarification"
            else "execute_tool"
        )
        db.add(AgentStep(run_id=run.id, step_name=step_name, status=result["status"], detail_json=as_json(result)))
        if commit:
            db.commit()
        result.setdefault("run_code", run.run_code)
        return result
    except Exception:
        if commit:
            db.rollback()
        raise


def list_pending_approvals_for_run(db: Session, run_id: int) -> list[AIApprovalRequest]:
    return db.scalars(select(AIApprovalRequest).where(AIApprovalRequest.run_id == run_id, AIApprovalRequest.status == "waiting")).all()
