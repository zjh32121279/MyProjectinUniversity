from __future__ import annotations

from typing import Any
from bookflow_core.core.exceptions import ValidationError

COPY_STATUSES = {"available", "borrowed", "reserved", "maintenance"}
READER_TYPES = {"child", "teen", "adult", "senior", "institution"}
CIRCULATION_TYPES = {"hot", "normal", "cold"}
SYSTEM_VALUE_TYPES = {"int", "string", "bool", "float"}
ADMIN_ROLES = {"admin", "super_admin"}
ADMIN_EVENT_TYPES = {"login_success", "login_failed", "password_changed", "disabled", "enabled", "permission_check", "logout"}
LOAN_STATUSES = {"active", "borrowed", "renewable", "overdue", "returned"}
OVERDUE_CASE_STATUSES = {"active", "resolved"}
RESERVATION_STATUSES = {"active", "waiting", "ready", "ready_for_pickup", "fulfilled", "cancelled", "expired"}
READER_STATUSES = {"active", "inactive", "suspended"}
READER_CREDIT_STATUSES = {"good", "limited", "suspended"}
TASK_STATUSES = {"pending", "ai_processing", "waiting_human", "admin_processing", "resolved", "cancelled"}
TASK_PRIORITIES = {"low", "normal", "high", "urgent"}
BOOK_AVAILABILITY = {"available", "unavailable", "none"}
BOOK_SEARCH_SORTS = {"availability", "newest", "title"}
NOTIFICATION_RECIPIENT_TYPES = {"reader", "admin", "all", "all_readers", "all_admins"}


def _require(payload: dict[str, Any], *names: str) -> None:
    missing = [name for name in names if name not in payload or payload[name] in (None, "")]
    if missing:
        raise ValidationError(
            "AI tool payload missing required fields.",
            details={"missing": missing, "incomplete": True, "reason": "missing_required_fields"},
        )


def _ensure_int_range(payload: dict[str, Any], name: str, *, min_value: int | None = None, max_value: int | None = None, required: bool = False) -> None:
    if name not in payload or payload[name] is None:
        if required:
            raise ValidationError(
                "AI tool payload missing required integer field.",
                details={"missing": [name], "field": name, "incomplete": True, "reason": "missing_required_fields"},
            )
        return
    try:
        value = int(payload[name])
    except (TypeError, ValueError):
        raise ValidationError("AI tool payload field must be an integer.", details={"field": name, "value": payload[name]})
    if min_value is not None and value < min_value:
        raise ValidationError("AI tool payload integer is below allowed range.", details={"field": name, "min_value": min_value, "value": value})
    if max_value is not None and value > max_value:
        raise ValidationError("AI tool payload integer is above allowed range.", details={"field": name, "max_value": max_value, "value": value})
    payload[name] = value


def _ensure_recipients(payload: dict[str, Any]) -> None:
    _require(payload, "title", "content")
    recipients = payload.get("recipients")
    if not isinstance(recipients, list) or not recipients:
        raise ValidationError(
            "AI notification tool requires a non-empty recipients list.",
            details={"missing": ["recipients"], "field": "recipients", "incomplete": True, "reason": "missing_required_fields"},
        )
    for index, item in enumerate(recipients):
        if not isinstance(item, dict):
            raise ValidationError("AI notification recipient must be an object.", details={"index": index})
        recipient_type = item.get("recipient_type")
        if recipient_type not in NOTIFICATION_RECIPIENT_TYPES:
            raise ValidationError("Invalid notification recipient_type.", details={"index": index, "recipient_type": item.get("recipient_type")})
        if recipient_type in {"reader", "admin"} and not item.get("recipient_id"):
            raise ValidationError(
                "Notification recipient_id is required.",
                details={"missing": [f"recipients[{index}].recipient_id"], "index": index, "incomplete": True, "reason": "missing_required_fields"},
            )


def validate_tool_payload(tool_name: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    """Validate AI tool payloads before permission/dispatch.

    This is intentionally explicit rather than permissive: AI tools are a controlled Core surface,
    not free-form JSON accepted by business services.
    """
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValidationError("AI tool payload must be a JSON object.", details={"tool_name": tool_name})

    data = dict(payload)
    if tool_name in {"ai_get_hot_books", "ai_get_cold_books", "ai_get_active_risks", "ai_get_risk_warnings", "ai_get_dashboard", "ai_get_collection_health", "ai_get_circulation_analytics", "ai_get_reader_analytics", "ai_get_risk_analytics", "ai_get_efficiency", "ai_get_overdue_summary", "ai_get_dashboard_explanation", "ai_get_operational_brief"}:
        _ensure_int_range(data, "limit", min_value=1, max_value=100)
        return data

    if tool_name == "ai_search_books":
        _ensure_int_range(data, "limit", min_value=1, max_value=20)
        if data.get("availability") and data["availability"] not in BOOK_AVAILABILITY:
            raise ValidationError("Invalid book availability for AI tool.", details={"availability": data.get("availability")})
        if data.get("sort") and data["sort"] not in BOOK_SEARCH_SORTS:
            raise ValidationError("Invalid book search sort for AI tool.", details={"sort": data.get("sort")})
        return data

    if tool_name == "ai_get_loans":
        _ensure_int_range(data, "reader_id", min_value=1)
        _ensure_int_range(data, "book_id", min_value=1)
        _ensure_int_range(data, "copy_id", min_value=1)
        _ensure_int_range(data, "limit", min_value=1, max_value=100)
        _ensure_int_range(data, "offset", min_value=0)
        if data.get("status") and data["status"] not in LOAN_STATUSES:
            raise ValidationError("Invalid loan status for AI tool.", details={"status": data.get("status")})
        return data

    if tool_name == "ai_get_overdue_cases":
        _ensure_int_range(data, "min_overdue_days", min_value=0)
        _ensure_int_range(data, "max_overdue_days", min_value=0)
        _ensure_int_range(data, "limit", min_value=1, max_value=100)
        _ensure_int_range(data, "offset", min_value=0)
        if data.get("status") and data["status"] not in OVERDUE_CASE_STATUSES:
            raise ValidationError("Invalid overdue case status for AI tool.", details={"status": data.get("status")})
        return data

    if tool_name == "ai_get_reservations":
        _ensure_int_range(data, "reader_id", min_value=1)
        _ensure_int_range(data, "book_id", min_value=1)
        _ensure_int_range(data, "copy_id", min_value=1)
        _ensure_int_range(data, "limit", min_value=1, max_value=100)
        _ensure_int_range(data, "offset", min_value=0)
        if data.get("status") and data["status"] not in RESERVATION_STATUSES:
            raise ValidationError("Invalid reservation status for AI tool.", details={"status": data.get("status")})
        return data

    if tool_name in {"ai_get_notification_summary", "ai_get_task_summary", "ai_get_rule_summary", "ai_get_admin_security_summary"}:
        return data

    if tool_name == "ai_get_admins":
        _ensure_int_range(data, "limit", min_value=1, max_value=100)
        if data.get("role") and data["role"] not in ADMIN_ROLES:
            raise ValidationError("Invalid admin role for AI tool.", details={"role": data.get("role")})
        return data

    if tool_name == "ai_get_admin_events":
        _ensure_int_range(data, "limit", min_value=1, max_value=100)
        if data.get("event_type") and data["event_type"] not in ADMIN_EVENT_TYPES:
            raise ValidationError("Invalid admin event type for AI tool.", details={"event_type": data.get("event_type")})
        return data

    if tool_name == "ai_get_reader_detail":
        _require(data, "reader_code")
        return data

    if tool_name == "ai_get_reader_borrow_summary":
        _ensure_int_range(data, "reader_id", min_value=1, required=True)
        return data

    if tool_name == "ai_get_readers":
        _ensure_int_range(data, "limit", min_value=1, max_value=100)
        _ensure_int_range(data, "offset", min_value=0)
        if data.get("reader_type_code") and data["reader_type_code"] not in READER_TYPES:
            raise ValidationError("Invalid reader_type_code for AI tool.", details={"reader_type_code": data.get("reader_type_code")})
        if data.get("status") and data["status"] not in READER_STATUSES:
            raise ValidationError("Invalid reader status for AI tool.", details={"status": data.get("status")})
        if data.get("credit_status") and data["credit_status"] not in READER_CREDIT_STATUSES:
            raise ValidationError("Invalid reader credit status for AI tool.", details={"credit_status": data.get("credit_status")})
        return data

    if tool_name == "ai_get_reader_activity":
        _require(data, "reader_code")
        return data

    if tool_name == "ai_reader_create_borrow_request":
        _require(data, "reader_code")
        _ensure_int_range(data, "book_id", min_value=1)
        _ensure_int_range(data, "copy_id", min_value=1)
        if not data.get("book_id") and not data.get("book_code") and not data.get("copy_id"):
            raise ValidationError(
                "AI reader borrow request requires book_id, book_code, or copy_id.",
                details={
                    "tool_name": tool_name,
                    "missing": ["book_id|book_code|copy_id"],
                    "incomplete": True,
                    "reason": "missing_required_book_identifier",
                },
            )
        return data

    if tool_name == "ai_reader_create_return_request":
        _require(data, "reader_code")
        _ensure_int_range(data, "loan_id", min_value=1)
        if not data.get("loan_id") and not data.get("copy_code"):
            raise ValidationError(
                "AI reader return request requires loan_id or copy_code.",
                details={
                    "tool_name": tool_name,
                    "missing": ["loan_id|copy_code"],
                    "incomplete": True,
                    "reason": "missing_required_loan_or_copy_identifier",
                },
            )
        return data

    if tool_name == "ai_reader_create_reservation":
        _require(data, "reader_code")
        _ensure_int_range(data, "book_id", min_value=1)
        if not data.get("book_id") and not data.get("book_code"):
            raise ValidationError(
                "AI reader reservation requires book_id or book_code.",
                details={
                    "tool_name": tool_name,
                    "missing": ["book_id|book_code"],
                    "incomplete": True,
                    "reason": "missing_required_book_identifier",
                },
            )
        return data

    if tool_name == "ai_reader_renew_borrow":
        _require(data, "reader_code")
        _ensure_int_range(data, "loan_id", min_value=1, required=True)
        return data

    if tool_name == "ai_adjust_reader_credit":
        _require(data, "reader_code", "reason")
        _ensure_int_range(data, "delta", min_value=-100, max_value=100, required=True)
        _ensure_int_range(data, "related_loan_id", min_value=1)
        return data

    if tool_name in {"ai_suspend_reader", "ai_restore_reader"}:
        _require(data, "reader_code", "reason")
        return data

    if tool_name in {"ai_update_copy_status", "ai_request_copy_status_change"}:
        _require(data, "copy_code", "new_status")
        if data["new_status"] not in COPY_STATUSES:
            raise ValidationError("Invalid copy status for AI tool.", details={"new_status": data["new_status"]})
        return data

    if tool_name == "ai_borrow_copy":
        _require(data, "reader_code", "copy_code")
        return data

    if tool_name == "ai_return_copy":
        _require(data, "copy_code")
        return data

    if tool_name == "ai_renew_borrow":
        _ensure_int_range(data, "loan_id", min_value=1, required=True)
        return data

    if tool_name == "ai_cancel_reservation":
        _ensure_int_range(data, "reservation_id", min_value=1, required=True)
        return data

    if tool_name == "ai_create_reservation":
        _require(data, "reader_code", "book_code")
        return data

    if tool_name == "ai_fulfill_reservation":
        _ensure_int_range(data, "reservation_id", min_value=1, required=True)
        return data

    if tool_name == "ai_scan_overdues":
        return data

    if tool_name == "ai_create_notification":
        _require(data, "recipient_type", "title", "content")
        if data["recipient_type"] not in NOTIFICATION_RECIPIENT_TYPES:
            raise ValidationError("Invalid notification recipient_type.", details={"recipient_type": data["recipient_type"]})
        if data["recipient_type"] in {"reader", "admin"}:
            _require(data, "recipient_id")
        return data

    if tool_name == "ai_send_notification":
        _ensure_int_range(data, "notification_id", min_value=1, required=True)
        return data

    if tool_name == "ai_create_task_notifications":
        return data

    if tool_name == "ai_batch_create_notifications":
        _ensure_recipients(data)
        if len(data["recipients"]) > 100:
            raise ValidationError("AI notification batch cannot exceed 100 recipients.", details={"count": len(data["recipients"])})
        return data

    if tool_name == "ai_batch_create_tasks":
        tasks = data.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            raise ValidationError(
                "AI task batch requires a non-empty tasks list.",
                details={"missing": ["tasks"], "field": "tasks", "incomplete": True, "reason": "missing_required_fields"},
            )
        if len(tasks) > 50:
            raise ValidationError("AI task batch cannot exceed 50 tasks.", details={"count": len(tasks)})
        for item in tasks:
            if not isinstance(item, dict) or not item.get("title"):
                raise ValidationError(
                    "Each AI task batch item requires title.",
                    details={"missing": ["tasks[].title"], "item": item, "incomplete": True, "reason": "missing_required_fields"},
                )
            if item.get("priority", "normal") not in {"low", "normal", "high", "urgent"}:
                raise ValidationError("Invalid AI task priority.", details={"priority": item.get("priority")})
        return data

    if tool_name == "ai_batch_mark_low_risk_tasks":
        _ensure_int_range(data, "limit", min_value=1, max_value=100)
        return data

    if tool_name == "ai_create_work_task":
        _require(data, "title")
        if data.get("priority", "normal") not in {"low", "normal", "high", "urgent"}:
            raise ValidationError("Invalid AI task priority.", details={"priority": data.get("priority")})
        return data

    if tool_name == "ai_get_tasks":
        _ensure_int_range(data, "limit", min_value=1, max_value=100)
        _ensure_int_range(data, "offset", min_value=0)
        if data.get("status") and data["status"] not in TASK_STATUSES:
            raise ValidationError("Invalid task status for AI tool.", details={"status": data.get("status")})
        if data.get("priority") and data["priority"] not in TASK_PRIORITIES:
            raise ValidationError("Invalid task priority for AI tool.", details={"priority": data.get("priority")})
        return data

    if tool_name == "ai_assign_task_to_admin":
        _require(data, "task_code", "admin_code")
        return data

    if tool_name == "ai_resolve_work_task":
        _require(data, "task_code")
        return data

    if tool_name in {"ai_request_batch_status_change", "ai_request_high_risk_operation"}:
        _require(data, "reason")
        return data

    if tool_name == "ai_request_rule_change":
        if "change_type" not in data:
            # Backward-compatible shorthand used in early Step tests: request changing the adult/normal borrow rule.
            data["change_type"] = "borrow_rule"
            data.setdefault("circulation_type", "normal")
        _require(data, "change_type")
        change_type = data["change_type"]
        if change_type == "borrow_rule":
            _require(data, "reader_type_code", "circulation_type")
            if data["reader_type_code"] not in READER_TYPES:
                raise ValidationError("Invalid reader_type_code for rule change.", details={"reader_type_code": data["reader_type_code"]})
            if data["circulation_type"] not in CIRCULATION_TYPES:
                raise ValidationError("Invalid circulation_type for rule change.", details={"circulation_type": data["circulation_type"]})
            _ensure_int_range(data, "max_borrow_count", min_value=1)
            _ensure_int_range(data, "borrow_days", min_value=1)
            _ensure_int_range(data, "max_renewals", min_value=0)
            return data
        if change_type == "system_setting":
            _require(data, "key", "value")
            if data.get("value_type") and data["value_type"] not in SYSTEM_VALUE_TYPES:
                raise ValidationError("Invalid system rule value_type.", details={"value_type": data["value_type"]})
            return data
        if change_type == "circulation_policy":
            fields = data.get("fields")
            if not isinstance(fields, dict) or not fields:
                raise ValidationError("circulation_policy rule change requires non-empty fields.", details={"field": "fields"})
            for key, value in list(fields.items()):
                if key not in {"hot_borrow_90d_threshold", "hot_reserve_90d_threshold", "cold_borrow_365d_threshold", "cold_days_since_last_borrow_threshold"}:
                    raise ValidationError("Unsupported circulation policy field.", details={"field": key})
                try:
                    fields[key] = int(value)
                except (TypeError, ValueError):
                    raise ValidationError("Circulation policy field must be integer.", details={"field": key, "value": value})
                if fields[key] < 0:
                    raise ValidationError("Circulation policy threshold cannot be negative.", details={"field": key})
            return data
        raise ValidationError("Unsupported AI rule change type.", details={"change_type": change_type})

    # L5 tools still accept an object so the permission guard can reject them consistently.
    if tool_name in {"ai_execute_sql", "delete_audit_log", "modify_ai_permission", "read_api_key"}:
        return data

    return data
