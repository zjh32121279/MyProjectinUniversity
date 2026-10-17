from __future__ import annotations

from typing import Any

from bookflow_core.models import WorkTask


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


def _result_data(record: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(_as_dict(record.get("result")).get("data"))


def _result_total(data: dict[str, Any]) -> int | None:
    total = _as_int(data.get("total"))
    if total is not None:
        return total
    items = data.get("items")
    if isinstance(items, list):
        return len(items)
    return None


def _tool_observations(tool_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for record in tool_results:
        data = _result_data(record)
        observations.append(
            {
                "tool_name": _as_text(record.get("tool_name")),
                "status": _as_text(record.get("status")),
                "total": _result_total(data),
                "item_count": len(data.get("items")) if isinstance(data.get("items"), list) else None,
            }
        )
    return observations


def _has_evidence(observations: list[dict[str, Any]]) -> bool:
    for item in observations:
        total = item.get("total")
        if isinstance(total, int) and total > 0:
            return True
    return False


def _total_for(observations: list[dict[str, Any]], tool_name: str) -> int:
    total = 0
    for item in observations:
        if item.get("tool_name") != tool_name:
            continue
        value = item.get("total")
        if isinstance(value, int):
            total += value
    return total


def evaluate_execution_outcome(task: WorkTask, plan: dict[str, Any], tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize tool evidence and decide whether the task can be closed."""
    payload = _as_dict(plan.get("payload"))
    ctx = _context(payload)
    observations = _tool_observations(tool_results)
    failed_tools = [item for item in observations if item["status"] and item["status"] != "success"]
    sop_id = _as_text(plan.get("sop_id"))

    outcome = {
        "decision": "complete",
        "reason": "tool_steps_completed",
        "sop_id": sop_id,
        "observations": observations,
        "next_action": "record_trace_and_close",
    }
    if failed_tools:
        return {
            **outcome,
            "decision": "handoff",
            "reason": "tool_result_contains_non_success_status",
            "next_action": "admin_takeover",
            "failed_tools": failed_tools,
        }

    if _truthy(ctx.get("handoff_after_sop")):
        return {**outcome, "decision": "handoff", "reason": "explicit_handoff_after_sop", "next_action": "admin_takeover"}

    if _truthy(ctx.get("require_evidence")) and not _has_evidence(observations):
        return {**outcome, "decision": "handoff", "reason": "sop_missing_expected_evidence", "next_action": "admin_verify_missing_context"}

    if sop_id == "overdue_case_triage":
        overdue_days = _as_int(ctx.get("overdue_days")) or 0
        active_cases = _total_for(observations, "ai_get_overdue_cases")
        outcome["matched_overdue_cases"] = active_cases
        if overdue_days >= 7 and active_cases > 0:
            return {**outcome, "decision": "handoff", "reason": "long_overdue_case_needs_admin_followup", "next_action": "admin_takeover"}
        if active_cases == 0:
            outcome["next_action"] = "close_no_active_overdue_case_found"

    if sop_id == "reservation_event_triage":
        reservations = _total_for(observations, "ai_get_reservations")
        outcome["matched_reservations"] = reservations
        if reservations == 0:
            outcome["next_action"] = "close_no_matching_reservation_found"

    if sop_id == "risk_warning_triage":
        risks = _total_for(observations, "ai_get_risk_warnings")
        outcome["matched_risk_warnings"] = risks
        if risks == 0:
            outcome["next_action"] = "close_no_open_risk_warning_found"

    if sop_id == "reader_account_triage":
        outcome["matched_reader_records"] = _total_for(observations, "ai_get_readers")
        outcome["matched_reader_loans"] = _total_for(observations, "ai_get_loans")
        outcome["matched_reader_reservations"] = _total_for(observations, "ai_get_reservations")

    if sop_id == "collection_ops_triage":
        outcome["next_action"] = "record_collection_health_trace"

    if sop_id == "notification_ops_triage":
        outcome["next_action"] = "record_notification_health_trace"

    return outcome
