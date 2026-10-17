from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from bookflow_core.ai.tools.capability_defaults import infer_tool_defaults
from bookflow_core.ai.tools.schema_builder import TOOL_INPUT_SCHEMAS
from bookflow_core.ai_tools.analytics import (
    ai_get_active_risks,
    ai_get_admin_events,
    ai_get_admin_security_summary,
    ai_get_admins,
    ai_get_circulation_analytics,
    ai_get_collection_health,
    ai_get_dashboard,
    ai_get_dashboard_explanation,
    ai_get_efficiency,
    ai_get_notification_summary,
    ai_get_operational_brief,
    ai_get_overdue_summary,
    ai_get_reader_analytics,
    ai_get_reader_borrow_summary,
    ai_get_reader_detail,
    ai_get_risk_analytics,
    ai_get_risk_warnings,
    ai_get_rule_summary,
    ai_get_task_summary,
)
from bookflow_core.ai_tools.catalog import ai_get_cold_books, ai_get_hot_books, ai_search_books, ai_update_copy_status
from bookflow_core.ai_tools.circulation import (
    ai_borrow_copy,
    ai_cancel_reservation,
    ai_create_reservation,
    ai_fulfill_reservation,
    ai_get_loans,
    ai_get_overdue_cases,
    ai_get_reservations,
    ai_renew_borrow,
    ai_return_copy,
    ai_scan_overdues,
)
from bookflow_core.ai_tools.notification import (
    ai_batch_create_notifications,
    ai_create_notification,
    ai_create_task_notifications,
    ai_send_notification,
)
from bookflow_core.ai_tools.reader import (
    ai_adjust_reader_credit,
    ai_get_reader_activity,
    ai_get_readers,
    ai_restore_reader,
    ai_suspend_reader,
)
from bookflow_core.ai_tools.reader_circulation import (
    ai_reader_create_borrow_request,
    ai_reader_create_reservation,
    ai_reader_create_return_request,
    ai_reader_renew_borrow,
)
from bookflow_core.ai_tools.task import (
    ai_assign_task_to_admin,
    ai_batch_create_tasks,
    ai_batch_mark_low_risk_tasks,
    ai_create_work_task,
    ai_get_tasks,
    ai_resolve_work_task,
)
from bookflow_core.core.exceptions import NotFoundError
from bookflow_core.models import AICapability

ToolCallable = Callable[[Session, dict], dict]

_TOOL_MAP: dict[str, Callable] = {
    "ai_get_hot_books": ai_get_hot_books,
    "ai_get_cold_books": ai_get_cold_books,
    "ai_search_books": ai_search_books,
    "ai_update_copy_status": ai_update_copy_status,
    "ai_borrow_copy": ai_borrow_copy,
    "ai_return_copy": ai_return_copy,
    "ai_renew_borrow": ai_renew_borrow,
    "ai_cancel_reservation": ai_cancel_reservation,
    "ai_create_reservation": ai_create_reservation,
    "ai_fulfill_reservation": ai_fulfill_reservation,
    "ai_scan_overdues": ai_scan_overdues,
    "ai_get_loans": ai_get_loans,
    "ai_get_overdue_cases": ai_get_overdue_cases,
    "ai_get_reservations": ai_get_reservations,
    "ai_create_notification": ai_create_notification,
    "ai_batch_create_notifications": ai_batch_create_notifications,
    "ai_send_notification": ai_send_notification,
    "ai_create_task_notifications": ai_create_task_notifications,
    "ai_create_work_task": ai_create_work_task,
    "ai_batch_create_tasks": ai_batch_create_tasks,
    "ai_batch_mark_low_risk_tasks": ai_batch_mark_low_risk_tasks,
    "ai_get_tasks": ai_get_tasks,
    "ai_assign_task_to_admin": ai_assign_task_to_admin,
    "ai_resolve_work_task": ai_resolve_work_task,
    "ai_get_readers": ai_get_readers,
    "ai_get_reader_activity": ai_get_reader_activity,
    "ai_adjust_reader_credit": ai_adjust_reader_credit,
    "ai_suspend_reader": ai_suspend_reader,
    "ai_restore_reader": ai_restore_reader,
    "ai_reader_create_borrow_request": ai_reader_create_borrow_request,
    "ai_reader_create_return_request": ai_reader_create_return_request,
    "ai_reader_create_reservation": ai_reader_create_reservation,
    "ai_reader_renew_borrow": ai_reader_renew_borrow,
    "ai_get_active_risks": ai_get_active_risks,
    "ai_get_risk_warnings": ai_get_risk_warnings,
    "ai_get_dashboard": ai_get_dashboard,
    "ai_get_collection_health": ai_get_collection_health,
    "ai_get_circulation_analytics": ai_get_circulation_analytics,
    "ai_get_reader_analytics": ai_get_reader_analytics,
    "ai_get_risk_analytics": ai_get_risk_analytics,
    "ai_get_efficiency": ai_get_efficiency,
    "ai_get_overdue_summary": ai_get_overdue_summary,
    "ai_get_notification_summary": ai_get_notification_summary,
    "ai_get_task_summary": ai_get_task_summary,
    "ai_get_rule_summary": ai_get_rule_summary,
    "ai_get_reader_detail": ai_get_reader_detail,
    "ai_get_reader_borrow_summary": ai_get_reader_borrow_summary,
    "ai_get_dashboard_explanation": ai_get_dashboard_explanation,
    "ai_get_operational_brief": ai_get_operational_brief,
    "ai_get_admin_security_summary": ai_get_admin_security_summary,
    "ai_get_admin_events": ai_get_admin_events,
    "ai_get_admins": ai_get_admins,
}


@dataclass(frozen=True)
class ToolDefinition:
    tool_name: str
    display_name: str
    description: str
    permission_level: str
    risk_level: str
    writes_db: bool
    requires_super_authorization: bool
    input_schema: dict
    output_schema: dict
    callable: Callable | None
    enabled: bool


def registered_tool_names() -> list[str]:
    return sorted(_TOOL_MAP)


def _ensure_tool_capability(db: Session, tool_name: str) -> AICapability | None:
    if tool_name not in _TOOL_MAP:
        return None
    cap = AICapability(**infer_tool_defaults(tool_name))
    db.add(cap)
    db.flush()
    return cap


def _sync_tool_capability(cap: AICapability) -> AICapability:
    defaults = infer_tool_defaults(cap.tool_name)
    for field in (
        "permission_level",
        "risk_level",
        "is_write",
        "writes_db",
        "requires_super_authorization",
        "description",
    ):
        value = defaults[field]
        if getattr(cap, field) != value:
            setattr(cap, field, value)
    return cap


def get_tool_definition(db: Session, tool_name: str) -> ToolDefinition:
    cap = db.scalar(select(AICapability).where(AICapability.tool_name == tool_name))
    if not cap:
        cap = _ensure_tool_capability(db, tool_name)
    if not cap:
        raise NotFoundError("AI capability not found.", code="AI_TOOL_NOT_FOUND", details={"tool_name": tool_name})
    cap = _sync_tool_capability(cap)
    if not cap.is_enabled:
        raise NotFoundError("AI capability not found.", code="AI_TOOL_NOT_FOUND", details={"tool_name": tool_name})
    return ToolDefinition(
        tool_name=cap.tool_name,
        display_name=cap.display_name,
        description=cap.description,
        permission_level=cap.permission_level,
        risk_level=cap.risk_level,
        writes_db=bool(cap.writes_db),
        requires_super_authorization=bool(cap.requires_super_authorization),
        input_schema=TOOL_INPUT_SCHEMAS.get(cap.tool_name, {"type": "object"}),
        output_schema={},
        callable=_TOOL_MAP.get(cap.tool_name),
        enabled=bool(cap.is_enabled),
    )

