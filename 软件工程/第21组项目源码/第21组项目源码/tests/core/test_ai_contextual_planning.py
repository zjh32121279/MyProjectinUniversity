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
    db_path = tmp_path / "bookflow_ai_contextual_planning.db"
    shutil.copy2(SOURCE_DB, db_path)
    env = os.environ.copy()
    env["BOOKFLOW_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env["BOOKFLOW_AI_KERNEL_WORKER_ENABLED"] = "false"
    env["PYTHONPATH"] = str(BACKEND) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-B", "-c", textwrap.dedent(script)],
        cwd=BACKEND,
        env=env,
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )


def test_admin_ai_planning_uses_standalone_request_for_contextual_tool_arguments(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from bookflow_core.ai.chat.chat_service import chat
        from bookflow_core.ai.chat.conversation_memory import save_message_pair
        from bookflow_core.core.database import ensure_schema, get_session

        STANDALONE = "Find more catalog items about renewable energy and include availability"

        class FakeAdminClient:
            def __init__(self):
                self.calls = 0

            def require_ready(self):
                return None

            def complete_json(self, *, messages, temperature=0):
                self.calls += 1
                if self.calls == 1:
                    assert any("standalone_request" in str(item.get("content", "")) for item in messages)
                    assert any(item.get("role") == "user" and "renewable energy" in item.get("content", "") for item in messages)
                    return {
                        "intent": "tool_call",
                        "standalone_request": STANDALONE,
                        "tool_calls": [
                            {
                                "tool_name": "ai_search_books",
                                "arguments": {"limit": 3},
                                "reason": "The follow-up needs live catalog data resolved from chat history.",
                            }
                        ],
                        "patrol": None,
                        "reply": "",
                        "llm_summary": "resolved contextual catalog follow-up",
                        "model_name": "fake-admin-model",
                    }
                return {"reply": "Contextual catalog search completed."}

        ensure_schema()
        with get_session() as db:
            conversation_id = "PYTEST-CONTEXT-ADMIN"
            save_message_pair(
                db,
                conversation_id=conversation_id,
                user_text="Find books about renewable energy",
                assistant_text="I found a few catalog matches.",
            )
            db.commit()

            response = chat(
                db,
                conversation_id=conversation_id,
                text="What about more, and check availability too?",
                actor_id="pytest_admin",
                llm_client=FakeAdminClient(),
            )
            assert response["reply"] == "Contextual catalog search completed."
            assert response["tool_results"][0]["arguments"]["keyword"] == STANDALONE
            assert response["tool_results"][0]["reason"].startswith("The follow-up")
        """,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_reader_ai_planning_uses_chat_messages_and_standalone_request_fallback(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        import json
        from sqlalchemy import select

        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import ReaderAccount, WorkTask
        import bookflow_core.services.reader_ai_service as reader_ai_service

        STANDALONE = "Find additional catalog items about machine learning and show availability"

        class FakeReaderClient:
            def __init__(self, *args, **kwargs):
                self.calls = 0

            def require_ready(self):
                return None

            def complete_json(self, *, messages, temperature=0.1):
                self.calls += 1
                if self.calls == 1:
                    assert any("standalone_request" in str(item.get("content", "")) for item in messages)
                    assert any(item.get("role") == "user" and "machine learning" in item.get("content", "") for item in messages)
                    return {
                        "intent": "tool_call",
                        "standalone_request": STANDALONE,
                        "tool_calls": [
                            {
                                "tool_name": "ai_search_books",
                                "arguments": {"limit": 4},
                                "reason": "Resolve a contextual reader catalog follow-up.",
                            }
                        ],
                        "reply": "",
                        "llm_summary": "reader contextual catalog follow-up",
                        "model_name": "fake-reader-model",
                    }
                return {"reply": "Reader contextual catalog search completed."}

        reader_ai_service.OpenAICompatibleClient = FakeReaderClient

        ensure_schema()
        with get_session() as db:
            reader = db.scalar(select(ReaderAccount).order_by(ReaderAccount.id.asc()))
            assert reader is not None
            response = reader_ai_service.reader_ai_chat(
                db,
                reader,
                message="more, and are they available?",
                history=[
                    {"role": "user", "content": "Find books about machine learning"},
                    {"role": "assistant", "content": "I found several catalog items."},
                ],
            )
            assert response["answer"] == "Reader contextual catalog search completed."
            task = db.scalar(select(WorkTask).where(WorkTask.task_code == response["task_code"]))
            assert task is not None
            payload = json.loads(task.source_payload_json)
            assert payload["llm_plan"]["standalone_request"] == STANDALONE
            assert payload["tool_calls"][0]["arguments"]["keyword"] == STANDALONE
            assert payload["tool_calls"][0]["reason"].startswith("Resolve")
        """,
    )
    assert result.returncode == 0, result.stdout + result.stderr
