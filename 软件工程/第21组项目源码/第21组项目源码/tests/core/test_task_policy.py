from __future__ import annotations

import json

from bookflow_core.ai.kernel.task_policy import apply_task_policy
from bookflow_core.core.time import now
from bookflow_core.models import WorkTask


def _task(**kwargs) -> WorkTask:
    defaults = {
        "title": "pytest task",
        "description": "",
        "priority": "normal",
        "source_type": "system",
        "task_group": "other",
        "related_entity_type": "",
        "related_entity_id": "",
        "risk_warning_code": "",
        "requires_human_confirmation": False,
        "created_at": now(),
    }
    defaults.update(kwargs)
    return WorkTask(**defaults)


def _payload(**kwargs) -> str:
    return json.dumps(kwargs)


def test_policy_scores_normal_reader_reservation_as_normal_medium() -> None:
    row = _task(
        title="reader reservation request",
        source_type="reader_event",
        task_group="reservation",
        related_entity_type="circulation_service_request",
        related_entity_id="1",
        source_payload_json=_payload(
            _requested_priority="normal",
            action="circulation_request_reservation",
            request_type="reservation",
            status="completed",
            reader_code="R-PYTEST",
            book_id=1,
        ),
    )

    apply_task_policy(row)

    assert row.priority == "normal"
    assert row.risk_level == "medium"
    assert row.queue_name == "reader_ops"
    assert "base_priority_score=" in row.urgency_reason
    assert "risk_score=" in row.urgency_reason


def test_policy_promotes_seven_day_overdue_to_urgent_high() -> None:
    row = _task(
        title="overdue loan",
        source_type="overdue",
        task_group="borrow",
        related_entity_type="loan",
        related_entity_id="42",
        source_payload_json=_payload(
            _requested_priority="normal",
            action="overdue_case",
            overdue_days=10,
            reader_code="R-PYTEST",
            loan_id=42,
        ),
    )

    apply_task_policy(row)

    assert row.priority == "urgent"
    assert row.risk_level == "high"
    assert row.queue_name == "human_review"
    assert "hard=overdue>=7d" in row.urgency_reason


def test_policy_marks_reader_governance_as_high_risk_without_critical() -> None:
    row = _task(
        title="suspend reader",
        source_type="ai_admin",
        task_group="review",
        related_entity_type="reader",
        related_entity_id="7",
        source_payload_json=_payload(
            _requested_priority="normal",
            action="suspend_reader",
            reader_code="R-PYTEST",
        ),
    )

    apply_task_policy(row)

    assert row.risk_level == "high"
    assert row.queue_name == "human_review"


def test_policy_marks_system_settings_as_critical() -> None:
    row = _task(
        title="update system settings",
        source_type="ai_admin",
        task_group="review",
        source_payload_json=_payload(
            _requested_priority="normal",
            action="update_system_settings",
            affected_count=1,
        ),
    )

    apply_task_policy(row)

    assert row.risk_level == "critical"
    assert row.queue_name == "human_review"
    assert "hard=critical_governance_or_batch" in row.urgency_reason
