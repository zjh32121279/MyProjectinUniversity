from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = ROOT / "backend" / "data" / "bookflow.db"


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _add_work_task_group(conn: sqlite3.Connection) -> dict:
    columns = _columns(conn, "work_tasks")
    changed = False
    if "task_group" not in columns:
        conn.execute("ALTER TABLE work_tasks ADD COLUMN task_group TEXT NOT NULL DEFAULT 'other'")
        changed = True

    conn.execute(
        """
        UPDATE work_tasks
        SET task_group = CASE
            WHEN COALESCE(title, '') || COALESCE(description, '') || COALESCE(task_type, '') || COALESCE(source_type, '')
                 GLOB '*借阅*' OR COALESCE(title, '') || COALESCE(description, '') || COALESCE(task_type, '') || COALESCE(source_type, '')
                 GLOB '*借书*' OR COALESCE(title, '') || COALESCE(description, '') || COALESCE(task_type, '') || COALESCE(source_type, '')
                 GLOB '*还书*' OR COALESCE(title, '') || COALESCE(description, '') || COALESCE(task_type, '') || COALESCE(source_type, '')
                 GLOB '*续借*' OR COALESCE(title, '') || COALESCE(description, '') || COALESCE(task_type, '') || COALESCE(source_type, '')
                 GLOB '*预约*' OR COALESCE(title, '') || COALESCE(description, '') || COALESCE(task_type, '') || COALESCE(source_type, '')
                 GLOB '*归还*' OR COALESCE(title, '') || COALESCE(description, '') || COALESCE(task_type, '') || COALESCE(source_type, '')
                 GLOB '*借出*' OR COALESCE(title, '') || COALESCE(description, '') || COALESCE(task_type, '') || COALESCE(source_type, '')
                 GLOB '*逾期*' OR COALESCE(title, '') || COALESCE(description, '') || COALESCE(task_type, '') || COALESCE(source_type, '')
                 GLOB '*超期*' OR COALESCE(title, '') || COALESCE(description, '') || COALESCE(task_type, '') || COALESCE(source_type, '')
                 GLOB '*到期*'
                THEN 'borrow'
            WHEN COALESCE(source_type, '') IN ('risk', 'security', 'ai_review')
                 OR COALESCE(task_type, '') IN ('risk', 'security', 'ai_review', 'exception')
                 OR COALESCE(title, '') || COALESCE(description, '') || COALESCE(task_type, '') || COALESCE(source_type, '')
                 GLOB '*异常*' OR COALESCE(title, '') || COALESCE(description, '') || COALESCE(task_type, '') || COALESCE(source_type, '')
                 GLOB '*风险*' OR COALESCE(title, '') || COALESCE(description, '') || COALESCE(task_type, '') || COALESCE(source_type, '')
                 GLOB '*复核*' OR COALESCE(title, '') || COALESCE(description, '') || COALESCE(task_type, '') || COALESCE(source_type, '')
                 GLOB '*检测*' OR COALESCE(title, '') || COALESCE(description, '') || COALESCE(task_type, '') || COALESCE(source_type, '')
                 GLOB '*错架*' OR COALESCE(title, '') || COALESCE(description, '') || COALESCE(task_type, '') || COALESCE(source_type, '')
                 GLOB '*错误*' OR COALESCE(title, '') || COALESCE(description, '') || COALESCE(task_type, '') || COALESCE(source_type, '')
                 GLOB '*安全*' OR COALESCE(title, '') || COALESCE(description, '') || COALESCE(task_type, '') || COALESCE(source_type, '')
                 GLOB '*告警*'
                THEN 'exception'
            WHEN COALESCE(source_type, '') = 'shelving' OR COALESCE(task_type, '') = 'shelving'
                THEN 'shelving'
            WHEN COALESCE(source_type, '') IN ('ai', 'ai_admin')
                THEN 'review'
            ELSE 'other'
        END
        WHERE task_group IS NULL OR task_group = '' OR task_group = 'other'
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS ix_work_tasks_task_group ON work_tasks(task_group)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_work_tasks_status_group ON work_tasks(status, task_group)")
    rows = conn.execute("SELECT task_group, COUNT(*) FROM work_tasks GROUP BY task_group ORDER BY task_group").fetchall()
    return {"changed": changed, "task_group_counts": dict(rows)}


def _add_indexes(conn: sqlite3.Connection) -> None:
    statements = [
        "CREATE INDEX IF NOT EXISTS ix_notifications_recipient_reader_id ON notifications(recipient_reader_id)",
        "CREATE INDEX IF NOT EXISTS ix_notifications_recipient_admin_id ON notifications(recipient_admin_id)",
        "CREATE INDEX IF NOT EXISTS ix_notifications_batch_id ON notifications(batch_id)",
        "CREATE INDEX IF NOT EXISTS ix_notifications_status_type ON notifications(status, notification_type)",
        "CREATE INDEX IF NOT EXISTS ix_notification_batches_batch_code ON notification_batches(batch_code)",
        "CREATE INDEX IF NOT EXISTS ix_ai_conversations_code ON ai_conversations(conversation_code)",
        "CREATE INDEX IF NOT EXISTS ix_ai_chat_messages_conversation_id ON ai_chat_messages(conversation_id)",
        "CREATE INDEX IF NOT EXISTS ix_search_events_keyword_created_at ON search_events(keyword, created_at)",
    ]
    for statement in statements:
        conn.execute(statement)


def migrate(db_path: Path = DEFAULT_DB) -> dict:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        task_result = _add_work_task_group(conn)
        _add_indexes(conn)
        conn.commit()
        return {
            "database": str(db_path),
            "work_tasks": task_result,
            "indexes_checked": True,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply non-destructive BookFlow Core schema compatibility migrations.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    print(json.dumps(migrate(args.db), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
