from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "backend" / "data" / "bookflow.db"


def refresh(db_path: Path = DEFAULT_DB) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        stamp = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")
        conn.execute("BEGIN")
        conn.execute(
            """
            INSERT INTO book_circulation_stats (
              book_id, source_book_id, title_snapshot, total_copies, available_copies, active_loans,
              reservations_waiting, borrow_90d, reserve_90d, borrow_365d,
              days_since_last_borrow, circulation_type, stat_date, computed_at
            )
            SELECT b.id, b.source_book_id, b.title, 0, 0, 0, 0, 0, 0, 0, 9999, 'normal', date(:stamp), :stamp
            FROM books b
            WHERE NOT EXISTS (SELECT 1 FROM book_circulation_stats s WHERE s.book_id=b.id)
            """,
            {"stamp": stamp},
        )
        conn.execute(
            """
            UPDATE book_circulation_stats
            SET
              stat_date = date(:stamp),
              computed_at = :stamp
            """,
            {"stamp": stamp},
        )
        conn.execute("DROP TABLE IF EXISTS temp_copy_stats")
        conn.execute(
            """
            CREATE TEMP TABLE temp_copy_stats AS
            SELECT
              book_id,
              COUNT(*) AS total_copies,
              SUM(copy_status='available') AS available_copies
            FROM book_copies
            GROUP BY book_id
            """
        )
        conn.execute("CREATE INDEX temp_ix_copy_stats_book_id ON temp_copy_stats(book_id)")
        conn.execute("DROP TABLE IF EXISTS temp_loan_stats")
        conn.execute(
            """
            CREATE TEMP TABLE temp_loan_stats AS
            SELECT book_id, COUNT(*) AS active_loans
            FROM loans
            WHERE status IN ('active', 'overdue')
            GROUP BY book_id
            """
        )
        conn.execute("CREATE INDEX temp_ix_loan_stats_book_id ON temp_loan_stats(book_id)")
        conn.execute("DROP TABLE IF EXISTS temp_reservation_stats")
        conn.execute(
            """
            CREATE TEMP TABLE temp_reservation_stats AS
            SELECT book_id, COUNT(*) AS reservations_waiting
            FROM reservations
            WHERE status IN ('waiting', 'reserved', 'ready')
            GROUP BY book_id
            """
        )
        conn.execute("CREATE INDEX temp_ix_reservation_stats_book_id ON temp_reservation_stats(book_id)")
        conn.execute(
            """
            UPDATE book_circulation_stats
            SET
              total_copies = COALESCE((SELECT total_copies FROM temp_copy_stats s WHERE s.book_id=book_circulation_stats.book_id), 0),
              available_copies = COALESCE((SELECT available_copies FROM temp_copy_stats s WHERE s.book_id=book_circulation_stats.book_id), 0),
              active_loans = COALESCE((SELECT active_loans FROM temp_loan_stats s WHERE s.book_id=book_circulation_stats.book_id), 0),
              reservations_waiting = COALESCE((SELECT reservations_waiting FROM temp_reservation_stats s WHERE s.book_id=book_circulation_stats.book_id), 0)
            """
        )
        conn.execute(
            """
            UPDATE books
            SET copy_count_snapshot = COALESCE((SELECT total_copies FROM temp_copy_stats s WHERE s.book_id=books.id), 0)
            """
        )
        conn.execute("DROP TABLE IF EXISTS temp_copy_stats")
        conn.execute("DROP TABLE IF EXISTS temp_loan_stats")
        conn.execute("DROP TABLE IF EXISTS temp_reservation_stats")
        conn.commit()
        total = conn.execute("SELECT COUNT(*) FROM book_circulation_stats").fetchone()[0]
        return {"database": str(db_path), "updated_stats_rows": int(total or 0), "computed_at": stamp}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh derived BookFlow bibliographic statistics from current operational tables.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    print(json.dumps(refresh(args.db), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
