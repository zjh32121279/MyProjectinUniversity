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
    db_path = tmp_path / "bookflow_reader_ai_test.db"
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


def test_reader_ai_chat_uses_llm_plan_kernel_and_server_reader_scope(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        import json
        from sqlalchemy import select

        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import ReaderAccount, WorkTask
        import bookflow_core.services.reader_ai_service as reader_ai_service

        class FakeReaderClient:
            def __init__(self, *args, **kwargs):
                self.calls = 0

            def require_ready(self):
                return None

            def complete_json(self, *, messages, temperature=0.1):
                self.calls += 1
                if self.calls == 1:
                    return {
                        "intent": "tool_call",
                        "tool_calls": [
                            {
                                "tool_name": "ai_get_loans",
                                "arguments": {"reader_id": 999999, "limit": 2},
                                "reason": "inspect current reader loans",
                            }
                        ],
                        "reply": "",
                        "llm_summary": "reader asks for own loans",
                        "model_name": "fake-reader-model",
                    }
                return {"reply": "这是根据实时借阅记录生成的回复。"}

        reader_ai_service.OpenAICompatibleClient = FakeReaderClient

        ensure_schema()
        with get_session() as db:
            reader = db.scalar(select(ReaderAccount).order_by(ReaderAccount.id.asc()))
            assert reader is not None

            response = reader_ai_service.reader_ai_chat(db, reader, message="查一下我的借阅")
            assert response["answer"] == "这是根据实时借阅记录生成的回复。"
            assert response["kernel_run_id"]

            task = db.scalar(select(WorkTask).where(WorkTask.task_code == response["task_code"]))
            assert task is not None
            assert task.status == "resolved"

            payload = json.loads(task.source_payload_json)
            assert payload["llm_plan"]["intent"] == "tool_call"
            assert payload["tool_calls"][0]["tool_name"] == "ai_get_loans"
            assert payload["tool_calls"][0]["arguments"]["reader_id"] == reader.id
            assert payload["final_answer"] == response["answer"]
        """,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_reader_ai_chat_can_create_borrow_request_without_trusting_llm_reader_scope(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        import json
        from sqlalchemy import select

        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import Book, BookCopy, CirculationServiceRequest, ReaderAccount, WorkTask
        import bookflow_core.services.reader_ai_service as reader_ai_service

        COPY_ID = None

        class FakeReaderClient:
            def __init__(self, *args, **kwargs):
                self.calls = 0

            def require_ready(self):
                return None

            def complete_json(self, *, messages, temperature=0.1):
                self.calls += 1
                if self.calls == 1:
                    return {
                        "intent": "tool_call",
                        "tool_calls": [
                            {
                                "tool_name": "ai_reader_create_borrow_request",
                                "arguments": {"reader_code": "MALICIOUS-READER", "copy_id": COPY_ID},
                                "reason": "reader asks AI to prepare a borrow request",
                            }
                        ],
                        "reply": "",
                        "llm_summary": "reader wants to borrow an available copy",
                        "model_name": "fake-reader-model",
                    }
                return {"reply": "已为你生成借书办理请求，请带凭证码到馆员处确认。"}

        reader_ai_service.OpenAICompatibleClient = FakeReaderClient

        ensure_schema()
        with get_session() as db:
            reader = db.scalar(select(ReaderAccount).where(ReaderAccount.status == "active").order_by(ReaderAccount.id.asc()))
            assert reader is not None
            book = Book(book_code="PYTEST-READER-AI-BOOK", title="pytest reader ai book", circulation_type="normal", status="active")
            db.add(book)
            db.flush()
            copy = BookCopy(book_id=book.id, copy_code="PYTEST-READER-AI-COPY", copy_status="available", can_borrow_outside_library=True)
            db.add(copy)
            db.flush()
            COPY_ID = copy.id

            response = reader_ai_service.reader_ai_chat(db, reader, message="帮我借这本书")
            assert response["answer"] == "已为你生成借书办理请求，请带凭证码到馆员处确认。"
            assert response["kernel_run_id"]
            assert response["actions"]
            action = response["actions"][0]
            assert action["kind"] == "circulation_service_request"
            assert action["request_type"] == "borrow"
            assert action["status"] == "ready"
            assert any(item["label"] == "凭证码" and item["value"] for item in action["fields"])
            assert response["service_requests"][0]["request_type"] == "borrow"
            assert response["service_requests"][0]["reader_code"] == reader.reader_code

            parent_task = db.scalar(select(WorkTask).where(WorkTask.task_code == response["task_code"]))
            assert parent_task is not None
            assert parent_task.status == "resolved"
            payload = json.loads(parent_task.source_payload_json)
            tool_args = payload["tool_calls"][0]["arguments"]
            assert tool_args["reader_code"] == reader.reader_code
            assert tool_args["copy_id"] == COPY_ID
            assert payload["reader_actions"][0]["request_type"] == "borrow"

            request = db.scalar(
                select(CirculationServiceRequest)
                .where(CirculationServiceRequest.copy_id == COPY_ID)
                .order_by(CirculationServiceRequest.id.desc())
            )
            assert request is not None
            assert request.request_type == "borrow"
            assert request.status == "ready"
            assert request.reader_code == reader.reader_code
            assert request.source_type == "reader_ai"
            assert request.voucher_code
            locked_copy = db.get(BookCopy, COPY_ID)
            assert locked_copy.copy_status == "reserved"
        """,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_reader_ai_chat_can_create_return_request_without_trusting_llm_reader_scope(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from datetime import timedelta
        from sqlalchemy import select

        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import Book, BookCopy, CirculationServiceRequest, Loan, ReaderAccount
        from bookflow_core.services.statistics_service import get_business_date
        import bookflow_core.services.reader_ai_service as reader_ai_service

        LOAN_ID = None

        class FakeReaderClient:
            def __init__(self, *args, **kwargs):
                self.calls = 0

            def require_ready(self):
                return None

            def complete_json(self, *, messages, temperature=0.1):
                self.calls += 1
                if self.calls == 1:
                    return {
                        "intent": "tool_call",
                        "tool_calls": [
                            {
                                "tool_name": "ai_reader_create_return_request",
                                "arguments": {"reader_code": "MALICIOUS-READER", "loan_id": LOAN_ID},
                                "reason": "reader asks AI to create a return request",
                            }
                        ],
                        "reply": "",
                        "llm_summary": "reader wants to return a borrowed book",
                        "model_name": "fake-reader-model",
                    }
                return {"reply": "已为你生成还书办理请求，请带图书到服务台确认。"}

        reader_ai_service.OpenAICompatibleClient = FakeReaderClient

        ensure_schema()
        with get_session() as db:
            reader = db.scalar(select(ReaderAccount).where(ReaderAccount.status == "active").order_by(ReaderAccount.id.asc()))
            assert reader is not None
            book = Book(book_code="PYTEST-READER-AI-RETURN-BOOK", title="pytest reader ai return book", circulation_type="normal", status="active")
            db.add(book)
            db.flush()
            copy = BookCopy(book_id=book.id, copy_code="PYTEST-READER-AI-RETURN-COPY", copy_status="borrowed", can_borrow_outside_library=True)
            db.add(copy)
            db.flush()
            today = get_business_date(db)
            loan = Loan(
                loan_code="PYTEST-READER-AI-RETURN-LOAN",
                reader_id=reader.id,
                book_id=book.id,
                copy_id=copy.id,
                borrowed_at=today,
                due_at=today + timedelta(days=14),
                status="active",
                renewal_count=0,
            )
            db.add(loan)
            db.flush()
            LOAN_ID = loan.id

            response = reader_ai_service.reader_ai_chat(db, reader, message="我要还这本书")
            assert response["answer"] == "已为你生成还书办理请求，请带图书到服务台确认。"
            assert response["actions"]
            action = response["actions"][0]
            assert action["kind"] == "circulation_service_request"
            assert action["request_type"] == "return"
            assert action["status"] == "ready"
            assert response["service_requests"][0]["reader_code"] == reader.reader_code

            request = db.scalar(
                select(CirculationServiceRequest)
                .where(CirculationServiceRequest.loan_id == LOAN_ID)
                .order_by(CirculationServiceRequest.id.desc())
            )
            assert request is not None
            assert request.request_type == "return"
            assert request.status == "ready"
            assert request.reader_code == reader.reader_code
            assert request.source_type == "reader_ai"
            assert request.voucher_code
        """,
    )
    assert result.returncode == 0, result.stdout + result.stderr
