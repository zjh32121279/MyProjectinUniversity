from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from bookflow_core.ai.tools.registry import ToolDefinition
    from bookflow_core.models import WorkTask

PermissionDecision = Literal["allow", "waiting_authorization", "deny", "handoff"]


@dataclass(frozen=True)
class ToolPermissionDecision:
    decision: PermissionDecision
    reason: str
    details: dict = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.decision == "allow"


def decide_tool_permission(
    definition: ToolDefinition,
    *,
    actor_id: str,
    task: WorkTask | None = None,
    autonomous: bool = True,
) -> ToolPermissionDecision:
    task_risk = str(getattr(task, "risk_level", "") or "").lower() if task is not None else ""
    audit_level = "standard"
    if definition.permission_level == "L4" or definition.requires_super_authorization or task_risk == "critical":
        audit_level = "strict"
    elif definition.risk_level == "high" or task_risk == "high":
        audit_level = "enhanced"
    details = {
        "tool_name": definition.tool_name,
        "actor_id": actor_id,
        "permission_level": definition.permission_level,
        "risk_level": definition.risk_level,
        "writes_db": definition.writes_db,
        "requires_super_authorization": definition.requires_super_authorization,
        "audit_level": audit_level,
        "risk_control": "permission_level_blocks_only_highest; business_risk_is_audit_and_trace_signal",
    }
    if task is not None:
        details.update(
            {
                "task_code": task.task_code,
                "task_risk_level": task.risk_level,
                "requires_human_confirmation": bool(task.requires_human_confirmation),
            }
        )

    if not definition.enabled:
        return ToolPermissionDecision("deny", "tool_disabled", details)
    if definition.permission_level == "L5":
        return ToolPermissionDecision("deny", "tool_forbidden", details)
    if definition.permission_level == "L4":
        return ToolPermissionDecision("waiting_authorization", "super_authorization_required", details)
    if definition.requires_super_authorization:
        if not autonomous and definition.permission_level == "L3":
            return ToolPermissionDecision("allow", "interactive_admin_operator_allowed", details)
        return ToolPermissionDecision("waiting_authorization", "super_authorization_required", details)

    if autonomous and task is not None:
        if bool(task.requires_human_confirmation):
            return ToolPermissionDecision("handoff", "task_requires_human_confirmation", details)

    return ToolPermissionDecision("allow", "policy_allows_execution", details)


def autonomous_policy_label(definition: ToolDefinition) -> str:
    if not definition.enabled:
        return "disabled"
    if definition.permission_level == "L5":
        return "forbidden"
    if definition.permission_level == "L4" or definition.requires_super_authorization:
        return "authorization_required"
    if definition.writes_db:
        if definition.risk_level == "high":
            return "auto_write_enhanced_audit"
        return "auto_write_with_task_risk_guard"
    return "auto_read"
