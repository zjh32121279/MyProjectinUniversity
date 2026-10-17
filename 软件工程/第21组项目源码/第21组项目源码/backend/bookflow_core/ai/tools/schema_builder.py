from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from bookflow_core.ai.tools.capability_defaults import infer_tool_defaults
from bookflow_core.models import AICapability


TOOL_INPUT_SCHEMAS = {
    "ai_get_hot_books": {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}}},
    "ai_get_cold_books": {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}}},
    "ai_search_books": {
        "type": "object",
        "properties": {
            "keyword": {"type": "string"},
            "availability": {"type": "string", "enum": ["available", "unavailable", "none"]},
            "sort": {"type": "string", "enum": ["availability", "newest", "title"]},
            "limit": {"type": "integer", "minimum": 1, "maximum": 20},
        },
    },
    "ai_get_active_risks": {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}}},
    "ai_get_risk_warnings": {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}}},
    "ai_get_overdue_summary": {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}}},
    "ai_get_loans": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["active", "borrowed", "renewable", "overdue", "returned"]},
            "reader_id": {"type": "integer", "minimum": 1},
            "book_id": {"type": "integer", "minimum": 1},
            "copy_id": {"type": "integer", "minimum": 1},
            "keyword": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            "offset": {"type": "integer", "minimum": 0},
        },
    },
    "ai_get_overdue_cases": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["active", "resolved"]},
            "min_overdue_days": {"type": "integer", "minimum": 0},
            "max_overdue_days": {"type": "integer", "minimum": 0},
            "reader_keyword": {"type": "string"},
            "book_keyword": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            "offset": {"type": "integer", "minimum": 0},
        },
    },
    "ai_get_reservations": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["active", "waiting", "ready", "ready_for_pickup", "fulfilled", "cancelled", "expired"]},
            "reader_id": {"type": "integer", "minimum": 1},
            "book_id": {"type": "integer", "minimum": 1},
            "copy_id": {"type": "integer", "minimum": 1},
            "keyword": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            "offset": {"type": "integer", "minimum": 0},
        },
    },
    "ai_get_notification_summary": {"type": "object", "properties": {}},
    "ai_get_task_summary": {"type": "object", "properties": {}},
    "ai_get_rule_summary": {"type": "object", "properties": {}},
    "ai_get_dashboard_explanation": {"type": "object", "properties": {}},
    "ai_get_operational_brief": {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}}},
    "ai_get_reader_detail": {"type": "object", "required": ["reader_code"], "properties": {"reader_code": {"type": "string"}}},
    "ai_get_reader_analytics": {"type": "object", "properties": {}},
    "ai_get_reader_borrow_summary": {"type": "object", "required": ["reader_id"], "properties": {"reader_id": {"type": "integer", "minimum": 1}}},
    "ai_get_readers": {
        "type": "object",
        "properties": {
            "reader_type_code": {"type": "string", "enum": ["child", "teen", "adult", "senior", "institution"]},
            "status": {"type": "string", "enum": ["active", "inactive", "suspended"]},
            "credit_status": {"type": "string", "enum": ["good", "limited", "suspended"]},
            "keyword": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            "offset": {"type": "integer", "minimum": 0},
        },
    },
    "ai_get_reader_activity": {"type": "object", "required": ["reader_code"], "properties": {"reader_code": {"type": "string"}}},
    "ai_reader_create_borrow_request": {
        "type": "object",
        "required": ["reader_code"],
        "properties": {
            "reader_code": {"type": "string"},
            "book_id": {"type": "integer", "minimum": 1},
            "book_code": {"type": "string"},
            "copy_id": {"type": "integer", "minimum": 1},
        },
    },
    "ai_reader_create_return_request": {
        "type": "object",
        "required": ["reader_code"],
        "properties": {
            "reader_code": {"type": "string"},
            "loan_id": {"type": "integer", "minimum": 1},
            "copy_code": {"type": "string"},
        },
    },
    "ai_reader_create_reservation": {
        "type": "object",
        "required": ["reader_code"],
        "properties": {
            "reader_code": {"type": "string"},
            "book_id": {"type": "integer", "minimum": 1},
            "book_code": {"type": "string"},
        },
    },
    "ai_reader_renew_borrow": {
        "type": "object",
        "required": ["reader_code", "loan_id"],
        "properties": {
            "reader_code": {"type": "string"},
            "loan_id": {"type": "integer", "minimum": 1},
        },
    },
    "ai_adjust_reader_credit": {
        "type": "object",
        "required": ["reader_code", "delta", "reason"],
        "properties": {
            "reader_code": {"type": "string"},
            "delta": {"type": "integer", "minimum": -100, "maximum": 100},
            "reason": {"type": "string"},
            "related_loan_id": {"type": "integer", "minimum": 1},
        },
    },
    "ai_suspend_reader": {"type": "object", "required": ["reader_code", "reason"], "properties": {"reader_code": {"type": "string"}, "reason": {"type": "string"}}},
    "ai_restore_reader": {"type": "object", "required": ["reader_code", "reason"], "properties": {"reader_code": {"type": "string"}, "reason": {"type": "string"}}},
    "ai_get_admin_security_summary": {"type": "object", "properties": {}},
    "ai_get_admin_events": {"type": "object", "properties": {"event_type": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 100}}},
    "ai_get_admins": {"type": "object", "properties": {"is_super_admin": {"type": "boolean"}, "status": {"type": "string", "enum": ["active", "disabled"]}, "limit": {"type": "integer", "minimum": 1, "maximum": 100}}},
    "ai_update_copy_status": {
        "type": "object",
        "required": ["copy_code", "new_status"],
        "properties": {
            "copy_code": {"type": "string"},
            "new_status": {"type": "string", "enum": ["available", "borrowed", "reserved", "maintenance"]},
            "reason": {"type": "string"},
        },
    },
    "ai_borrow_copy": {
        "type": "object",
        "required": ["reader_code", "copy_code"],
        "properties": {"reader_code": {"type": "string"}, "copy_code": {"type": "string"}},
    },
    "ai_return_copy": {
        "type": "object",
        "required": ["copy_code"],
        "properties": {"copy_code": {"type": "string"}},
    },
    "ai_renew_borrow": {
        "type": "object",
        "required": ["loan_id"],
        "properties": {"loan_id": {"type": "integer", "minimum": 1}},
    },
    "ai_cancel_reservation": {
        "type": "object",
        "required": ["reservation_id"],
        "properties": {"reservation_id": {"type": "integer", "minimum": 1}},
    },
    "ai_create_reservation": {
        "type": "object",
        "required": ["reader_code", "book_code"],
        "properties": {"reader_code": {"type": "string"}, "book_code": {"type": "string"}},
    },
    "ai_fulfill_reservation": {
        "type": "object",
        "required": ["reservation_id"],
        "properties": {"reservation_id": {"type": "integer", "minimum": 1}},
    },
    "ai_scan_overdues": {"type": "object", "properties": {}},
    "ai_request_copy_status_change": {
        "type": "object",
        "required": ["copy_code", "new_status"],
        "properties": {
            "copy_code": {"type": "string"},
            "new_status": {"type": "string", "enum": ["available", "borrowed", "reserved", "maintenance"]},
            "reason": {"type": "string"},
        },
    },
    "ai_request_batch_status_change": {
        "type": "object",
        "required": ["reason"],
        "properties": {"reason": {"type": "string"}, "copy_ids": {"type": "array", "items": {"type": "integer"}}},
    },
    "ai_request_high_risk_operation": {
        "type": "object",
        "required": ["reason"],
        "properties": {"reason": {"type": "string"}, "operation": {"type": "string"}},
    },
    "ai_create_work_task": {
        "type": "object",
        "required": ["title"],
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]},
            "auto_complete": {"type": "boolean"},
            "requires_human_confirmation": {"type": "boolean"},
            "fail_reason": {"type": "string"},
            "disable_auto_ai": {"type": "boolean"},
            "related_entities": {"type": "array", "items": {"type": "object"}},
        },
    },
    "ai_batch_create_tasks": {
        "type": "object",
        "required": ["tasks"],
        "properties": {
            "tasks": {
                "type": "array",
                "maxItems": 50,
                "items": {
                    "type": "object",
                    "required": ["title"],
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]},
                        "auto_complete": {"type": "boolean"},
                        "requires_human_confirmation": {"type": "boolean"},
                        "fail_reason": {"type": "string"},
                        "disable_auto_ai": {"type": "boolean"},
                        "related_entities": {"type": "array", "items": {"type": "object"}},
                    },
                },
            },
            "disable_auto_ai": {"type": "boolean"},
        },
    },
    "ai_get_tasks": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["pending", "ai_processing", "waiting_human", "admin_processing", "resolved", "cancelled"]},
            "source_type": {"type": "string"},
            "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]},
            "task_group": {"type": "string"},
            "keyword": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            "offset": {"type": "integer", "minimum": 0},
        },
    },
    "ai_assign_task_to_admin": {
        "type": "object",
        "required": ["task_code", "admin_code"],
        "properties": {"task_code": {"type": "string"}, "admin_code": {"type": "string"}, "reason": {"type": "string"}},
    },
    "ai_resolve_work_task": {
        "type": "object",
        "required": ["task_code"],
        "properties": {"task_code": {"type": "string"}, "resolution": {"type": "string"}},
    },
    "ai_create_notification": {
        "type": "object",
        "required": ["recipient_type", "title", "content"],
        "properties": {
            "recipient_type": {"type": "string", "enum": ["reader", "admin", "all", "all_readers", "all_admins"]},
            "recipient_id": {"type": "string"},
            "title": {"type": "string"},
            "content": {"type": "string"},
            "notification_type": {"type": "string"},
            "send_immediately": {"type": "boolean"},
            "related_entity_type": {"type": "string"},
            "related_entity_id": {"type": "string"},
            "source_task_code": {"type": "string"},
            "idempotency_key": {"type": "string"},
        },
    },
    "ai_send_notification": {"type": "object", "required": ["notification_id"], "properties": {"notification_id": {"type": "integer", "minimum": 1}}},
    "ai_create_task_notifications": {"type": "object", "properties": {}},
    "ai_batch_create_notifications": {
        "type": "object",
        "required": ["recipients", "title", "content"],
        "properties": {
            "recipients": {
                "type": "array",
                "maxItems": 100,
                "items": {
                    "type": "object",
                    "required": ["recipient_type"],
                    "properties": {
                        "recipient_type": {"type": "string", "enum": ["reader", "admin", "all", "all_readers", "all_admins"]},
                        "recipient_id": {"type": "string"},
                    },
                },
            },
            "title": {"type": "string"},
            "content": {"type": "string"},
            "notification_type": {"type": "string"},
            "send_immediately": {"type": "boolean"},
            "related_entity_type": {"type": "string"},
            "related_entity_id": {"type": "string"},
            "source_task_code": {"type": "string"},
            "idempotency_key": {"type": "string"},
        },
    },
    "ai_request_rule_change": {
        "type": "object",
        "required": ["change_type"],
        "properties": {
            "change_type": {"type": "string", "enum": ["borrow_rule", "system_setting", "circulation_policy"]},
            "reader_type_code": {"type": "string"},
            "reason": {"type": "string"},
        },
    },
}


def _schema_from_capability(row: AICapability) -> dict:
    if row.tool_name in TOOL_INPUT_SCHEMAS:
        return TOOL_INPUT_SCHEMAS[row.tool_name]
    try:
        data = json.loads(row.input_schema_json or "{}")
    except json.JSONDecodeError:
        return {"type": "object"}
    return data if isinstance(data, dict) else {"type": "object"}


def _autonomous_policy(row: AICapability) -> str:
    if not row.is_enabled:
        return "disabled"
    if row.permission_level == "L5":
        return "forbidden"
    if row.permission_level == "L4" or row.requires_super_authorization:
        return "authorization_required"
    if row.writes_db:
        if row.risk_level == "high":
            return "auto_write_enhanced_audit"
        return "auto_write_with_task_risk_guard"
    return "auto_read"


def _sync_capability_row(row: AICapability) -> AICapability:
    defaults = infer_tool_defaults(row.tool_name)
    for field in ("permission_level", "risk_level", "is_write", "writes_db", "requires_super_authorization", "description"):
        value = defaults[field]
        if getattr(row, field) != value:
            setattr(row, field, value)
    return row


def _ensure_registered_capabilities(db: Session) -> None:
    from bookflow_core.ai.tools.registry import registered_tool_names

    existing = set(db.scalars(select(AICapability.tool_name)).all())
    missing = [tool_name for tool_name in registered_tool_names() if tool_name not in existing]
    if not missing:
        return
    for tool_name in missing:
        db.add(AICapability(**infer_tool_defaults(tool_name)))
    db.flush()


def tool_schemas_for_llm(db: Session) -> list[dict]:
    _ensure_registered_capabilities(db)
    rows = db.scalars(
        select(AICapability)
        .where(AICapability.is_enabled == True, AICapability.is_enabled == True, AICapability.permission_level != "L5")
        .order_by(AICapability.permission_level, AICapability.tool_name)
    ).all()
    rows = [_sync_capability_row(row) for row in rows]
    return [
        {
            "tool_name": row.tool_name,
            "display_name": row.display_name,
            "description": row.description,
            "permission_level": row.permission_level,
            "risk_level": row.risk_level,
            "is_write": row.is_write,
            "writes_db": row.writes_db,
            "requires_super_authorization": row.requires_super_authorization,
            "autonomous_policy": _autonomous_policy(row),
            "input_schema": _schema_from_capability(row),
            "output_schema": json.loads(row.output_schema_json or "{}"),
        }
        for row in rows
    ]


def available_tool_names(db: Session) -> set[str]:
    return {item["tool_name"] for item in tool_schemas_for_llm(db)}


