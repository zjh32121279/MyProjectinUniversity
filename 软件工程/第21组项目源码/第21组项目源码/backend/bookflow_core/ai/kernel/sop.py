from __future__ import annotations

from typing import Any

from bookflow_core.models import WorkTask


SOP_VERSION = "2026-06-03.1"
_MAX_STEPS = 5


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_text(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _context(payload: dict[str, Any]) -> dict[str, Any]:
    nested = _as_dict(payload.get("payload"))
    merged = dict(nested)
    for key, value in payload.items():
        if key != "payload" and key not in merged:
            merged[key] = value
    return merged


def _step(tool_name: str, arguments: dict[str, Any] | None = None, reason: str = "") -> dict[str, Any]:
    return {
        "tool_name": tool_name,
        "arguments": arguments or {},
        "reason": reason or f"sop_step:{tool_name}",
        "stop_on_failure": True,
    }


def _dedupe_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for item in steps:
        key = (str(item.get("tool_name") or ""), repr(sorted(_as_dict(item.get("arguments")).items())))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= _MAX_STEPS:
            break
    return result


def _plan(sop_id: str, reason: str, steps: list[dict[str, Any]], payload: dict[str, Any], *, confidence: float = 0.82) -> dict[str, Any] | None:
    clean_steps = _dedupe_steps(steps)
    if not clean_steps:
        return None
    return {
        "action": "execute_plan",
        "steps": clean_steps,
        "reason": reason,
        "confidence": confidence,
        "tool_name": "",
        "arguments": {},
        "payload": payload,
        "sop_id": sop_id,
        "sop_version": SOP_VERSION,
    }


def _task_text(task: WorkTask, payload: dict[str, Any]) -> str:
    ctx = _context(payload)
    parts = [
        getattr(task, "title", ""),
        getattr(task, "description", ""),
        getattr(task, "source_type", ""),
        getattr(task, "task_group", ""),
        _as_text(payload.get("kernel_intent")),
        _as_text(ctx.get("action")),
        _as_text(ctx.get("warning_type")),
    ]
    return " ".join(part for part in parts if part).lower()


def _reader_steps(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    reader_code = _as_text(ctx.get("reader_code"))
    if not reader_code:
        return []
    return [
        _step("ai_get_reader_activity", {"reader_code": reader_code}, "inspect reader activity and current constraints"),
    ]


def _optional_handoff_steps(task: WorkTask, ctx: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    admin_code = _as_text(ctx.get("assign_admin_code"))
    if admin_code:
        steps.append(
            _step(
                "ai_assign_task_to_admin",
                {"task_code": task.task_code, "admin_code": admin_code, "reason": "sop_explicit_admin_assignment"},
                "assign task to the explicitly requested admin",
            )
        )
    if _truthy(ctx.get("notify_admins")) or _truthy(ctx.get("notify_task_assignees")):
        steps.append(_step("ai_create_task_notifications", {}, "notify admins about current actionable task pool"))
    return steps


def _overdue_plan(task: WorkTask, payload: dict[str, Any]) -> dict[str, Any] | None:
    ctx = _context(payload)
    reader_code = _as_text(ctx.get("reader_code"))
    copy_code = _as_text(ctx.get("copy_code"))
    overdue_days = _as_int(ctx.get("overdue_days"))
    loan_args: dict[str, Any] = {"status": "overdue", "limit": 10}
    if copy_code:
        loan_args["keyword"] = copy_code
    elif reader_code:
        loan_args["keyword"] = reader_code

    overdue_args: dict[str, Any] = {"status": "active", "limit": 10}
    if overdue_days is not None:
        overdue_args["min_overdue_days"] = max(0, min(overdue_days, 3650))
    if reader_code:
        overdue_args["reader_keyword"] = reader_code

    steps = [
        _step("ai_get_loans", loan_args, "verify overdue loan state"),
        _step("ai_get_overdue_cases", overdue_args, "inspect matching overdue case records"),
        *_reader_steps(ctx),
        *_optional_handoff_steps(task, ctx),
    ]
    return _plan("overdue_case_triage", "sop_overdue_case_triage", steps, payload, confidence=0.9)


def _reservation_plan(task: WorkTask, payload: dict[str, Any]) -> dict[str, Any] | None:
    ctx = _context(payload)
    keyword = _as_text(ctx.get("reader_code")) or _as_text(ctx.get("book_code")) or _as_text(ctx.get("copy_code"))
    status = _as_text(ctx.get("status"))
    args: dict[str, Any] = {"limit": 10}
    if keyword:
        args["keyword"] = keyword
    if status in {"active", "waiting", "ready", "ready_for_pickup", "fulfilled", "cancelled", "expired"}:
        args["status"] = status
    copy_id = _as_int(ctx.get("copy_id"))
    book_id = _as_int(ctx.get("book_id"))
    if copy_id:
        args["copy_id"] = copy_id
    if book_id:
        args["book_id"] = book_id

    steps = [
        _step("ai_get_reservations", args, "verify reservation state and related queue"),
        *_reader_steps(ctx),
        *_optional_handoff_steps(task, ctx),
    ]
    return _plan("reservation_event_triage", "sop_reservation_event_triage", steps, payload, confidence=0.86)


def _risk_plan(task: WorkTask, payload: dict[str, Any]) -> dict[str, Any] | None:
    ctx = _context(payload)
    warning_type = _as_text(ctx.get("warning_type"))
    steps = [
        _step("ai_get_risk_warnings", {"limit": 20}, "inspect open risk warning context"),
    ]
    if warning_type == "active_overdue":
        steps.append(_step("ai_get_overdue_cases", {"status": "active", "limit": 20}, "inspect active overdue cases behind the risk"))
    elif warning_type == "low_credit_reader":
        steps.append(_step("ai_get_readers", {"credit_status": "limited", "limit": 20}, "inspect readers with constrained credit"))
    elif warning_type in {"unavailable_copy", "hot_book_low_inventory"}:
        steps.append(_step("ai_get_collection_health", {}, "inspect collection availability health"))
    else:
        steps.append(_step("ai_get_operational_brief", {"limit": 20}, "collect operational context for risk triage"))
    steps.extend(_optional_handoff_steps(task, ctx))
    return _plan("risk_warning_triage", "sop_risk_warning_triage", steps, payload, confidence=0.84)


def _circulation_event_plan(task: WorkTask, payload: dict[str, Any]) -> dict[str, Any] | None:
    ctx = _context(payload)
    action = _as_text(ctx.get("action"))
    reader_code = _as_text(ctx.get("reader_code"))
    copy_code = _as_text(ctx.get("copy_code"))
    loan_id = _as_int(ctx.get("loan_id"))
    keyword = copy_code or reader_code
    loan_args: dict[str, Any] = {"limit": 10}
    if keyword:
        loan_args["keyword"] = keyword
    if action in {"borrow_copy", "renew_borrow"}:
        loan_args["status"] = "active"
    elif action == "return_copy":
        loan_args["status"] = "returned"

    steps: list[dict[str, Any]] = []
    if loan_id or keyword:
        steps.append(_step("ai_get_loans", loan_args, "verify circulation event result"))
    if action == "return_copy" and _as_int(ctx.get("overdue_days")):
        steps.append(_step("ai_get_overdue_cases", {"status": "active", "limit": 10}, "check unresolved overdue residue after return"))
    steps.extend(_reader_steps(ctx))
    steps.extend(_optional_handoff_steps(task, ctx))
    return _plan("circulation_event_audit", "sop_circulation_event_audit", steps, payload, confidence=0.78)


def _task_pool_plan(task: WorkTask, payload: dict[str, Any]) -> dict[str, Any] | None:
    ctx = _context(payload)
    args: dict[str, Any] = {"status": _as_text(ctx.get("status") or "pending"), "limit": _as_int(ctx.get("limit")) or 20}
    group = _as_text(ctx.get("task_group"))
    if group:
        args["task_group"] = group
    priority = _as_text(ctx.get("priority"))
    if priority in {"low", "normal", "high", "urgent"}:
        args["priority"] = priority
    steps = [
        _step("ai_get_tasks", args, "inspect task pool backlog"),
        *_optional_handoff_steps(task, ctx),
    ]
    return _plan("task_pool_triage", "sop_task_pool_triage", steps, payload, confidence=0.8)


def _reader_account_plan(task: WorkTask, payload: dict[str, Any]) -> dict[str, Any] | None:
    ctx = _context(payload)
    reader_code = _as_text(ctx.get("reader_code"))
    keyword = reader_code or _as_text(ctx.get("reader_keyword")) or _as_text(ctx.get("keyword"))
    steps: list[dict[str, Any]] = []
    if reader_code:
        steps.extend(_reader_steps(ctx))
        steps.append(_step("ai_get_loans", {"keyword": reader_code, "limit": 20}, "inspect reader circulation state"))
        steps.append(_step("ai_get_reservations", {"keyword": reader_code, "limit": 20}, "inspect reader reservation state"))
    else:
        args = {"limit": 20}
        if keyword:
            args["keyword"] = keyword
        steps.append(_step("ai_get_readers", args, "inspect matching reader accounts"))
    steps.extend(_optional_handoff_steps(task, ctx))
    return _plan("reader_account_triage", "sop_reader_account_triage", steps, payload, confidence=0.82)


def _collection_plan(task: WorkTask, payload: dict[str, Any]) -> dict[str, Any] | None:
    ctx = _context(payload)
    steps = [
        _step("ai_get_collection_health", {}, "inspect collection and copy health"),
        _step("ai_get_hot_books", {"limit": 20}, "inspect high-demand books"),
        _step("ai_get_cold_books", {"limit": 20}, "inspect low-circulation books"),
        *_optional_handoff_steps(task, ctx),
    ]
    return _plan("collection_ops_triage", "sop_collection_ops_triage", steps, payload, confidence=0.8)


def _notification_plan(task: WorkTask, payload: dict[str, Any]) -> dict[str, Any] | None:
    ctx = _context(payload)
    steps = [
        _step("ai_get_notification_summary", {}, "inspect notification backlog and delivery state"),
        *_optional_handoff_steps(task, ctx),
    ]
    return _plan("notification_ops_triage", "sop_notification_ops_triage", steps, payload, confidence=0.78)


def build_sop_plan(task: WorkTask, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Return a deterministic AI Kernel SOP plan for common library operations."""
    intent = _as_text(payload.get("kernel_intent"))
    ctx = _context(payload)
    action = _as_text(ctx.get("action"))
    text = _task_text(task, payload)

    if intent == "overdue_case" or getattr(task, "source_type", "") == "overdue" or "overdue" in text:
        return _overdue_plan(task, payload)

    if intent == "risk_warning" or getattr(task, "task_group", "") == "risk" or getattr(task, "source_type", "") == "risk":
        return _risk_plan(task, payload)

    if (
        getattr(task, "task_group", "") == "reservation"
        or getattr(task, "source_type", "") == "reservation"
        or "reservation" in text
        or action in {"create_reservation", "cancel_reservation", "fulfill_reservation", "create_reader_reservation", "cancel_reader_reservation"}
    ):
        return _reservation_plan(task, payload)

    if action in {"borrow_copy", "return_copy", "renew_borrow"}:
        return _circulation_event_plan(task, payload)

    if getattr(task, "task_group", "") in {"catalog", "shelving"} or getattr(task, "source_type", "") in {"catalog", "shelving"}:
        return _collection_plan(task, payload)

    if getattr(task, "task_group", "") == "notification":
        return _notification_plan(task, payload)

    if _as_text(ctx.get("reader_code")) and intent != "reader_ai_chat":
        return _reader_account_plan(task, payload)

    if intent in {"task_pool", "task_backlog"} or action in {"task_pool", "task_backlog"}:
        return _task_pool_plan(task, payload)

    return None
