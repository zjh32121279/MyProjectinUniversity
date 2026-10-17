from __future__ import annotations

from typing import Any

from bookflow_core.models import WorkTask


_MAX_FOLLOWUP_STEPS = 3


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_text(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


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


def _step(tool_name: str, arguments: dict[str, Any], reason: str, *, idempotency_key: str = "", target_type: str = "", target_id: str = "") -> dict[str, Any]:
    return {
        "tool_name": tool_name,
        "arguments": arguments,
        "reason": reason,
        "stop_on_failure": True,
        "followup": True,
        "idempotency_key": idempotency_key,
        "target_type": target_type,
        "target_id": target_id,
    }


def _already_ran(tool_results: list[dict[str, Any]], tool_name: str, arguments: dict[str, Any]) -> bool:
    for record in tool_results:
        if _as_text(record.get("tool_name")) != tool_name:
            continue
        if _as_dict(record.get("arguments")) == arguments:
            return True
    return False


def _append_if_new(steps: list[dict[str, Any]], tool_results: list[dict[str, Any]], step: dict[str, Any]) -> None:
    tool_name = _as_text(step.get("tool_name"))
    arguments = _as_dict(step.get("arguments"))
    if not tool_name or _already_ran(tool_results, tool_name, arguments):
        return
    if any(_as_text(item.get("tool_name")) == tool_name and _as_dict(item.get("arguments")) == arguments for item in steps):
        return
    if len(steps) < _MAX_FOLLOWUP_STEPS:
        steps.append(step)


def build_followup_steps(task: WorkTask, plan: dict[str, Any], outcome: dict[str, Any], tool_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build bounded post-outcome actions for common autonomous closures."""
    payload = _as_dict(plan.get("payload"))
    ctx = _context(payload)
    sop_id = _as_text(outcome.get("sop_id") or plan.get("sop_id"))
    steps: list[dict[str, Any]] = []

    if _as_text(outcome.get("decision")) == "handoff":
        admin_code = _as_text(ctx.get("assign_admin_code"))
        if admin_code:
            _append_if_new(
                steps,
                tool_results,
                _step(
                    "ai_assign_task_to_admin",
                    {"task_code": task.task_code, "admin_code": admin_code, "reason": _as_text(outcome.get("reason")) or "ai_followup_handoff"},
                    "assign handoff task to explicit admin",
                    idempotency_key=f"task_assign:{task.task_code}:{admin_code}",
                    target_type="work_task",
                    target_id=task.task_code,
                ),
            )
        if _truthy(ctx.get("notify_admins")):
            _append_if_new(
                steps,
                tool_results,
                _step(
                    "ai_create_task_notifications",
                    {},
                    "notify admins about handoff task",
                    idempotency_key=f"task_admin_notify:{task.task_code}:{_as_text(outcome.get('reason'))}",
                    target_type="work_task",
                    target_id=task.task_code,
                ),
            )
        return steps

    reader_code = _as_text(ctx.get("reader_code"))
    if sop_id == "reservation_event_triage" and reader_code:
        status = _as_text(ctx.get("status"))
        if status in {"ready", "ready_for_pickup"} and int(outcome.get("matched_reservations") or 0) > 0 and not _truthy(ctx.get("suppress_reader_notification")):
            reservation_code = _as_text(ctx.get("reservation_code"))
            book_title = _as_text(ctx.get("book_title"))
            reserved_until = _as_text(ctx.get("reserved_until"))
            title_text = f"《{book_title}》" if book_title else "图书"
            content = f"你预约的{title_text}已到馆，请在保留期内到馆办理借阅。取书凭证号：{reservation_code}。"
            if reserved_until:
                content += f"保留截止日期：{reserved_until}。"
            _append_if_new(
                steps,
                tool_results,
                _step(
                    "ai_create_notification",
                    {
                        "recipient_type": "reader",
                        "recipient_id": reader_code,
                        "title": "预约图书已到馆",
                        "content": content,
                        "notification_type": "reservation",
                    },
                    "notify reader that reservation is ready",
                    idempotency_key=f"reservation_ready_notice:{reader_code}:{_as_text(ctx.get('book_code'))}:{status}",
                    target_type="reader",
                    target_id=reader_code,
                ),
            )

    if sop_id == "overdue_case_triage" and reader_code:
        if _truthy(ctx.get("auto_notify_reader")) and int(outcome.get("matched_overdue_cases") or 0) > 0:
            _append_if_new(
                steps,
                tool_results,
                _step(
                    "ai_create_notification",
                    {
                        "recipient_type": "reader",
                        "recipient_id": reader_code,
                        "title": "图书逾期提醒",
                        "content": "你有图书已经逾期，请尽快归还或联系馆员处理。",
                        "notification_type": "overdue",
                    },
                    "notify reader about active overdue case",
                    idempotency_key=f"overdue_notice:{reader_code}:{_as_text(ctx.get('loan_id')) or _as_text(ctx.get('copy_code')) or 'active'}",
                    target_type="reader",
                    target_id=reader_code,
                ),
            )

    return steps
