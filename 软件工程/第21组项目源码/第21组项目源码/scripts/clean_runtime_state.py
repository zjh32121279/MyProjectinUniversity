from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "backend" / "data" / "bookflow.db"

RUNTIME_TABLES = [
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
    "ai_task_checkpoints",
    "ai_token_usage",
    "audit_events",
    "admin_login_events",
    "circulation_service_requests",
    "copy_location_events",
    "copy_status_events",
    "daily_operation_metrics",
    "data_import_errors",
    "data_import_batches",
    "export_jobs",
    "loan_events",
    "loans",
    "notification_deliveries",
    "notification_messages",
    "notification_batches",
    "notifications",
    "overdue_cases",
    "reader_credit_events",
    "reader_login_events",
    "reader_status_events",
    "reader_verification_codes",
    "reservation_events",
    "reservations",
    "review_items",
    "risk_events",
    "risk_warnings",
    "search_events",
    "work_task_events",
    "work_tasks",
]


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] or 0)


def clean(db_path: Path = DEFAULT_DB, *, backup: bool = True) -> dict:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    backup_path = None
    if backup:
        backup_path = db_path.with_name(f"{db_path.stem}.backup_before_runtime_clean_{datetime.now().strftime('%Y%m%d_%H%M%S')}{db_path.suffix}")
        shutil.copy2(db_path, backup_path)

    conn = sqlite3.connect(db_path)
    try:
        existing = _tables(conn)
        deleted: dict[str, int] = {}
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN")
        for table in RUNTIME_TABLES:
            if table not in existing:
                continue
            deleted[table] = _count(conn, table)
            conn.execute(f"DELETE FROM {table}")

        if "book_copies" in existing:
            conn.execute(
                """
                UPDATE book_copies
                SET copy_status='available',
                    status_code='S01',
                    status_name='在馆可借',
                    updated_at=CURRENT_TIMESTAMP
                """
            )
        if "reader_accounts" in existing:
            conn.execute(
                """
                UPDATE reader_accounts
                SET status='active',
                    current_borrow_count=0,
                    borrow_suspended_until='',
                    updated_at=CURRENT_TIMESTAMP
                """
            )
        if "reader_stats" in existing:
            conn.execute(
                """
                UPDATE reader_stats
                SET active_loans='0',
                    overdue_count=0,
                    total_borrow_count=0,
                    total_reservation_count=0,
                    last_borrowed_at=NULL,
                    computed_at=CURRENT_TIMESTAMP
                """
            )
        if "book_circulation_stats" in existing and "book_copies" in existing:
            conn.execute(
                """
                UPDATE book_circulation_stats
                SET total_copies = COALESCE((SELECT COUNT(*) FROM book_copies WHERE book_copies.book_id = book_circulation_stats.book_id), 0),
                    available_copies = COALESCE((SELECT COUNT(*) FROM book_copies WHERE book_copies.book_id = book_circulation_stats.book_id AND book_copies.copy_status='available'), 0),
                    active_loans = 0,
                    reservations_waiting = 0,
                    computed_at = CURRENT_TIMESTAMP
                """
            )
        if "library_profiles" in existing:
            conn.execute(
                """
                UPDATE library_profiles
                SET lendable_collection_count = COALESCE((SELECT COUNT(*) FROM book_copies WHERE copy_status='available'), 0),
                    registered_reader_count = COALESCE((SELECT COUNT(*) FROM reader_accounts), 0),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = (SELECT id FROM library_profiles ORDER BY id LIMIT 1)
                """
            )

        fk_issues = [dict(zip(["table", "rowid", "parent", "fkid"], row)) for row in conn.execute("PRAGMA foreign_key_check").fetchall()]
        if fk_issues:
            raise RuntimeError(f"Foreign key issues after cleanup: {fk_issues[:20]}")
        conn.commit()
        return {
            "database": str(db_path),
            "backup": str(backup_path) if backup_path else None,
            "deleted": deleted,
            "copy_status_reset": "book_copies" in existing,
            "reader_counts_reset": "reader_accounts" in existing,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean BookFlow runtime records while preserving seed catalog, readers, admins, rules, and locations.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()
    print(json.dumps(clean(args.db, backup=not args.no_backup), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
