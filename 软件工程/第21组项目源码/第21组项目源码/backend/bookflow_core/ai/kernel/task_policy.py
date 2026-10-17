from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any

from bookflow_core.core.time import now
from bookflow_core.models import WorkTask


VALID_PRIORITIES = ("low", "normal", "high", "urgent")
PRIORITY_RANK = {"low": 0, "normal": 1, "high": 2, "urgent": 3}
PRIORITY_QUEUE_BASE = {"low": 0, "normal": 100, "high": 200, "urgent": 300}
PRIORITY_THRESHOLDS = ((70, "urgent"), (45, "high"), (20, "normal"), (0, "low"))
RISK_THRESHOLDS = ((71, "critical"), (46, "high"), (21, "medium"), (0, "low"))

REQUESTED_PRIORITY_POINTS = {"urgent": 20, "high": 10, "normal": 0, "low": 0}

READER_SERVICE_TYPES = {"borrow", "reservation", "renew", "return"}
READER_SERVICE_GROUPS = {"borrow", "reservation"}
RESOURCE_GROUPS = {"borrow", "reservation", "catalog", "shelving"}
RISK_SOURCE_TYPES = {"risk", "security", "ai_review"}

READ_ONLY_WORDS = ("get_", "search", "summary", "analytics", "brief", "query", "list", "read")
NOTIFICATION_WORDS = ("notification", "notice", "reminder", "send")
CIRCULATION_WORDS = ("borrow", "return", "renew", "reservation", "fulfill")
HIGH_RIGHTS_WORDS = ("credit", "suspend", "restore", "password", "qualification", "ban")
CRITICAL_WORDS = (
    "admin",
    "permission",
    "role",
    "settings",
    "setting",
    "rule",
    "policy",
    "sql",
    "delete",
    "export",
    "rollback",
    "ai_rule",
)


def _json_obj(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {"raw": raw}
    return data if isinstance(data, dict) else {"value": data}


def _context(row: WorkTask) -> dict[str, Any]:
    source_payload = _json_obj(getattr(row, "source_payload_json", None))
    execution_context = _json_obj(getattr(row, "execution_context_json", None))
    nested_payload = source_payload.get("payload") if isinstance(source_payload.get("payload"), dict) else {}
    return {
        **nested_payload,
        **source_payload,
        "execution_context": execution_context,
    }


def _lower(value: Any) -> str:
    return str(value or "").strip().lower()


def _action(row: WorkTask, ctx: dict[str, Any]) -> str:
    return _lower(
        ctx.get("action")
        or ctx.get("tool_name")
        or ctx.get("requested_tool")
        or ctx.get("kernel_intent")
        or getattr(row, "task_type", "")
    )


def _request_type(ctx: dict[str, Any], action: str) -> str:
    request_type = _lower(ctx.get("request_type"))
    if request_type:
        return request_type
    for item in READER_SERVICE_TYPES:
        if item in action:
            return item
    return ""


def _severity(ctx: dict[str, Any]) -> str:
    return _lower(ctx.get("severity") or ctx.get("risk_severity"))


def _requested_priority(row: WorkTask, ctx: dict[str, Any]) -> str:
    value = _lower(ctx.get("_requested_priority") or ctx.get("requested_priority") or getattr(row, "priority", "normal"))
    return value if value in VALID_PRIORITIES else "normal"


def _aware(value: datetime) -> datetime:
    from bookflow_core.core.time import CST
    return value if value.tzinfo is not None else value.replace(tzinfo=CST)


def _age_minutes(row: WorkTask) -> int:
    current = now()
    created_at = _aware(row.created_at) if getattr(row, "created_at", None) else current
    return max(0, int((current - created_at).total_seconds() // 60))


def _sla_remaining(row: WorkTask):
    if not getattr(row, "sla_due_at", None):
        return None
    return _aware(row.sla_due_at) - now()


def _number(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _object_count(ctx: dict[str, Any]) -> int:
    keys = (
        "affected_count",
        "item_count",
        "count",
        "total",
        "batch_size",
        "reader_count",
        "copy_count",
        "notification_count",
    )
    count = max((_number(ctx.get(key), 0) for key in keys), default=0)
    for key in ("items", "tasks", "recipients", "tool_calls", "steps"):
        value = ctx.get(key)
        if isinstance(value, list):
            count = max(count, len(value))
    return count


def _has_single_target(row: WorkTask, ctx: dict[str, Any]) -> bool:
    if getattr(row, "related_entity_id", None):
        return True
    for key in ("reader_code", "book_id", "book_code", "copy_id", "copy_code", "loan_id", "reservation_id"):
        if ctx.get(key):
            return True
    return False


def _overdue_days(ctx: dict[str, Any]) -> int:
    return max(_number(ctx.get("overdue_days"), 0), _number(ctx.get("days_overdue"), 0))


def _is_reader_service(row: WorkTask, ctx: dict[str, Any], action: str) -> bool:
    request_type = _request_type(ctx, action)
    return (
        request_type in READER_SERVICE_TYPES
        or getattr(row, "task_group", "") in READER_SERVICE_GROUPS
        or getattr(row, "source_type", "") == "reader_event"
        or getattr(row, "related_entity_type", "") == "circulation_service_request"
    )


def _is_write_action(row: WorkTask, action: str) -> bool:
    if any(word in action for word in ("create", "update", "borrow", "return", "renew", "cancel", "fulfill", "send", "adjust", "suspend", "restore", "resolve", "assign", "batch")):
        return True
    if getattr(row, "source_type", "") in {"reader_event", "ai_admin", "risk", "security", "ai_review"}:
        return True
    return False


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _priority_from_score(score: int) -> str:
    for minimum, level in PRIORITY_THRESHOLDS:
        if score >= minimum:
            return level
    return "low"


def _risk_from_score(score: int) -> str:
    for minimum, level in RISK_THRESHOLDS:
        if score >= minimum:
            return level
    return "low"


def _max_priority(*levels: str) -> str:
    current = "low"
    for level in levels:
        normalized = level if level in PRIORITY_RANK else "low"
        if PRIORITY_RANK[normalized] > PRIORITY_RANK[current]:
            current = normalized
    return current


def _max_risk(*levels: str) -> str:
    rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    current = "low"
    for level in levels:
        normalized = level if level in rank else "low"
        if rank[normalized] > rank[current]:
            current = normalized
    return current


def _priority_score(row: WorkTask, ctx: dict[str, Any]) -> tuple[int, list[str], str]:
    action = _action(row, ctx)
    score = 0
    reasons: list[str] = []

    remaining = _sla_remaining(row)
    if remaining is not None:
        if remaining <= timedelta(minutes=0):
            score += 40
            reasons.append("sla_overdue=40")
        elif remaining <= timedelta(hours=1):
            score += 30
            reasons.append("sla<=1h=30")
        elif remaining <= timedelta(hours=4):
            score += 20
            reasons.append("sla<=4h=20")
        elif remaining <= timedelta(hours=24):
            score += 10
            reasons.append("sla<=24h=10")

    request_type = _request_type(ctx, action)
    request_status = _lower(ctx.get("status"))
    if _is_reader_service(row, ctx, action):
        if request_status in {"pending", "ready", "waiting_human", "blocked"}:
            score += 25
            reasons.append("reader_service_blocked=25")
        elif request_type in READER_SERVICE_TYPES or getattr(row, "task_group", "") in READER_SERVICE_GROUPS:
            score += 15
            reasons.append("reader_service=15")
        else:
            score += 5
            reasons.append("reader_related=5")

    count = _object_count(ctx)
    if count > 20:
        score += 20
        reasons.append("scope>20=20")
    elif count >= 2:
        score += 10
        reasons.append("scope=2-20=10")
    elif _has_single_target(row, ctx):
        score += 5
        reasons.append("scope=single=5")

    severity = _severity(ctx)
    source_type = getattr(row, "source_type", "")
    group = getattr(row, "task_group", "")
    if source_type == "security" or severity in {"critical", "high"} or bool(getattr(row, "ai_error", "")):
        score += 30
        reasons.append("business_security_or_failure=30")
    elif source_type in RISK_SOURCE_TYPES or getattr(row, "risk_warning_code", "") or severity == "medium" or group in {"risk", "exception", "ai_review"} or _overdue_days(ctx) > 0:
        score += 20
        reasons.append("business_exception=20")
    elif group in RESOURCE_GROUPS or request_type in READER_SERVICE_TYPES:
        score += 10
        reasons.append("business_normal_ops=10")

    available = _number(ctx.get("available_copies"), -1)
    waiting = max(_number(ctx.get("waiting_count"), 0), _number(ctx.get("reservation_waiting_count"), 0))
    circulation_type = _lower(ctx.get("circulation_type"))
    if waiting > 0 and available == 0:
        score += 10
        reasons.append("resource_waiting_no_available=10")
    elif circulation_type == "hot" and available <= 1 and available >= 0:
        score += 5
        reasons.append("resource_hot_low_inventory=5")

    requested = _requested_priority(row, ctx)
    requested_points = REQUESTED_PRIORITY_POINTS.get(requested, 0)
    if requested_points:
        score += requested_points
        reasons.append(f"requested_priority_{requested}={requested_points}")

    hard = "low"
    overdue_days = _overdue_days(ctx)
    age_minutes = _age_minutes(row)
    if remaining is not None and remaining <= timedelta(minutes=0):
        hard = _max_priority(hard, "urgent")
        reasons.append("hard=sla_overdue")
    if overdue_days >= 7:
        hard = _max_priority(hard, "urgent")
        reasons.append("hard=overdue>=7d")
    elif overdue_days > 0:
        hard = _max_priority(hard, "high")
        reasons.append("hard=overdue")
    if source_type == "security" or severity in {"critical", "high"}:
        hard = _max_priority(hard, "urgent")
        reasons.append("hard=security_or_high_severity")
    elif severity == "medium":
        hard = _max_priority(hard, "high")
        reasons.append("hard=medium_severity")
    if getattr(row, "ai_error", "") and _is_reader_service(row, ctx, action):
        hard = _max_priority(hard, "urgent")
        reasons.append("hard=ai_failure_reader_rights")
    elif getattr(row, "ai_error", ""):
        hard = _max_priority(hard, "high")
        reasons.append("hard=ai_failure")
    if remaining is not None and remaining <= timedelta(hours=4):
        hard = _max_priority(hard, "high")
        reasons.append("hard=sla<=4h")
    if _is_reader_service(row, ctx, action) and request_status in {"pending", "ready", "waiting_human"} and age_minutes >= 30:
        hard = _max_priority(hard, "high")
        reasons.append("hard=reader_request_wait>=30m")

    return min(score, 100), reasons, hard


def _risk_score(row: WorkTask, ctx: dict[str, Any]) -> tuple[int, list[str], str]:
    action = _action(row, ctx)
    score = 0
    reasons: list[str] = []
    is_write = _is_write_action(row, action)
    count = _object_count(ctx)
    request_type = _request_type(ctx, action)
    source_type = getattr(row, "source_type", "")
    action_text = action

    if _contains_any(action_text, CRITICAL_WORDS):
        score += 25
        reasons.append("data_change_system=25")
    elif _contains_any(action_text, HIGH_RIGHTS_WORDS):
        score += 20
        reasons.append("data_change_reader_governance=20")
    elif _contains_any(action_text, CIRCULATION_WORDS) or getattr(row, "task_group", "") in READER_SERVICE_GROUPS:
        score += 15 if "request" not in action_text else 10
        reasons.append("data_change_circulation=15" if "request" not in action_text else "data_change_service_request=10")
    elif _contains_any(action_text, NOTIFICATION_WORDS):
        score += 10
        reasons.append("data_change_notification=10")
    elif is_write:
        score += 5
        reasons.append("data_change_internal=5")

    if _contains_any(action_text, HIGH_RIGHTS_WORDS):
        score += 20
        reasons.append("rights_account=20")
    elif request_type in READER_SERVICE_TYPES or _contains_any(action_text, CIRCULATION_WORDS):
        score += 10
        reasons.append("rights_circulation=10")
    elif _contains_any(action_text, NOTIFICATION_WORDS):
        score += 5
        reasons.append("rights_notification=5")

    if count > 20:
        score += 20
        reasons.append("scope>20=20")
    elif count >= 2:
        score += 10
        reasons.append("scope=2-20=10")
    elif _has_single_target(row, ctx):
        score += 5
        reasons.append("scope=single=5")

    if _contains_any(action_text, CRITICAL_WORDS):
        score += 15
        reasons.append("reversibility_hard=15")
    elif _contains_any(action_text, HIGH_RIGHTS_WORDS) or "return" in action_text or "borrow" in action_text or "fulfill" in action_text:
        score += 8
        reasons.append("reversibility_side_effects=8")
    elif "request" in action_text or "reservation" in action_text:
        score += 8
        reasons.append("reversibility_request=8")

    confidence = getattr(row, "ai_confidence", None)
    if confidence is not None:
        if float(confidence) < 0.65:
            score += 15
            reasons.append("evidence_confidence<0.65=15")
        elif float(confidence) < 0.85:
            score += 8
            reasons.append("evidence_confidence<0.85=8")
    if bool(getattr(row, "requires_human_confirmation", False)):
        score += 8
        reasons.append("evidence_human_confirmation=8")
    if source_type in RISK_SOURCE_TYPES or getattr(row, "risk_warning_code", ""):
        score += 8
        reasons.append("evidence_risk_source=8")

    if _contains_any(action_text, HIGH_RIGHTS_WORDS) or source_type == "security":
        score += 10
        reasons.append("external_account_or_security=10")
    elif _contains_any(action_text, NOTIFICATION_WORDS):
        score += 5
        reasons.append("external_notification=5")

    hard = "low"
    if _contains_any(action_text, CRITICAL_WORDS) or (count > 20 and is_write):
        hard = _max_risk(hard, "critical")
        reasons.append("hard=critical_governance_or_batch")
    if _contains_any(action_text, HIGH_RIGHTS_WORDS) or _overdue_days(ctx) > 0 or source_type in RISK_SOURCE_TYPES:
        hard = _max_risk(hard, "high")
        reasons.append("hard=high_rights_or_risk")
    if request_type in READER_SERVICE_TYPES or _contains_any(action_text, NOTIFICATION_WORDS):
        hard = _max_risk(hard, "medium")
        reasons.append("hard=normal_business_write")
    if _contains_any(action_text, READ_ONLY_WORDS) and not is_write:
        hard = _max_risk(hard, "low")
        reasons.append("hard=read_only")

    return min(score, 100), reasons, hard


def infer_queue_name(row: WorkTask, risk_level: str) -> str:
    if bool(row.requires_human_confirmation) or risk_level in {"critical", "high"}:
        return "human_review"
    if row.task_group in {"borrow", "reservation", "notification"} or row.source_type == "reader_event":
        return "reader_ops"
    if row.task_group in {"catalog", "shelving"}:
        return "collection_ops"
    return "default"


def compute_priority(row: WorkTask) -> tuple[int, str, str]:
    ctx = _context(row)
    base_score, priority_reasons, hard_priority = _priority_score(row, ctx)
    calculated_priority = _max_priority(_priority_from_score(base_score), hard_priority)
    risk_score, risk_reasons, hard_risk = _risk_score(row, ctx)
    risk_level = _max_risk(_risk_from_score(risk_score), hard_risk)

    age_hours = _age_minutes(row) // 60
    age_score = min(120, age_hours * 4)
    queue_score = PRIORITY_QUEUE_BASE[calculated_priority] + base_score + age_score
    reason = (
        f"priority={calculated_priority};base_priority_score={base_score};"
        f"risk={risk_level};risk_score={risk_score};"
        f"queue_score={queue_score};"
        f"priority_factors={','.join(priority_reasons) or 'none'};"
        f"risk_factors={','.join(risk_reasons) or 'none'}"
    )
    return queue_score, risk_level, reason


def apply_task_policy(row: WorkTask, *, preferred_queue: str | None = None) -> WorkTask:
    ctx = _context(row)
    base_score, _, hard_priority = _priority_score(row, ctx)
    row.priority = _max_priority(_priority_from_score(base_score), hard_priority)
    score, risk_level, reason = compute_priority(row)
    row.priority_score = score
    row.risk_level = risk_level
    row.queue_name = preferred_queue or infer_queue_name(row, risk_level)
    row.urgency_reason = reason
    if row.max_attempts is None:
        row.max_attempts = 3
    if row.attempt_count is None:
        row.attempt_count = 0
    return row
