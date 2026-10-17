from __future__ import annotations

from sqlalchemy.orm import Session

from bookflow_core.ai.tools.registry import ToolDefinition, get_tool_definition
from bookflow_core.ai_tools.validation import validate_tool_payload
from bookflow_core.core.exceptions import BookFlowError, NotFoundError, ValidationError


def validate_tool_call_allowed(db: Session, tool_name: str) -> ToolDefinition:
    try:
        definition = get_tool_definition(db, tool_name)
    except NotFoundError as exc:
        raise BookFlowError("LLM selected an unknown or disabled AI tool.", code="AI_TOOL_CALL_INVALID", details={"tool_name": tool_name}) from exc
    if not definition.enabled:
        raise BookFlowError("LLM selected an unknown or disabled AI tool.", code="AI_TOOL_CALL_INVALID", details={"tool_name": tool_name})
    if definition.permission_level == "L5":
        raise BookFlowError("LLM selected a forbidden AI tool.", code="AI_FORBIDDEN_OPERATION", details={"tool_name": tool_name})
    return definition


def normalize_tool_call(db: Session, call: dict, *, index: int = 0, planner_context: bool = True) -> dict:
    if not isinstance(call, dict):
        raise BookFlowError("LLM tool call must be an object.", code="AI_PLANNER_OUTPUT_INVALID", details={"index": index})
    tool_name = call.get("tool_name")
    arguments = call.get("arguments", call.get("payload", {}))
    if not isinstance(tool_name, str) or not tool_name:
        raise BookFlowError("LLM tool call missing tool_name.", code="AI_PLANNER_OUTPUT_INVALID", details={"index": index})
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise BookFlowError("LLM tool arguments must be an object.", code="AI_PLANNER_OUTPUT_INVALID", details={"index": index, "tool_name": tool_name})
    definition = validate_tool_call_allowed(db, tool_name)
    try:
        payload = validate_tool_payload(tool_name, arguments)
    except ValidationError as exc:
        if not planner_context:
            raise
        raise BookFlowError(
            "LLM tool payload does not match the tool schema.",
            code="AI_PLANNER_OUTPUT_INVALID",
            details={"index": index, "tool_name": tool_name, **exc.details},
        ) from exc
    corrections = {}
    for field, expected in {
        "permission_level": definition.permission_level,
        "risk_level": definition.risk_level,
        "writes_db": definition.writes_db,
        "requires_super_authorization": definition.requires_super_authorization,
    }.items():
        if field in call and call[field] != expected:
            corrections[field] = {"model": call[field], "registry": expected}
    return {
        "tool_name": tool_name,
        "arguments": payload,
        "payload": payload,
        "permission_level": definition.permission_level,
        "risk_level": definition.risk_level,
        "writes_db": definition.writes_db,
        "requires_super_authorization": definition.requires_super_authorization,
        "policy_corrections": corrections,
    }
