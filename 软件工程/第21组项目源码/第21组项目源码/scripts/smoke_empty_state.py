from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SOURCE_DB = BACKEND / "data" / "bookflow.db"

OPERATIONAL_TABLES = [
    "action_snapshots",
    "agent_steps",
    "agent_runs",
    "ai_approval_requests",
    "ai_chat_messages",
    "ai_conversations",
    "ai_execution_ledger",
    "ai_memory_items",
    "ai_observations",
    "ai_rule_execution_logs",
    "ai_rule_versions",
    "ai_rules",
    "ai_task_checkpoints",
    "ai_token_usage",
    "audit_events",
    "admin_login_events",
    "book_subject_relations",
    "book_subject_tags",
    "book_circulation_stats",
    "book_copies",
    "books",
    "book_subcategories",
    "book_categories",
    "copy_location_events",
    "copy_status_events",
    "daily_operation_metrics",
    "data_import_errors",
    "data_import_batches",
    "export_jobs",
    "library_profiles",
    "library_zones",
    "loan_events",
    "loans",
    "circulation_service_requests",
    "notification_deliveries",
    "notification_messages",
    "notification_batches",
    "notifications",
    "overdue_cases",
    "reader_credentials",
    "reader_credit_events",
    "reader_login_events",
    "reader_notification_settings",
    "reader_preferences",
    "reader_stats",
    "reader_status_events",
    "reader_verification_codes",
    "reader_accounts",
    "reservation_events",
    "reservations",
    "review_items",
    "risk_events",
    "risk_warnings",
    "search_events",
    "shelf_positions",
    "shelves",
    "work_task_events",
    "work_tasks",
]


@dataclass
class EmptyReader:
    id: int = 9_999_999
    reader_code: str = "EMPTY-READER"
    name: str = "Empty State Reader"
    reader_type_code: str = "adult"
    reader_type_name: str = "adult"
    status: str = "active"
    phone_masked: str = ""
    email: str = ""
    credit_score: int = 100
    borrow_suspended_until: str = ""


def _copy_empty_database() -> Path:
    source = Path(os.getenv("BOOKFLOW_SMOKE_SOURCE_DATABASE", str(SOURCE_DB))).resolve()
    temp_dir = Path(tempfile.mkdtemp(prefix="bookflow_empty_"))
    copied = temp_dir / "bookflow_empty.db"
    shutil.copy2(source, copied)
    with sqlite3.connect(copied) as conn:
        existing = {row[0] for row in conn.execute("select name from sqlite_master where type='table'")}
        conn.execute("PRAGMA foreign_keys=OFF")
        for table in OPERATIONAL_TABLES:
            if table in existing:
                conn.execute(f"DELETE FROM {table}")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()
    os.environ["BOOKFLOW_DATABASE_URL"] = f"sqlite:///{copied.as_posix()}"
    return copied


def _payload(response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("success") is True, body
    return body.get("data")


def _assert_empty_page(data: dict[str, Any]) -> None:
    assert data.get("items") == [], data
    assert int(data.get("total", 0)) == 0, data


def main() -> int:
    sys.path.insert(0, str(BACKEND))
    db_path = _copy_empty_database()

    from bookflow_core.api.deps import require_reader
    from bookflow_core.core.database import get_session
    from bookflow_core.core.security import create_access_token
    from bookflow_core.main import app
    from bookflow_core.models import AdminUser
    from bookflow_core.services.permission_service import admin_role

    with get_session() as db:
        admin = db.scalar(select(AdminUser).where(AdminUser.status == "active").order_by(AdminUser.id.asc()))
        super_admin = db.scalar(
            select(AdminUser).where(AdminUser.status == "active", AdminUser.is_super_admin == True).order_by(AdminUser.id.asc())
        )
        if admin is None:
            raise RuntimeError("Empty-state smoke requires an active admin identity for authentication.")
        if super_admin is None:
            raise RuntimeError("Empty-state smoke requires an active super_admin identity for governance APIs.")
        admin_token = create_access_token(admin.id, role=admin_role(admin), subject_type="admin", admin_code=admin.admin_code)
        super_token = create_access_token(
            super_admin.id,
            role=admin_role(super_admin),
            subject_type="admin",
            admin_code=super_admin.admin_code,
        )

    app.dependency_overrides[require_reader] = lambda: EmptyReader()
    client = TestClient(app)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    super_headers = {"Authorization": f"Bearer {super_token}"}

    checks: list[str] = []

    _assert_empty_page(_payload(client.get("/public/catalog/books", params={"limit": 5})))
    checks.append("public catalog books")
    assert _payload(client.get("/public/catalog/categories")) == []
    checks.append("public categories")
    _assert_empty_page(_payload(client.get("/public/locations/zones")))
    checks.append("public zones")
    not_found = client.get("/public/catalog/books/999999")
    assert not_found.status_code in {404, 422}, not_found.text
    checks.append("public missing detail")

    _assert_empty_page(_payload(client.get("/reader/borrows")))
    _assert_empty_page(_payload(client.get("/reader/reservations")))
    _assert_empty_page(_payload(client.get("/reader/notifications")))
    reader_home = _payload(client.get("/reader/home"))
    assert reader_home["recommendations"] == []
    assert reader_home["recent_notifications"] == []
    assert reader_home["borrow_summary"]["current_count"] == 0
    checks.append("reader empty pages")

    _assert_empty_page(_payload(client.get("/catalog/books")))
    _assert_empty_page(_payload(client.get("/catalog/copies")))
    _assert_empty_page(_payload(client.get("/readers")))
    _assert_empty_page(_payload(client.get("/notifications", headers=admin_headers)))
    _assert_empty_page(_payload(client.get("/tasks")))
    dashboard = _payload(client.get("/dashboard/admin"))
    for key in [
        "today_borrow_count",
        "today_return_count",
        "overdue_count",
        "pending_task_count",
        "collection_database_total",
        "available_copy_database_count",
        "borrowed_copy_count",
        "reserved_copy_count",
    ]:
        assert int(dashboard.get(key, 0)) == 0, (key, dashboard.get(key))
    checks.append("admin empty pages")

    _assert_empty_page(_payload(client.get("/super-admin/audit-security/events", headers=super_headers)))
    checks.append("ai and governance empty pages")

    app.dependency_overrides.clear()
    print({"database": str(db_path), "checks": checks, "status": "passed"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
