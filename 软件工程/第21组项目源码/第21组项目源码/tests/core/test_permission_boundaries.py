from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from bookflow_core.core.exceptions import BookFlowError
from bookflow_core.models import AdminUser
from bookflow_core.services.permission_service import ensure_permission, ensure_super_admin, permissions_for_role


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


def test_admin_permission_table_keeps_manual_operations_available() -> None:
    admin_permissions = set(permissions_for_role("admin"))
    super_permissions = set(permissions_for_role("super_admin"))

    assert "readers:write" in admin_permissions
    assert "tasks:read" in admin_permissions
    assert "tasks:write" in admin_permissions
    assert "settings:write" in admin_permissions
    assert "library:write" in admin_permissions
    assert {"settings:write", "library:write", "approvals:approve_l4"} <= super_permissions

    admin = AdminUser(admin_code="pytest_admin", status="active", is_super_admin=False)
    ensure_permission(admin, "readers:write")
    ensure_permission(admin, "tasks:read")
    ensure_permission(admin, "settings:write")
    ensure_permission(admin, "library:write")
    with pytest.raises(BookFlowError):
        ensure_super_admin(admin)


def test_admin_manual_reader_governance_and_settings_endpoints_remain_available(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from fastapi.testclient import TestClient
        from uuid import uuid4

        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.core.security import create_access_token
        from bookflow_core.main import app
        from bookflow_core.models import AdminUser, ReaderAccount, ReaderCredential
        from bookflow_core.core.security import hash_password
        from bookflow_core.services.permission_service import admin_role
        from bookflow_core.services.task_service import create_task

        ensure_schema()
        suffix = uuid4().hex[:8]

        try:
            with get_session() as db:
                regular_admin = AdminUser(
                    admin_code=f"PYTEST-ADMIN-{suffix}",
                    name="pytest regular admin",
                    email=f"regular-{suffix}@pytest.local",
                    status="active",
                    is_super_admin=False,
                )
                super_admin = AdminUser(
                    admin_code=f"PYTEST-SUPER-{suffix}",
                    name="pytest super admin",
                    email=f"super-{suffix}@pytest.local",
                    status="active",
                    is_super_admin=True,
                )
                reader = ReaderAccount(
                    reader_code=f"PYTEST-READER-{suffix}",
                    reader_type_code="adult",
                    reader_type_name="adult",
                    name="pytest reader",
                    status="active",
                    credit_score="100",
                    current_borrow_count=0,
                )
                db.add_all([regular_admin, super_admin, reader])
                db.flush()
                db.add(
                    ReaderCredential(
                        reader_id=reader.id,
                        login_name=reader.reader_code,
                        password_hash=hash_password("pytest123"),
                        status="active",
                    )
                )
                task = create_task(
                    db,
                    title="pytest permission task",
                    description="task detail must remain visible to normal admins",
                    priority="normal",
                    source_type="system",
                    task_group="review",
                    actor_id=regular_admin.admin_code,
                )
                db.commit()
                regular_token = create_access_token(
                    regular_admin.id,
                    role=admin_role(regular_admin),
                    subject_type="admin",
                    admin_code=regular_admin.admin_code,
                )
                super_token = create_access_token(
                    super_admin.id,
                    role=admin_role(super_admin),
                    subject_type="admin",
                    admin_code=super_admin.admin_code,
                )
                reader_code = reader.reader_code
                task_code = task.task_code

            client = TestClient(app)
            regular_headers = {"Authorization": f"Bearer {regular_token}"}
            super_headers = {"Authorization": f"Bearer {super_token}"}

            detail_resp = client.get(f"/tasks/{task_code}", headers=regular_headers)
            assert detail_resp.status_code == 200, detail_resp.text

            allowed_requests = [
                ("post", f"/readers/{reader_code}/suspend", {"reason": "pytest"}),
                ("post", f"/readers/{reader_code}/restore", {"reason": "pytest"}),
                ("post", f"/readers/{reader_code}/reset-password", {"new_password": "pytest123", "confirm_password": "pytest123"}),
                ("put", "/library/settings", {"settings": {}}),
            ]
            for method, path, payload in allowed_requests:
                response = getattr(client, method)(path, json=payload, headers=regular_headers)
                assert response.status_code == 200, (path, response.status_code, response.text)

            allowed_resp = client.post(f"/readers/{reader_code}/suspend", json={"reason": "pytest super"}, headers=super_headers)
            assert allowed_resp.status_code == 200, allowed_resp.text
            assert allowed_resp.json()["data"]["status"] == "suspended"

        finally:
            # 清理测试数据，防止污染数据库
            from sqlalchemy import text
            with get_session() as db:
                db.execute(text("PRAGMA foreign_keys=OFF"))
                reader_filter = "SELECT id FROM reader_accounts WHERE reader_code LIKE 'PYTEST-READER-%'"
                db.execute(text(f"DELETE FROM notification_deliveries WHERE recipient_type = 'reader' AND recipient_id IN ({reader_filter})"))
                db.execute(text(f"DELETE FROM circulation_service_requests WHERE reader_id IN ({reader_filter})"))
                db.execute(text(f"DELETE FROM reader_credentials WHERE reader_id IN ({reader_filter}) OR login_name LIKE 'PYTEST-READER-%'"))
                db.execute(text(f"DELETE FROM reader_notification_settings WHERE reader_id IN ({reader_filter})"))
                db.execute(text(f"DELETE FROM reader_preferences WHERE reader_id IN ({reader_filter})"))
                db.execute(text(f"DELETE FROM reader_stats WHERE reader_id IN ({reader_filter})"))
                db.execute(text("DELETE FROM reader_status_events WHERE reader_id IN (SELECT id FROM reader_accounts WHERE reader_code LIKE 'PYTEST-READER-%')"))
                db.execute(text("DELETE FROM reader_credit_events WHERE reader_id IN (SELECT id FROM reader_accounts WHERE reader_code LIKE 'PYTEST-READER-%')"))
                db.execute(text("DELETE FROM reader_accounts WHERE reader_code LIKE 'PYTEST-%'"))
                db.execute(text("DELETE FROM work_task_events WHERE task_id IN (SELECT id FROM work_tasks WHERE title LIKE 'pytest %')"))
                db.execute(text("DELETE FROM work_tasks WHERE title LIKE 'pytest %' OR task_code LIKE 'PYTEST-%'"))
                db.execute(text("DELETE FROM admin_login_events WHERE admin_code LIKE 'PYTEST-%'"))
                db.execute(text("DELETE FROM admin_user_roles WHERE admin_id IN (SELECT id FROM admin_users WHERE admin_code LIKE 'PYTEST-%')"))
                db.execute(text("DELETE FROM admin_users WHERE admin_code LIKE 'PYTEST-%'"))
                db.commit()
                db.execute(text("PRAGMA foreign_keys=ON"))
        """,
    )
    assert result.returncode == 0, result.stdout + result.stderr
