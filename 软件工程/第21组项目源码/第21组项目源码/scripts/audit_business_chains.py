from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SOURCE_DB = BACKEND / "data" / "bookflow.db"


def _prepare_temp_database() -> Path:
    temp = Path(tempfile.mkdtemp(prefix="bookflow_chain_")) / "bookflow_chain.db"
    shutil.copy2(Path(os.getenv("BOOKFLOW_CHAIN_SOURCE_DATABASE", str(SOURCE_DB))).resolve(), temp)
    os.environ["BOOKFLOW_DATABASE_URL"] = f"sqlite:///{temp.as_posix()}"
    return temp


def main() -> int:
    sys.path.insert(0, str(BACKEND))
    db_path = _prepare_temp_database()

    from bookflow_core.core.database import get_session
    from bookflow_core.core.security import create_access_token
    from bookflow_core.main import app
    from bookflow_core.models import AdminUser, Book, BookCopy, Loan, ReaderAccount
    from bookflow_core.services.circulation_service import _rule_for
    from bookflow_core.services.permission_service import admin_role

    results: list[dict] = []

    def add(name: str, ok: bool, detail=None) -> None:
        results.append({"name": name, "ok": bool(ok), "detail": detail})

    with get_session() as db:
        admin = db.scalar(select(AdminUser).where(AdminUser.admin_code == "A02-001"))
        super_admin = db.scalar(select(AdminUser).where(AdminUser.admin_code == "A01-001"))
        if not admin or not super_admin:
            raise RuntimeError("Business-chain audit requires A02-001 and A01-001 test accounts.")
        admin_token = create_access_token(admin.id, role=admin_role(admin), subject_type="admin", admin_code=admin.admin_code)
        super_token = create_access_token(super_admin.id, role=admin_role(super_admin), subject_type="admin", admin_code=super_admin.admin_code)

        combos = db.execute(
            select(ReaderAccount.reader_type_code, ReaderAccount.reader_type_name, Book.circulation_type)
            .select_from(ReaderAccount)
            .join(Loan, Loan.reader_id == ReaderAccount.id)
            .join(Book, Book.id == Loan.book_id)
            .group_by(ReaderAccount.reader_type_code, ReaderAccount.reader_type_name, Book.circulation_type)
        ).all()
        failed_rules = []
        for reader_type_code, reader_type_name, circulation_type in combos:
            try:
                _rule_for(db, reader_type_code, circulation_type)
            except Exception as exc:  # pragma: no cover - diagnostic path
                failed_rules.append((reader_type_code, reader_type_name, circulation_type, str(exc)))
        add("circulation rule normalization covers existing loan data", not failed_rules, failed_rules[:5])

        test_copy = None
        reader = None
        active_readers = db.scalars(select(ReaderAccount).where(ReaderAccount.status == "active").order_by(ReaderAccount.id.asc()).limit(500)).all()
        available_copies = db.scalars(select(BookCopy).where(BookCopy.copy_status == "available").order_by(BookCopy.id.asc()).limit(800)).all()
        for candidate_reader in active_readers:
            active_count = db.scalar(select(func.count(Loan.id)).where(Loan.reader_id == candidate_reader.id, Loan.status.in_(["active", "overdue"]))) or 0
            for copy in available_copies:
                book = db.get(Book, copy.book_id)
                try:
                    rule = _rule_for(db, candidate_reader.reader_type_code, book.circulation_type)
                except Exception:
                    continue
                if active_count < rule.max_borrow_count and rule.max_renewals > 0:
                    reader = candidate_reader
                    test_copy = copy
                    break
            if test_copy is not None:
                break
        add("found a copy suitable for borrow-renew-return audit", test_copy is not None, {"reader_code": getattr(reader, "reader_code", None), "copy_code": getattr(test_copy, "copy_code", None)})

    client = TestClient(app)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    super_headers = {"Authorization": f"Bearer {super_token}"}

    if test_copy is not None:
        response = client.post("/circulation/borrow", headers=admin_headers, json={"reader_code": reader.reader_code, "copy_code": test_copy.copy_code})
        add("borrow available copy", response.status_code == 200 and response.json().get("success") is True, response.text[:300])
        loan_id = (response.json().get("data") or {}).get("loan_id") if response.status_code == 200 else None
        if loan_id:
            response = client.post("/circulation/renew", headers=admin_headers, json={"loan_id": loan_id})
            add("renew borrowed loan", response.status_code == 200 and response.json().get("success") is True, response.text[:300])
            response = client.post("/circulation/return", headers=admin_headers, json={"copy_code": test_copy.copy_code})
            add(
                "return borrowed copy",
                response.status_code == 200 and response.json().get("success") is True and (response.json().get("data") or {}).get("copy_status") in {"available", "reserved"},
                response.text[:300],
            )

    with get_session() as db:
        reservation_reader = db.scalar(select(ReaderAccount).where(ReaderAccount.status == "active").order_by(ReaderAccount.id.desc()))
        reservation_copy = db.scalar(select(BookCopy).where(BookCopy.copy_status == "available").order_by(BookCopy.id.asc()))
        reservation_book = db.get(Book, reservation_copy.book_id)

    response = client.post("/circulation/reservations", headers=admin_headers, json={"reader_code": reservation_reader.reader_code, "book_code": reservation_book.book_code})
    reservation_data = response.json().get("data") if response.status_code == 200 else {}
    add("create ready-for-pickup reservation", response.status_code == 200 and reservation_data.get("status") == "ready_for_pickup", response.text[:300])
    reservation_id = reservation_data.get("reservation_id")

    duplicate = client.post("/circulation/reservations", headers=admin_headers, json={"reader_code": reservation_reader.reader_code, "book_code": reservation_book.book_code})
    add("duplicate active reservation is blocked", duplicate.status_code == 400, duplicate.text[:300])

    if reservation_id:
        pending_response = client.get(
            "/circulation/pending-requests",
            headers=admin_headers,
            params={"reader_id": reservation_reader.id, "status": "ready", "limit": 20},
        )
        pending_items = (pending_response.json().get("data") or {}).get("items", []) if pending_response.status_code == 200 else []
        request_row = next((item for item in pending_items if item.get("reservation_id") == reservation_id), None)
        if request_row:
            response = client.post(
                f"/circulation/requests/{request_row['request_code']}/borrow/complete",
                headers=admin_headers,
                json={"voucher_code": request_row.get("voucher_code")},
            )
            add("fulfill ready reservation via service request", response.status_code == 200 and response.json().get("success") is True, response.text[:300])
        else:
            add("fulfill ready reservation via service request", False, pending_response.text[:300])

    rules = client.get("/super-admin/ai-rules", headers=super_headers, params={"limit": 200}).json()["data"]["items"]
    rule_id = next((item["id"] for item in rules if str(item.get("id", "")).startswith(("ai-", "system-"))), None)
    response = client.post(f"/super-admin/ai-rules/{rule_id}/toggle", headers=super_headers, json={"enabled": False}) if rule_id else None
    add("toggle a governance rule", response is not None and response.status_code == 200, response.text[:300] if response else "no ai/system rule")

    response = client.post("/super-admin/audit-security/export", headers=super_headers, json={"template_name": "business-chain audit", "export_type": "audit_summary", "filter": {"limit": 10}})
    add("create audit export job", response.status_code == 200 and response.json().get("success") is True, response.text[:300])

    output = {"database": str(db_path), "summary": dict(Counter(item["ok"] for item in results)), "results": results}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if all(item["ok"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
