from __future__ import annotations

from datetime import datetime

WRITE_TOOL_HINTS = (
    "update",
    "borrow",
    "return",
    "renew",
    "cancel",
    "create",
    "batch",
    "mark",
    "fulfill",
    "scan",
    "adjust",
    "suspend",
    "restore",
    "send",
    "assign",
    "resolve",
)
HIGH_RISK_WRITE_HINTS = ("borrow", "return", "renew", "update", "fulfill", "adjust", "suspend", "restore")
READER_AUTONOMOUS_WRITE_TOOLS = {
    "ai_reader_create_borrow_request",
    "ai_reader_create_return_request",
    "ai_reader_create_reservation",
    "ai_reader_renew_borrow",
}
SUPER_AUTHORIZATION_TOOLS = {
    "ai_request_rule_change",
    "ai_request_high_risk_operation",
}

TOOL_DESCRIPTIONS = {
    "ai_search_books": (
        "Search live catalog books by natural-language title, author, ISBN, category, topic, "
        "series phrase, or location-related keyword. Use for reader/admin questions about whether "
        "the library has a book, genre, subject, series, availability, copies, or shelf locations."
    ),
    "ai_get_hot_books": "List currently high-demand books ranked by borrowing/reservation activity.",
    "ai_get_cold_books": "List low-circulation books ranked by long inactivity.",
    "ai_get_loans": "Query borrowing records by reader, book, copy, status, or keyword.",
    "ai_get_reservations": "Query reservation records by reader, book, copy, status, or keyword.",
    "ai_get_reader_activity": "Inspect one reader's borrow, reservation, overdue, and credit activity summary.",
    "ai_get_reader_detail": "Look up one reader profile by reader_code.",
    "ai_get_readers": "Search reader accounts by keyword, type, status, or credit status.",
    "ai_get_reader_borrow_summary": "Summarize one reader's borrowing statistics by reader_id.",
    "ai_reader_create_borrow_request": "Create a reader-side borrow service request for staff confirmation.",
    "ai_reader_create_return_request": "Create a reader-side return service request for staff confirmation.",
    "ai_reader_create_reservation": "Create a reader's reservation for a specific book.",
    "ai_reader_renew_borrow": "Renew a reader's eligible active loan.",
    "ai_borrow_copy": "Borrow a specific copy for a reader when staff-level arguments are complete.",
    "ai_return_copy": "Return a specific borrowed copy when staff-level arguments are complete.",
    "ai_renew_borrow": "Renew a specific loan by loan_id.",
    "ai_create_reservation": "Create a reservation for a reader and book.",
    "ai_cancel_reservation": "Cancel a specific reservation by reservation_id.",
    "ai_fulfill_reservation": "Mark a reservation as fulfilled after staff handling.",
    "ai_update_copy_status": "Update one copy's circulation status.",
    "ai_get_overdue_cases": "List overdue borrowing cases with optional filters.",
    "ai_get_overdue_summary": "Summarize current overdue workload and risks.",
    "ai_scan_overdues": "Scan active loans and create/update overdue risk items.",
    "ai_get_active_risks": "List active operational risk warnings.",
    "ai_get_risk_warnings": "List risk warning records.",
    "ai_get_dashboard": "Read dashboard summary metrics.",
    "ai_get_collection_health": "Analyze collection health, availability, hot/cold circulation, and inventory pressure.",
    "ai_get_circulation_analytics": "Analyze borrowing, returning, reservation, and circulation metrics.",
    "ai_get_reader_analytics": "Analyze reader composition, activity, and credit distribution.",
    "ai_get_risk_analytics": "Analyze operational risk distribution and trends.",
    "ai_get_efficiency": "Analyze AI/staff processing efficiency.",
    "ai_get_notification_summary": "Summarize notification delivery state.",
    "ai_get_task_summary": "Summarize active work task queues and status distribution.",
    "ai_get_rule_summary": "Summarize active circulation rules and policies.",
    "ai_get_dashboard_explanation": "Explain current dashboard metrics using BookFlow data.",
    "ai_get_operational_brief": "Generate an operations brief from current metrics, tasks, and risks.",
    "ai_get_admin_security_summary": "Summarize administrator security state.",
    "ai_get_admin_events": "List administrator audit/security events.",
    "ai_get_admins": "List administrator accounts and status.",
    "ai_create_work_task": "Create one work task for staff follow-up.",
    "ai_batch_create_tasks": "Create multiple work tasks from concrete items.",
    "ai_batch_mark_low_risk_tasks": "Mark eligible low-risk task items in batch.",
    "ai_get_tasks": "Search work tasks by status, source, priority, group, or keyword.",
    "ai_assign_task_to_admin": "Assign a task to a specific administrator.",
    "ai_resolve_work_task": "Resolve a work task with a resolution note.",
    "ai_create_notification": "Create a notification message for reader/admin recipients.",
    "ai_batch_create_notifications": "Create notification messages for a concrete recipient batch.",
    "ai_send_notification": "Send a prepared notification message.",
    "ai_create_task_notifications": "Create notifications for task-related events.",
    "ai_adjust_reader_credit": "Adjust a reader credit score with a reason.",
    "ai_suspend_reader": "Suspend a reader account with a reason.",
    "ai_restore_reader": "Restore a suspended reader account with a reason.",
    "ai_request_rule_change": "Request a circulation rule/system setting/policy change requiring super-admin authorization.",
    "ai_request_batch_status_change": "Request a batch copy-status change for human/super-admin review.",
    "ai_request_high_risk_operation": "Request a high-risk operation for authorization instead of executing it directly.",
}


def infer_tool_defaults(tool_name: str, *, stamp: datetime | None = None) -> dict:
    writes = any(hint in tool_name for hint in WRITE_TOOL_HINTS)
    if tool_name in READER_AUTONOMOUS_WRITE_TOOLS:
        writes = True
        risk_level = "medium"
    else:
        risk_level = "high" if writes and any(hint in tool_name for hint in HIGH_RISK_WRITE_HINTS) else ("medium" if writes else "low")
    requires_super_authorization = tool_name in SUPER_AUTHORIZATION_TOOLS
    data = {
        "tool_name": tool_name,
        "display_name": tool_name,
        "permission_level": "L4" if requires_super_authorization else ("L3" if writes else "L1"),
        "risk_level": risk_level,
        "is_write": writes,
        "writes_db": writes,
        "requires_super_authorization": requires_super_authorization,
        "input_schema_json": "{}",
        "output_schema_json": "{}",
        "is_enabled": True,
        "description": TOOL_DESCRIPTIONS.get(tool_name, f"Built-in BookFlow AI tool: {tool_name}"),
    }
    if stamp is not None:
        data["created_at"] = stamp
        data["updated_at"] = stamp
    return data
