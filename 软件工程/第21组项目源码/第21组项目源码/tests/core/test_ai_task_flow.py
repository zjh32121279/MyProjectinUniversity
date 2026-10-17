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
    db_path = tmp_path / "bookflow_test.db"
    shutil.copy2(SOURCE_DB, db_path)
    env = os.environ.copy()
    env["BOOKFLOW_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env["PYTHONPATH"] = str(BACKEND) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        cwd=BACKEND,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def _assert_ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stdout + result.stderr


def test_task_service_ai_handoff_takeover_and_cancel_paths(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from sqlalchemy import select

        from bookflow_core.core.database import get_session
        from bookflow_core.models import AuditEvent, WorkTaskEvent
        from bookflow_core.services.task_service import (
            ai_complete_task,
            ai_fail_task,
            ai_start_task,
            cancel_task,
            create_task,
            resolve_task,
            takeover_task,
        )

        with get_session() as db:
            completed = create_task(
                db,
                title="service ai complete",
                priority="normal",
                source_type="ai",
                task_group="review",
                actor_id="pytest",
            )
            assert completed.status == "pending"
            completed = ai_start_task(db, completed.task_code, run_id=101, actor_id="pytest_ai")
            assert completed.status == "ai_processing"
            completed = ai_complete_task(db, completed.task_code, run_id=101, result="done", actor_id="pytest_ai")
            assert completed.status == "resolved"
            assert completed.claim_status == "ai_completed"

            handed_off = create_task(
                db,
                title="service ai handoff",
                priority="high",
                source_type="ai",
                task_group="exception",
                auto_start_ai=True,
                actor_id="pytest",
            )
            assert handed_off.status == "ai_processing"
            handed_off = ai_fail_task(db, handed_off.task_code, run_id=102, error="low confidence", confidence=0.2, actor_id="pytest_ai")
            assert handed_off.status == "waiting_human"
            assert bool(handed_off.requires_human_confirmation) is True
            handed_off = takeover_task(db, handed_off.task_code, admin_code="pytest_admin", reason="manual review", actor_id="pytest_admin")
            assert handed_off.status == "admin_processing"
            assert handed_off.claim_status == "admin_claimed"
            handed_off = resolve_task(db, handed_off.task_code, resolution="handled", actor_id="pytest_admin")
            assert handed_off.status == "resolved"

            overridden = create_task(
                db,
                title="service admin overrides ai",
                priority="urgent",
                source_type="ai",
                task_group="exception",
                auto_start_ai=True,
                actor_id="pytest",
            )
            overridden = takeover_task(db, overridden.task_code, admin_code="pytest_admin", reason="urgent override", actor_id="pytest_admin")
            assert overridden.status == "admin_processing"
            assert overridden.claim_status == "overridden_by_admin"
            overridden = resolve_task(db, overridden.task_code, resolution="admin resolved", actor_id="pytest_admin")
            assert overridden.status == "resolved"
            assert overridden.claim_status == "overridden_by_admin"

            cancellable_statuses = []
            pending = create_task(db, title="cancel pending", priority="low", source_type="system", task_group="other", actor_id="pytest")
            cancellable_statuses.append(cancel_task(db, pending.task_code, reason="not needed", actor_id="pytest_admin").status)
            ai_running = create_task(db, title="cancel ai", priority="normal", source_type="ai", task_group="review", auto_start_ai=True, actor_id="pytest")
            cancellable_statuses.append(cancel_task(db, ai_running.task_code, reason="not needed", actor_id="pytest_admin").status)
            waiting = create_task(db, title="cancel waiting", priority="normal", source_type="ai", task_group="exception", auto_start_ai=True, actor_id="pytest")
            waiting = ai_fail_task(db, waiting.task_code, error="handoff", actor_id="pytest_ai")
            cancellable_statuses.append(cancel_task(db, waiting.task_code, reason="not needed", actor_id="pytest_admin").status)
            admin_task = create_task(db, title="cancel admin", priority="normal", source_type="system", task_group="other", actor_id="pytest")
            admin_task = takeover_task(db, admin_task.task_code, admin_code="pytest_admin", actor_id="pytest_admin")
            cancellable_statuses.append(cancel_task(db, admin_task.task_code, reason="not needed", actor_id="pytest_admin").status)
            assert cancellable_statuses == ["cancelled", "cancelled", "cancelled", "cancelled"]

            actions = db.scalars(
                select(AuditEvent.action).where(AuditEvent.actor_code.in_(["pytest", "pytest_ai", "pytest_admin"]))
            ).all()
            for action in [
                "create_task",
                "ai_start_task",
                "ai_complete_task",
                "ai_fail_task",
                "admin_takeover_ai_task",
                "admin_claim_task",
                "resolve_task",
                "cancel_task",
            ]:
                assert action in actions, (action, actions)
            task_events = db.scalars(select(WorkTaskEvent.event_type)).all()
            for event_type in [
                "create_task",
                "ai_start_task",
                "ai_complete_task",
                "ai_fail_task",
                "admin_takeover_ai_task",
                "admin_claim_task",
                "resolve_task",
                "cancel_task",
            ]:
                assert event_type in task_events, (event_type, task_events)
        """,
    )
    _assert_ok(result)


def test_tasks_api_ai_failure_takeover_resolution_flow(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from fastapi.testclient import TestClient
        from sqlalchemy import select

        from bookflow_core.core.database import get_session
        from bookflow_core.core.security import create_access_token
        from bookflow_core.main import app
        from bookflow_core.models import AdminUser
        from bookflow_core.services.permission_service import admin_role

        with get_session() as db:
            admin = db.scalar(select(AdminUser).where(AdminUser.status == "active").order_by(AdminUser.id.asc()))
            assert admin is not None, "API smoke requires an active admin in the copied local database"
            token = create_access_token(admin.id, role=admin_role(admin), subject_type="admin", admin_code=admin.admin_code)
            admin_code = admin.admin_code

        client = TestClient(app)
        headers = {"Authorization": f"Bearer {token}"}

        status_resp = client.get("/ai/engine/status", headers=headers)
        assert status_resp.status_code == 200, status_resp.text
        status_data = status_resp.json()["data"]
        assert "api_key" not in status_data
        assert "apiKey" not in status_data

        create_resp = client.post(
            "/tasks",
            json={
                "title": "api ai smoke",
                "description": "temporary copied database smoke",
                "priority": "normal",
                "task_group": "review",
                "source_type": "ai",
                "auto_start_ai": True,
            },
            headers=headers,
        )
        assert create_resp.status_code == 200, create_resp.text
        created = create_resp.json()["data"]
        assert created["status"] == "ai_processing"
        assert created["claim_status"] == "ai_claimed"
        task_code = created["task_code"]

        fail_resp = client.post(
            f"/tasks/{task_code}/ai-fail",
            json={"run_id": 201, "error": "simulated failure", "confidence": 0.31},
            headers=headers,
        )
        assert fail_resp.status_code == 200, fail_resp.text
        failed = fail_resp.json()["data"]
        assert failed["status"] == "waiting_human"
        assert bool(failed["requires_human_confirmation"]) is True

        takeover_resp = client.post(
            f"/tasks/{task_code}/takeover",
            json={"admin_code": admin_code, "reason": "api smoke takeover"},
            headers=headers,
        )
        assert takeover_resp.status_code == 200, takeover_resp.text
        taken = takeover_resp.json()["data"]
        assert taken["status"] == "admin_processing"
        assert taken["claim_status"] == "admin_claimed"

        resolve_resp = client.post(
            f"/tasks/{task_code}/resolve",
            json={"resolution": "api smoke resolved"},
            headers=headers,
        )
        assert resolve_resp.status_code == 200, resolve_resp.text
        resolved = resolve_resp.json()["data"]
        assert resolved["status"] == "resolved"
        assert resolved["resolution"] == "api smoke resolved"
        """,
    )
    _assert_ok(result)
