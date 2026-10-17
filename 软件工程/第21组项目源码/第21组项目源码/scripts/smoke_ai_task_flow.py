from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SOURCE_DB = BACKEND / "data" / "bookflow.db"


def _prepare_database() -> Path:
    source = Path(os.getenv("BOOKFLOW_SMOKE_SOURCE_DATABASE", str(SOURCE_DB))).resolve()
    temp_dir = Path(tempfile.mkdtemp(prefix="bookflow_smoke_"))
    copied = temp_dir / "bookflow_smoke.db"
    shutil.copy2(source, copied)
    os.environ["BOOKFLOW_DATABASE_URL"] = f"sqlite:///{copied.as_posix()}"
    return copied


def main() -> int:
    sys.path.insert(0, str(BACKEND))
    db_path = _prepare_database()

    from bookflow_core.core.database import get_session
    from bookflow_core.core.security import create_access_token
    from bookflow_core.main import app
    from bookflow_core.models import AdminUser
    from bookflow_core.services.permission_service import admin_role

    with get_session() as db:
        admin = db.scalar(select(AdminUser).where(AdminUser.status == "active").order_by(AdminUser.id.asc()))
        if admin is None:
            raise RuntimeError("No active admin found for API smoke.")
        token = create_access_token(admin.id, role=admin_role(admin), subject_type="admin", admin_code=admin.admin_code)
        admin_code = admin.admin_code

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    status_resp = client.get("/ai/engine/status", headers=headers)
    status_resp.raise_for_status()
    status_data = status_resp.json()["data"]
    if "api_key" in status_data or "apiKey" in status_data:
        raise AssertionError("AI engine status must not expose API key values.")

    create_resp = client.post(
        "/tasks",
        json={
            "title": "manual api ai smoke",
            "description": "temporary copied database smoke",
            "priority": "normal",
            "task_group": "review",
            "source_type": "ai",
            "auto_start_ai": True,
        },
        headers=headers,
    )
    create_resp.raise_for_status()
    created = create_resp.json()["data"]
    if created["status"] != "ai_processing":
        raise AssertionError(created)

    task_code = created["task_code"]
    fail_resp = client.post(
        f"/tasks/{task_code}/ai-fail",
        json={"run_id": 301, "error": "simulated failure", "confidence": 0.31},
        headers=headers,
    )
    fail_resp.raise_for_status()
    failed = fail_resp.json()["data"]
    if failed["status"] != "waiting_human":
        raise AssertionError(failed)

    takeover_resp = client.post(
        f"/tasks/{task_code}/takeover",
        json={"admin_code": admin_code, "reason": "manual smoke takeover"},
        headers=headers,
    )
    takeover_resp.raise_for_status()
    taken = takeover_resp.json()["data"]
    if taken["status"] != "admin_processing":
        raise AssertionError(taken)

    resolve_resp = client.post(
        f"/tasks/{task_code}/resolve",
        json={"resolution": "manual smoke resolved"},
        headers=headers,
    )
    resolve_resp.raise_for_status()
    resolved = resolve_resp.json()["data"]
    if resolved["status"] != "resolved":
        raise AssertionError(resolved)

    print(
        {
            "database": str(db_path),
            "task_code": task_code,
            "flow": [created["status"], failed["status"], taken["status"], resolved["status"]],
            "engine_connected": status_data.get("connected"),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
