from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "backend" / "data" / "bookflow.db"


def scalar(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    value = conn.execute(sql, params).fetchone()[0]
    return int(value or 0)


def check(db_path: Path = DEFAULT_DB) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        result = {
            "database": str(db_path),
            "checks": {},
            "ok": True,
        }
        result["checks"]["copy_total_matches_stats"] = scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM book_circulation_stats s
            LEFT JOIN (
              SELECT book_id, COUNT(*) AS total, SUM(copy_status='available') AS available
              FROM book_copies
              GROUP BY book_id
            ) c ON c.book_id = s.book_id
            WHERE s.total_copies != COALESCE(c.total, 0)
               OR s.available_copies != COALESCE(c.available, 0)
            """,
        )
        result["checks"]["borrowed_copies_without_active_loan"] = scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM book_copies c
            WHERE c.copy_status='borrowed'
              AND NOT EXISTS (
                SELECT 1 FROM loans l
                WHERE l.copy_id=c.id AND l.status IN ('active', 'overdue')
              )
            """,
        )
        result["checks"]["active_loans_without_borrowed_copy"] = scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM loans l
            JOIN book_copies c ON c.id=l.copy_id
            WHERE l.status IN ('active', 'overdue') AND c.copy_status!='borrowed'
            """,
        )
        result["checks"]["reserved_copies_without_active_reservation"] = scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM book_copies c
            WHERE c.copy_status='reserved'
              AND NOT EXISTS (
                SELECT 1 FROM reservations r
                WHERE r.fulfilled_copy_id=c.id AND r.status IN ('ready_for_pickup')
              )
            """,
        )
        result["checks"]["tasks_missing_group"] = scalar(conn, "SELECT COUNT(*) FROM work_tasks WHERE task_group IS NULL OR TRIM(task_group)=''")
        result["checks"]["notifications_with_two_recipient_types"] = scalar(conn, "SELECT COUNT(*) FROM notifications WHERE recipient_reader_id IS NOT NULL AND recipient_admin_id IS NOT NULL")
        result["checks"]["loan_event_missing_loan"] = scalar(
            conn,
            "SELECT COUNT(*) FROM loan_events e LEFT JOIN loans l ON l.id=e.loan_id WHERE l.id IS NULL",
        )
        result["checks"]["reservation_event_missing_reservation"] = scalar(
            conn,
            "SELECT COUNT(*) FROM reservation_events e LEFT JOIN reservations r ON r.id=e.reservation_id WHERE r.id IS NULL",
        )
        result["ok"] = all(value == 0 for value in result["checks"].values())
        return result
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Check BookFlow Core data consistency without modifying data.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    result = check(args.db)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
