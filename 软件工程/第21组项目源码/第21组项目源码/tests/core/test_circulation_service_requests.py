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
    db_path = tmp_path / "bookflow_circulation_request_test.db"
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
        timeout=60,
        check=False,
    )


def test_borrow_and_return_service_requests_keep_staff_confirmation_boundary(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from sqlalchemy import select

        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import Book, BookCopy, CirculationServiceRequest, Loan, ReaderAccount, WorkTask
        from bookflow_core.services.circulation_request_service import (
            complete_return_request,
            create_borrow_request,
            create_renew_request,
            create_reservation_request,
            create_return_request,
            redeem_borrow_request,
        )
        from bookflow_core.services.task_service import list_tasks

        ensure_schema()
        with get_session() as db:
            reader = db.scalar(select(ReaderAccount).where(ReaderAccount.status == "active").order_by(ReaderAccount.id))
            assert reader is not None
            book = Book(book_code="PYTEST-SVC-BOOK", title="pytest service request book", circulation_type="normal", status="active")
            db.add(book)
            db.flush()
            copy = BookCopy(book_id=book.id, copy_code="PYTEST-SVC-COPY", copy_status="available", can_borrow_outside_library=True)
            db.add(copy)
            db.flush()

            request = create_borrow_request(db, reader, copy_id=copy.id, source_actor_id=reader.reader_code, commit=False)
            assert request.status == "ready"
            assert request.voucher_code
            assert request.task_code
            locked_copy = db.get(BookCopy, request.copy_id)
            assert locked_copy.copy_status == "reserved"
            task = db.scalar(select(WorkTask).where(WorkTask.task_code == request.task_code))
            assert task is not None
            assert task.related_entity_type == "circulation_service_request"
            assert "借书" in task.title
            reader_ops = list_tasks(db, task_group="reader_ops", limit=50)
            assert any(item.task_code == task.task_code for item in reader_ops["items"])

            completed = redeem_borrow_request(db, request.voucher_code, admin_code="pytest_admin", commit=False)
            assert completed.status == "completed"
            assert completed.loan_id
            borrowed_copy = db.get(BookCopy, completed.copy_id)
            assert borrowed_copy.copy_status == "borrowed"
            loan = db.get(Loan, completed.loan_id)
            assert loan is not None
            assert loan.status == "active"

            renew_request = create_renew_request(db, reader, loan_id=loan.id, source_actor_id=reader.reader_code, commit=False)
            assert renew_request.request_type == "renew"
            assert renew_request.status == "completed"
            assert renew_request.loan_id == loan.id
            assert "new_due_at" in renew_request.result_json

            reservation_book = Book(book_code="PYTEST-SVC-RES-BOOK", title="pytest service reservation book", circulation_type="normal", status="active")
            db.add(reservation_book)
            db.flush()
            reservation_request = create_reservation_request(db, reader, book_id=reservation_book.id, source_actor_id=reader.reader_code, commit=False)
            assert reservation_request.request_type == "reservation"
            assert reservation_request.status == "completed"
            assert reservation_request.reservation_id
            assert reservation_request.reservation_code

            return_request = create_return_request(db, reader, loan_id=loan.id, source_actor_id=reader.reader_code, commit=False)
            assert return_request.status == "ready"
            duplicate_return_request = create_return_request(db, reader, loan_id=loan.id, source_actor_id=reader.reader_code, commit=False)
            assert duplicate_return_request.id == return_request.id
            assert duplicate_return_request.request_code == return_request.request_code
            returned = complete_return_request(db, return_request.request_code, admin_code="pytest_admin", commit=False)
            assert returned.status == "completed"
            db.flush()
            loan_after = db.get(Loan, loan.id)
            assert loan_after.status == "returned"
            assert db.get(BookCopy, completed.copy_id).copy_status in {"available", "reserved"}

            rows = db.scalars(select(CirculationServiceRequest).order_by(CirculationServiceRequest.id)).all()
            assert len(rows) >= 2
            db.commit()
        """,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_reader_portal_can_create_return_request(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from datetime import timedelta

        from fastapi.testclient import TestClient
        from sqlalchemy import select

        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.core.security import create_access_token
        from bookflow_core.models import Book, BookCopy, CirculationServiceRequest, Loan, ReaderAccount
        from bookflow_core.main import app
        from bookflow_core.services.statistics_service import get_business_date

        ensure_schema()
        with get_session() as db:
            reader = db.scalar(select(ReaderAccount).where(ReaderAccount.status == "active").order_by(ReaderAccount.id))
            assert reader is not None
            book = Book(book_code="PYTEST-PORTAL-RETURN-BOOK", title="pytest portal return book", circulation_type="normal", status="active")
            db.add(book)
            db.flush()
            copy = BookCopy(book_id=book.id, copy_code="PYTEST-PORTAL-RETURN-COPY", copy_status="borrowed", can_borrow_outside_library=True)
            db.add(copy)
            db.flush()
            today = get_business_date(db)
            loan = Loan(
                loan_code="PYTEST-PORTAL-RETURN-LOAN",
                reader_id=reader.id,
                book_id=book.id,
                copy_id=copy.id,
                borrowed_at=today,
                due_at=today + timedelta(days=14),
                status="active",
                renewal_count=0,
            )
            db.add(loan)
            db.commit()
            db.refresh(loan)
            loan_id = loan.id
            reader_id = reader.id
            token = create_access_token(reader.id, role="reader", subject_type="reader", reader_code=reader.reader_code)

        client = TestClient(app)
        first = client.post(f"/reader/borrows/{loan_id}/return", headers={"Authorization": f"Bearer {token}"})
        assert first.status_code == 200, first.text
        first_data = first.json()["data"]
        assert first_data["status"] == "ready"
        assert first_data["voucher_code"]

        second = client.post(f"/reader/borrows/{loan_id}/return", headers={"Authorization": f"Bearer {token}"})
        assert second.status_code == 200, second.text
        assert second.json()["data"]["request_code"] == first_data["request_code"]

        with get_session() as db:
            rows = db.scalars(
                select(CirculationServiceRequest).where(
                    CirculationServiceRequest.loan_id == loan_id,
                    CirculationServiceRequest.request_type == "return",
                )
            ).all()
            assert len(rows) == 1
            assert rows[0].source_type == "reader_portal"
            assert rows[0].reader_id == reader_id
        """,
    )
    assert result.returncode == 0, result.stdout + result.stderr
