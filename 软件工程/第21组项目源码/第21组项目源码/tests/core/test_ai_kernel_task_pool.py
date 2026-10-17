from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SOURCE_DB = BACKEND / "data" / "bookflow.db"


def _run_backend_script(tmp_path: Path, script: str) -> subprocess.CompletedProcess[str]:
    db_path = tmp_path / "bookflow_kernel_test.db"
    shutil.copy2(SOURCE_DB, db_path)
    env = os.environ.copy()
    env["BOOKFLOW_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env["BOOKFLOW_AI_KERNEL_WORKER_ENABLED"] = "false"
    env["PYTHONPATH"] = str(BACKEND) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        cwd=BACKEND,
        env=env,
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )


def _assert_ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stdout + result.stderr


def test_ai_kernel_leases_highest_priority_task_and_completes_low_risk(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from sqlalchemy import select

        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import AITaskCheckpoint, WorkTask
        from bookflow_core.services.task_service import create_task
        from bookflow_core.ai.kernel.agent import process_task
        from bookflow_core.ai.kernel.task_queue import lease_next_task, queue_summary, refresh_queue

        ensure_schema()
        with get_session() as db:
            low = create_task(
                db,
                title="kernel low risk admin",
                priority="low",
                source_type="system",
                task_group="other",
                actor_id="pytest",
            )
            high = create_task(
                db,
                title="kernel urgent risk review",
                priority="urgent",
                source_type="risk",
                task_group="exception",
                requires_human_confirmation=True,
                actor_id="pytest",
            )
            assert high.priority_score > low.priority_score
            assert high.risk_level in {"high", "critical"}

            refresh_queue(db)
            leased = lease_next_task(db, worker_id="pytest_worker")
            assert leased.task_code == high.task_code
            assert leased.status == "ai_processing"
            assert leased.lease_owner == "pytest_worker"
            assert leased.attempt_count == 1

            processed = process_task(db, low.task_code, worker_id="pytest_worker")
            assert processed["status"] == "success"
            low_after = db.scalar(select(WorkTask).where(WorkTask.task_code == low.task_code))
            assert low_after.status == "resolved"
            assert low_after.lease_owner is None
            assert db.scalar(select(AITaskCheckpoint).where(AITaskCheckpoint.task_id == low_after.id)) is not None

            summary = queue_summary(db)
            assert summary["active_total"] >= 1
        """,
    )
    _assert_ok(result)


def test_ai_kernel_process_next_interrupts_high_risk_tasks_for_admin_takeover(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from sqlalchemy import select

        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import WorkTask
        from bookflow_core.services.task_service import create_task, takeover_task
        from bookflow_core.ai.kernel.agent import process_next_task

        ensure_schema()
        with get_session() as db:
            task = create_task(
                db,
                title="kernel high risk interruption",
                description="requires admin confirmation",
                priority="high",
                source_type="ai_review",
                task_group="exception",
                requires_human_confirmation=True,
                actor_id="pytest",
            )

            result = process_next_task(db, worker_id="pytest_worker")
            assert result["status"] == "waiting_human"
            refreshed = db.scalar(select(WorkTask).where(WorkTask.task_code == task.task_code))
            assert refreshed.status == "waiting_human"
            assert refreshed.claim_status == "waiting_human"
            assert refreshed.lease_owner is None
            assert refreshed.interrupt_reason == "human_confirmation_required"

            taken = takeover_task(db, task.task_code, admin_code="pytest_admin", reason="kernel test", actor_id="pytest_admin")
            assert taken.status == "admin_processing"
        """,
    )
    _assert_ok(result)


def test_ai_kernel_api_replaces_legacy_autonomy_routes(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from fastapi.testclient import TestClient
        from sqlalchemy import select

        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.core.security import create_access_token
        from bookflow_core.main import app
        from bookflow_core.models import AdminUser
        from bookflow_core.services.permission_service import admin_role

        ensure_schema()
        with get_session() as db:
            admin = db.scalar(select(AdminUser).where(AdminUser.status == "active").order_by(AdminUser.id.asc()))
            assert admin is not None
            token = create_access_token(admin.id, role=admin_role(admin), subject_type="admin", admin_code=admin.admin_code)

        client = TestClient(app)
        headers = {"Authorization": f"Bearer {token}"}

        old_resp = client.post("/ai/autonomy/patrol/overdue", headers=headers)
        assert old_resp.status_code == 404, old_resp.text

        patrol_resp = client.post("/ai/kernel/patrol/daily", json={"auto_process": False}, headers=headers)
        assert patrol_resp.status_code == 200, patrol_resp.text
        patrol_data = patrol_resp.json()["data"]
        assert patrol_data["status"] == "queued"
        assert patrol_data["kernel"] is True
        assert patrol_data["task"]["source_type"] == "patrol"

        queue_resp = client.get("/ai/kernel/queue", headers=headers)
        assert queue_resp.status_code == 200, queue_resp.text
        assert queue_resp.json()["data"]["active_total"] >= 1

        runs_resp = client.get("/ai/kernel/runs", headers=headers)
        assert runs_resp.status_code == 200, runs_resp.text
        assert "items" in runs_resp.json()["data"]
        """,
    )
    _assert_ok(result)


def test_risk_warning_creates_kernel_task(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from sqlalchemy import select

        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import WorkTask
        from bookflow_core.services.risk_service import create_risk_warning

        ensure_schema()
        with get_session() as db:
            warning = create_risk_warning(
                db,
                warning_type="pytest_risk",
                severity="high",
                title="pytest risk",
                description="kernel task should be created",
                actor_type="system",
                actor_id="pytest",
            )
            assert warning.created_task_id is not None
            task = db.get(WorkTask, warning.created_task_id)
            assert task is not None
            assert task.source_type == "risk"
            assert task.task_group == "risk"
            assert task.risk_warning_code == warning.warning_code
            assert task.requires_human_confirmation is True
            assert task.status == "pending"
        """,
    )
    _assert_ok(result)


def test_tool_permission_allows_high_risk_write_tool_with_complete_payload(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from sqlalchemy import select

        from bookflow_core.ai.tools.dispatcher import dispatch_tool
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import AIApprovalRequest, BookCategory, BookCopy
        from bookflow_core.services.catalog_service import create_book

        ensure_schema()
        with get_session() as db:
            category = db.scalar(select(BookCategory).order_by(BookCategory.id.asc()))
            if category is None:
                category = BookCategory(category_code="PYT", category_name="pytest", book_title_count=0, copy_count=0)
                db.add(category)
                db.flush()
            book = create_book(
                db,
                title="pytest permission book",
                category_id=category.id,
                initial_copies=1,
                actor_id="pytest",
                commit=False,
            )
            copy = db.scalar(select(BookCopy).where(BookCopy.book_id == book.id).order_by(BookCopy.id.asc()))
            assert copy is not None
            result = dispatch_tool(
                db,
                "ai_update_copy_status",
                {"copy_code": copy.copy_code, "new_status": copy.copy_status, "reason": "pytest permission"},
                actor_id="pytest_worker",
                planner_context=True,
            )
            assert result["status"] == "success"
            assert result["data"]["copy_code"] == copy.copy_code
            approval = db.scalar(select(AIApprovalRequest).where(AIApprovalRequest.requested_action == "ai_update_copy_status"))
            assert approval is None
        """,
    )
    _assert_ok(result)


def test_ai_kernel_worker_once_processes_task_pool(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from sqlalchemy import select

        from bookflow_core.ai.kernel.worker import run_ai_kernel_worker_once
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import WorkTask
        from bookflow_core.services.task_service import create_task

        ensure_schema()
        with get_session() as db:
            task = create_task(
                db,
                title="worker low risk task",
                priority="normal",
                source_type="system",
                task_group="other",
                actor_id="pytest",
            )
            task_code = task.task_code

        result = run_ai_kernel_worker_once(worker_id="pytest_worker", batch_size=2)
        assert result["processed_count"] >= 1
        assert result["error_count"] == 0

        with get_session() as db:
            refreshed = db.scalar(select(WorkTask).where(WorkTask.task_code == task_code))
            assert refreshed.status == "resolved"
            assert refreshed.ai_run_id is not None
            assert refreshed.lease_owner is None
        """,
    )
    _assert_ok(result)


def test_ai_kernel_splits_multi_intent_plan_into_child_tasks(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        import json
        from sqlalchemy import select

        from bookflow_core.ai.kernel.agent import process_task
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import AgentRun, WorkTask
        from bookflow_core.services.task_service import create_task

        ensure_schema()
        with get_session() as db:
            task = create_task(
                db,
                title="multi step read plan",
                priority="normal",
                source_type="system",
                task_group="other",
                source_payload={
                    "tool_calls": [
                        {"tool_name": "ai_get_task_summary", "arguments": {}, "reason": "inspect task pool"},
                        {"tool_name": "ai_get_notification_summary", "arguments": {}, "reason": "inspect notifications"},
                    ]
                },
                actor_id="pytest",
            )
            result = process_task(db, task.task_code, worker_id="pytest_worker")
            assert result["status"] == "success"
            refreshed = db.scalar(select(WorkTask).where(WorkTask.task_code == task.task_code))
            assert refreshed.status == "resolved"
            plan = json.loads(refreshed.ai_plan_json)
            assert plan["action"] == "split_tasks"
            run = db.scalar(select(AgentRun).where(AgentRun.id == refreshed.ai_run_id))
            output = json.loads(run.output_json)
            assert output["status"] == "success"
            children = db.scalars(select(WorkTask).where(WorkTask.source_task_id == refreshed.id).order_by(WorkTask.id.asc())).all()
            assert len(children) == 2
            assert [json.loads(child.source_payload_json)["tool_name"] for child in children] == ["ai_get_task_summary", "ai_get_notification_summary"]
            assert json.loads(children[1].source_payload_json)["depends_on_task_code"] == children[0].task_code
            assert output["task_package"]["created_count"] == 2
        """,
    )
    _assert_ok(result)


def test_ai_kernel_multi_step_plan_stops_at_missing_information(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        import json
        from sqlalchemy import select

        from bookflow_core.ai.kernel.agent import process_task
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import AgentRun, AIApprovalRequest, WorkTask
        from bookflow_core.services.task_service import create_task

        ensure_schema()
        with get_session() as db:
            task = create_task(
                db,
                title="multi step missing information plan",
                priority="normal",
                source_type="system",
                task_group="other",
                source_payload={
                    "process_subtasks_immediately": True,
                    "tool_calls": [
                        {"tool_name": "ai_get_task_summary", "arguments": {}, "reason": "inspect first"},
                        {"tool_name": "ai_update_copy_status", "arguments": {"new_status": "maintenance", "reason": "pytest"}, "reason": "missing copy code"},
                    ]
                },
                actor_id="pytest",
            )
            result = process_task(db, task.task_code, worker_id="pytest_worker")
            assert result["status"] == "needs_clarification"
            refreshed = db.scalar(select(WorkTask).where(WorkTask.task_code == task.task_code))
            assert refreshed.status == "waiting_human"
            assert refreshed.interrupt_reason.startswith("subtask_blocked:needs_clarification:")
            run = db.scalar(select(AgentRun).where(AgentRun.id == refreshed.ai_run_id))
            output = json.loads(run.output_json)
            assert output["status"] == "needs_clarification"
            assert [item["status"] for item in output["child_results"]] == ["success", "needs_clarification"]
            assert [item["status"] for item in output["tool_results"]] == ["success", "needs_clarification"]
            assert "copy_code" in output["tool_results"][1]["result"]["missing_fields"]
            children = db.scalars(select(WorkTask).where(WorkTask.source_task_id == refreshed.id).order_by(WorkTask.id.asc())).all()
            assert len(children) == 2
            assert children[0].status == "resolved"
            assert children[1].status == "waiting_human"
            approval = db.scalar(select(AIApprovalRequest).where(AIApprovalRequest.requested_action == "ai_update_copy_status"))
            assert approval is None
        """,
    )
    _assert_ok(result)


def test_ai_kernel_dynamic_agent_loop_replans_after_observation(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        import json
        from sqlalchemy import select

        from bookflow_core.ai.kernel.agent import process_task
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import AgentRun, WorkTask
        from bookflow_core.services.task_service import create_task

        class FakePlanner:
            def __init__(self):
                self.calls = 0

            def complete_json(self, *, messages, temperature=0):
                self.calls += 1
                if self.calls == 1:
                    return {
                        "action": "execute_tool",
                        "tool_name": "ai_get_task_summary",
                        "arguments": {},
                        "reason": "first observe task pool",
                        "confidence": 0.9,
                    }
                if self.calls == 2:
                    return {
                        "action": "execute_tool",
                        "tool_name": "ai_get_notification_summary",
                        "arguments": {},
                        "reason": "second observe notifications",
                        "confidence": 0.9,
                    }
                return {
                    "action": "complete",
                    "reason": "observations are sufficient",
                    "confidence": 0.95,
                }

        ensure_schema()
        with get_session() as db:
            task = create_task(
                db,
                title="dynamic loop task",
                priority="normal",
                source_type="system",
                task_group="other",
                source_payload={"dynamic_agent_loop": True, "original_intent": "inspect operations dynamically"},
                actor_id="pytest",
            )
            planner = FakePlanner()
            result = process_task(db, task.task_code, worker_id="pytest_worker", llm_client=planner)
            assert result["status"] == "success"
            assert planner.calls == 3
            refreshed = db.scalar(select(WorkTask).where(WorkTask.task_code == task.task_code))
            assert refreshed.status == "resolved"
            run = db.scalar(select(AgentRun).where(AgentRun.id == refreshed.ai_run_id))
            output = json.loads(run.output_json)
            assert output["plan"]["action"] == "dynamic_agent_loop"
            assert [item["tool_name"] for item in output["tool_results"]] == ["ai_get_task_summary", "ai_get_notification_summary"]
            assert len(output["observations"]) == 2
            assert [plan["action"] for plan in output["plan"]["plans"]] == ["execute_tool", "execute_tool", "complete"]
        """,
    )
    _assert_ok(result)


def test_ai_kernel_sop_triages_overdue_case_with_read_steps(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        import json
        from sqlalchemy import select

        from bookflow_core.ai.kernel.agent import process_task
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import AgentRun, ReaderAccount, WorkTask
        from bookflow_core.services.task_service import create_task

        ensure_schema()
        with get_session() as db:
            reader = db.scalar(select(ReaderAccount).order_by(ReaderAccount.id.asc()))
            assert reader is not None
            task = create_task(
                db,
                title="pytest overdue sop case",
                description="overdue case needs autonomous triage",
                priority="normal",
                source_type="overdue",
                task_group="borrow",
                source_payload={
                    "kernel_intent": "overdue_case",
                    "reader_code": reader.reader_code,
                    "copy_code": "",
                    "overdue_days": 3,
                },
                actor_id="pytest",
            )
            result = process_task(db, task.task_code, worker_id="pytest_worker")
            assert result["status"] == "success"
            refreshed = db.scalar(select(WorkTask).where(WorkTask.task_code == task.task_code))
            assert refreshed.status == "resolved"
            plan = json.loads(refreshed.ai_plan_json)
            assert plan["action"] == "execute_plan"
            assert plan["sop_id"] == "overdue_case_triage"
            run = db.scalar(select(AgentRun).where(AgentRun.id == refreshed.ai_run_id))
            output = json.loads(run.output_json)
            tool_names = [item["tool_name"] for item in output["tool_results"]]
            assert tool_names == ["ai_get_loans", "ai_get_overdue_cases", "ai_get_reader_activity"]
            assert all(item["status"] == "success" for item in output["tool_results"])
        """,
    )
    _assert_ok(result)


def test_ai_kernel_sop_handles_business_reservation_event_and_explicit_notification(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        import json
        from sqlalchemy import select

        from bookflow_core.ai.kernel.agent import process_task
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import AgentRun, ReaderAccount, WorkTask
        from bookflow_core.services.task_service import create_task

        ensure_schema()
        with get_session() as db:
            reader = db.scalar(select(ReaderAccount).order_by(ReaderAccount.id.asc()))
            assert reader is not None
            task = create_task(
                db,
                title="pytest reservation business event",
                description="business event should be inspected by sop",
                priority="normal",
                source_type="reader_event",
                task_group="reservation",
                source_payload={
                    "kernel_intent": "business_event",
                    "action": "create_reader_reservation",
                    "payload": {
                        "reader_code": reader.reader_code,
                        "book_code": "NOT_REAL_BOOK",
                        "status": "waiting",
                        "notify_admins": True,
                    },
                },
                actor_id="pytest",
            )
            result = process_task(db, task.task_code, worker_id="pytest_worker")
            assert result["status"] == "success"
            refreshed = db.scalar(select(WorkTask).where(WorkTask.task_code == task.task_code))
            assert refreshed.status == "resolved"
            plan = json.loads(refreshed.ai_plan_json)
            assert plan["action"] == "execute_plan"
            assert plan["sop_id"] == "reservation_event_triage"
            run = db.scalar(select(AgentRun).where(AgentRun.id == refreshed.ai_run_id))
            output = json.loads(run.output_json)
            tool_names = [item["tool_name"] for item in output["tool_results"]]
            assert tool_names == ["ai_get_reservations", "ai_get_reader_activity", "ai_create_task_notifications"]
            assert all(item["status"] == "success" for item in output["tool_results"])
        """,
    )
    _assert_ok(result)


def test_ai_kernel_sop_outcome_hands_off_when_required_evidence_is_missing(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        import json
        from sqlalchemy import select

        from bookflow_core.ai.kernel.agent import process_task
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import AgentRun, WorkTask
        from bookflow_core.services.task_service import create_task

        ensure_schema()
        with get_session() as db:
            task = create_task(
                db,
                title="pytest reservation evidence required",
                description="missing reservation evidence should not auto close",
                priority="normal",
                source_type="reader_event",
                task_group="reservation",
                source_payload={
                    "kernel_intent": "business_event",
                    "action": "create_reader_reservation",
                    "payload": {
                        "book_code": "PYTEST-NOT-REAL-BOOK-CODE",
                        "status": "waiting",
                        "require_evidence": True,
                    },
                },
                actor_id="pytest",
            )
            result = process_task(db, task.task_code, worker_id="pytest_worker")
            assert result["status"] == "waiting_human"
            refreshed = db.scalar(select(WorkTask).where(WorkTask.task_code == task.task_code))
            assert refreshed.status == "waiting_human"
            assert refreshed.interrupt_reason == "sop_missing_expected_evidence"
            run = db.scalar(select(AgentRun).where(AgentRun.id == refreshed.ai_run_id))
            output = json.loads(run.output_json)
            assert output["outcome"]["decision"] == "handoff"
            assert output["outcome"]["reason"] == "sop_missing_expected_evidence"
            assert [item["tool_name"] for item in output["tool_results"]] == ["ai_get_reservations"]
        """,
    )
    _assert_ok(result)


def test_ai_kernel_followup_notifies_reader_for_ready_reservation(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        import json
        from sqlalchemy import select

        from bookflow_core.ai.kernel.agent import process_task
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.core.time import now
        from bookflow_core.models import AgentRun, Book, NotificationDelivery, NotificationMessage, ReaderAccount, Reservation, WorkTask
        from bookflow_core.services.task_service import create_task

        ensure_schema()
        with get_session() as db:
            reader = db.scalar(select(ReaderAccount).order_by(ReaderAccount.id.asc()))
            book = db.scalar(select(Book).order_by(Book.id.asc()))
            assert reader is not None
            if book is None:
                book = Book(book_code="BK-PYTEST-FOLLOWUP", title="pytest followup book", circulation_type="normal", status="active")
                db.add(book)
                db.flush()
            reservation = Reservation(
                reservation_code="RSV-PYTEST-FOLLOWUP",
                reader_id=reader.id,
                book_id=book.id,
                status="ready_for_pickup",
                requested_at=now(),
                created_by_code=reader.reader_code,
                created_at=now(),
                updated_at=now(),
            )
            db.add(reservation)
            db.flush()
            task = create_task(
                db,
                title="pytest ready reservation followup",
                description="ready reservation should notify reader after sop",
                priority="normal",
                source_type="reader_event",
                task_group="reservation",
                source_payload={
                    "kernel_intent": "business_event",
                    "action": "create_reader_reservation",
                    "payload": {
                        "reader_code": reader.reader_code,
                        "book_code": book.book_code,
                        "status": "ready_for_pickup",
                    },
                },
                actor_id="pytest",
            )
            result = process_task(db, task.task_code, worker_id="pytest_worker")
            assert result["status"] == "success"
            refreshed = db.scalar(select(WorkTask).where(WorkTask.task_code == task.task_code))
            assert refreshed.status == "resolved"
            run = db.scalar(select(AgentRun).where(AgentRun.id == refreshed.ai_run_id))
            output = json.loads(run.output_json)
            assert output["outcome"]["matched_reservations"] >= 1
            assert output["outcome"]["followup_steps"] == 1
            assert [item["tool_name"] for item in output["followup_results"]] == ["ai_create_notification"]
            notice = db.scalar(
                select(NotificationMessage).where(
                    NotificationMessage.notification_type == "reservation",
                    NotificationMessage.title == "预约图书已到馆",
                )
            )
            assert notice is not None
            assert notice.lifecycle_status == "completed"
            delivery = db.scalar(
                select(NotificationDelivery).where(
                    NotificationDelivery.message_id == notice.id,
                    NotificationDelivery.recipient_type == "reader",
                    NotificationDelivery.recipient_id == reader.id,
                )
            )
            assert delivery is not None
            assert delivery.delivery_status == "sent"
            assert delivery.read_status == "unread"
        """,
    )
    _assert_ok(result)


def test_ai_kernel_followup_idempotency_skips_duplicate_ready_reservation_notice(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        import json
        from sqlalchemy import func, select

        from bookflow_core.ai.kernel.agent import process_task
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.core.time import now
        from bookflow_core.models import AgentRun, AIExecutionLedger, Book, NotificationDelivery, NotificationMessage, ReaderAccount, Reservation
        from bookflow_core.services.task_service import create_task

        ensure_schema()
        with get_session() as db:
            reader = db.scalar(select(ReaderAccount).order_by(ReaderAccount.id.asc()))
            assert reader is not None
            book = Book(book_code="BK-PYTEST-IDEMPOTENT", title="pytest idempotent book", circulation_type="normal", status="active")
            db.add(book)
            db.flush()
            db.add(
                Reservation(
                    reservation_code="RSV-PYTEST-IDEMPOTENT",
                    reader_id=reader.id,
                    book_id=book.id,
                    status="ready_for_pickup",
                    requested_at=now(),
                    created_by_code=reader.reader_code,
                    created_at=now(),
                    updated_at=now(),
                )
            )
            payload = {
                "kernel_intent": "business_event",
                "action": "create_reader_reservation",
                "payload": {"reader_code": reader.reader_code, "book_code": book.book_code, "status": "ready_for_pickup"},
            }
            first = create_task(db, title="pytest idempotent first", priority="normal", source_type="reader_event", task_group="reservation", source_payload=payload, actor_id="pytest")
            second = create_task(db, title="pytest idempotent second", priority="normal", source_type="reader_event", task_group="reservation", source_payload=payload, actor_id="pytest")
            assert process_task(db, first.task_code, worker_id="pytest_worker")["status"] == "success"
            assert process_task(db, second.task_code, worker_id="pytest_worker")["status"] == "success"

            notice_count = db.scalar(
                select(func.count(NotificationDelivery.id))
                .join(NotificationMessage, NotificationDelivery.message_id == NotificationMessage.id)
                .where(
                    NotificationDelivery.recipient_type == "reader",
                    NotificationDelivery.recipient_id == reader.id,
                    NotificationMessage.notification_type == "reservation",
                    NotificationMessage.title == "预约图书已到馆",
                )
            )
            assert notice_count == 1
            ledger_count = db.scalar(select(func.count(AIExecutionLedger.id)).where(AIExecutionLedger.status == "completed"))
            assert ledger_count == 1
            run = db.scalar(select(AgentRun).where(AgentRun.id == second.ai_run_id))
            output = json.loads(run.output_json)
            assert output["followup_results"][0]["status"] == "skipped"
        """,
    )
    _assert_ok(result)


def test_ai_kernel_unhandled_error_schedules_retry_without_stale_lease(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from sqlalchemy import select

        import bookflow_core.ai.kernel.agent as agent
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import AgentRun, WorkTask
        from bookflow_core.services.task_service import create_task

        ensure_schema()
        with get_session() as db:
            task = create_task(
                db,
                title="pytest retry on unhandled kernel error",
                priority="normal",
                source_type="system",
                task_group="other",
                source_payload={"tool_name": "ai_get_task_summary", "arguments": {}},
                actor_id="pytest",
            )
            original = agent.evaluate_execution_outcome
            agent.evaluate_execution_outcome = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("pytest outcome crash"))
            try:
                try:
                    agent.process_task(db, task.task_code, worker_id="pytest_worker")
                except RuntimeError as exc:
                    assert "pytest outcome crash" in str(exc)
                else:
                    raise AssertionError("process_task should raise")
            finally:
                agent.evaluate_execution_outcome = original

            refreshed = db.scalar(select(WorkTask).where(WorkTask.task_code == task.task_code))
            assert refreshed.status == "pending"
            assert refreshed.lease_owner is None
            assert refreshed.lease_expires_at is None
            assert refreshed.next_attempt_at is not None
            assert refreshed.attempt_count == 1
            run = db.scalar(select(AgentRun).where(AgentRun.id == refreshed.ai_run_id))
            assert run.status == "failed"
        """,
    )
    _assert_ok(result)


def test_ai_kernel_expanded_sops_cover_reader_and_collection_ops(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        import json
        from sqlalchemy import select

        from bookflow_core.ai.kernel.agent import process_task
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import ReaderAccount, WorkTask
        from bookflow_core.services.task_service import create_task

        ensure_schema()
        with get_session() as db:
            reader = db.scalar(select(ReaderAccount).order_by(ReaderAccount.id.asc()))
            assert reader is not None
            reader_task = create_task(
                db,
                title="pytest reader sop",
                priority="normal",
                source_type="reader_event",
                task_group="review",
                source_payload={"kernel_intent": "reader_case", "reader_code": reader.reader_code},
                actor_id="pytest",
            )
            collection_task = create_task(
                db,
                title="pytest collection sop",
                priority="normal",
                source_type="catalog",
                task_group="catalog",
                source_payload={"kernel_intent": "collection_health"},
                actor_id="pytest",
            )
            assert process_task(db, reader_task.task_code, worker_id="pytest_worker")["status"] == "success"
            assert process_task(db, collection_task.task_code, worker_id="pytest_worker")["status"] == "success"

            reader_after = db.scalar(select(WorkTask).where(WorkTask.task_code == reader_task.task_code))
            collection_after = db.scalar(select(WorkTask).where(WorkTask.task_code == collection_task.task_code))
            assert json.loads(reader_after.ai_plan_json)["sop_id"] == "reader_account_triage"
            assert json.loads(collection_after.ai_plan_json)["sop_id"] == "collection_ops_triage"
        """,
    )
    _assert_ok(result)


def test_new_circulation_tools_auto_register_and_execute_safe_reads(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from bookflow_core.ai.tools.dispatcher import dispatch_tool
        from bookflow_core.ai.tools.schema_builder import tool_schemas_for_llm
        from bookflow_core.core.database import ensure_schema, get_session

        ensure_schema()
        with get_session() as db:
            tool_names = {item["tool_name"] for item in tool_schemas_for_llm(db)}
            for name in {"ai_get_loans", "ai_get_overdue_cases", "ai_get_reservations", "ai_scan_overdues"}:
                assert name in tool_names

            loans = dispatch_tool(db, "ai_get_loans", {"limit": 3}, actor_id="pytest_worker", planner_context=True)
            assert loans["status"] == "success"
            assert "items" in loans["data"]

            overdues = dispatch_tool(db, "ai_get_overdue_cases", {"limit": 3}, actor_id="pytest_worker", planner_context=True)
            assert overdues["status"] == "success"
            assert "items" in overdues["data"]

            reservations = dispatch_tool(db, "ai_get_reservations", {"limit": 3}, actor_id="pytest_worker", planner_context=True)
            assert reservations["status"] == "success"
            assert "items" in reservations["data"]
        """,
    )
    _assert_ok(result)


def test_new_circulation_write_tools_require_complete_payload(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from bookflow_core.ai.tools.dispatcher import dispatch_tool
        from bookflow_core.core.database import ensure_schema, get_session

        ensure_schema()
        with get_session() as db:
            scan = dispatch_tool(db, "ai_scan_overdues", {}, actor_id="pytest_worker", planner_context=True)
            assert scan["status"] == "success"
            assert "overdue_count" in scan["data"]

            fulfill = dispatch_tool(db, "ai_fulfill_reservation", {}, actor_id="pytest_worker", planner_context=True)
            assert fulfill["status"] == "needs_clarification"
            assert "reservation_id" in fulfill["missing_fields"]
        """,
    )
    _assert_ok(result)


def test_reader_tools_auto_register_and_high_risk_writes_execute_with_audit_policy(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from sqlalchemy import select

        from bookflow_core.ai.tools.dispatcher import dispatch_tool
        from bookflow_core.ai.tools.schema_builder import tool_schemas_for_llm
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import AIApprovalRequest, ReaderAccount

        ensure_schema()
        with get_session() as db:
            reader = db.scalar(select(ReaderAccount).order_by(ReaderAccount.id.asc()))
            assert reader is not None
            tool_names = {item["tool_name"] for item in tool_schemas_for_llm(db)}
            for name in {"ai_get_readers", "ai_get_reader_activity", "ai_adjust_reader_credit", "ai_suspend_reader", "ai_restore_reader"}:
                assert name in tool_names

            readers = dispatch_tool(db, "ai_get_readers", {"limit": 2}, actor_id="pytest_worker", planner_context=True)
            assert readers["status"] == "success"
            assert "items" in readers["data"]

            activity = dispatch_tool(db, "ai_get_reader_activity", {"reader_code": reader.reader_code}, actor_id="pytest_worker", planner_context=True)
            assert activity["status"] == "success"
            assert activity["data"]["reader_code"] == reader.reader_code

            suspend = dispatch_tool(db, "ai_suspend_reader", {"reader_code": reader.reader_code, "reason": "pytest"}, actor_id="pytest_worker", planner_context=True)
            assert suspend["status"] == "success"
            assert suspend["data"]["status"] == "suspended"
            approval = db.scalar(select(AIApprovalRequest).where(AIApprovalRequest.requested_action == "ai_suspend_reader"))
            assert approval is None
        """,
    )
    _assert_ok(result)


def test_notification_tools_create_and_send(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from sqlalchemy import select

        from bookflow_core.ai.tools.dispatcher import dispatch_tool
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import NotificationMessage, ReaderAccount

        ensure_schema()
        with get_session() as db:
            reader = db.scalar(select(ReaderAccount).order_by(ReaderAccount.id.asc()))
            assert reader is not None
            missing = dispatch_tool(
                db,
                "ai_create_notification",
                {"recipient_type": "reader", "recipient_id": reader.reader_code, "title": "pytest missing notice"},
                actor_id="pytest_worker",
                planner_context=True,
            )
            assert missing["status"] == "needs_clarification"
            assert "content" in missing["missing_fields"]
            assert db.scalar(select(NotificationMessage).where(NotificationMessage.title == "pytest missing notice")) is None

            created = dispatch_tool(
                db,
                "ai_create_notification",
                {"recipient_type": "reader", "recipient_id": reader.reader_code, "title": "pytest notice", "content": "hello"},
                actor_id="pytest_worker",
                planner_context=True,
            )
            assert created["status"] == "success"
            notification_id = created["data"]["id"]
            sent = dispatch_tool(db, "ai_send_notification", {"notification_id": notification_id}, actor_id="pytest_worker", planner_context=True)
            assert sent["status"] == "success"
            assert sent["data"]["status"] == "sent"
        """,
    )
    _assert_ok(result)


def test_task_dispatch_tools_assign_and_resolve(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from sqlalchemy import select

        from bookflow_core.ai.tools.dispatcher import dispatch_tool
        from bookflow_core.ai.tools.schema_builder import tool_schemas_for_llm
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import AdminUser, WorkTask
        from bookflow_core.services.task_service import create_task

        ensure_schema()
        with get_session() as db:
            admin = db.scalar(select(AdminUser).where(AdminUser.status == "active").order_by(AdminUser.id.asc()))
            assert admin is not None
            tool_names = {item["tool_name"] for item in tool_schemas_for_llm(db)}
            for name in {"ai_get_tasks", "ai_assign_task_to_admin", "ai_resolve_work_task"}:
                assert name in tool_names

            task = create_task(db, title="pytest assign task", priority="normal", source_type="system", actor_id="pytest")
            listed = dispatch_tool(db, "ai_get_tasks", {"keyword": "pytest assign", "limit": 5}, actor_id="pytest_worker", planner_context=True)
            assert listed["status"] == "success"
            assert any(item["task_code"] == task.task_code for item in listed["data"]["items"])

            assigned = dispatch_tool(
                db,
                "ai_assign_task_to_admin",
                {"task_code": task.task_code, "admin_code": admin.admin_code, "reason": "pytest assign"},
                actor_id="pytest_worker",
                planner_context=True,
            )
            assert assigned["status"] == "success"
            assert assigned["data"]["status"] == "admin_processing"
            assert assigned["data"]["claimed_by_code"] == admin.admin_code

            second = create_task(db, title="pytest resolve task", priority="low", source_type="system", actor_id="pytest")
            resolved = dispatch_tool(
                db,
                "ai_resolve_work_task",
                {"task_code": second.task_code, "resolution": "pytest resolved"},
                actor_id="pytest_worker",
                planner_context=True,
            )
            assert resolved["status"] == "success"
            assert resolved["data"]["status"] == "resolved"
            refreshed = db.scalar(select(WorkTask).where(WorkTask.task_code == second.task_code))
            assert refreshed.resolution == "pytest resolved"
        """,
    )
    _assert_ok(result)
