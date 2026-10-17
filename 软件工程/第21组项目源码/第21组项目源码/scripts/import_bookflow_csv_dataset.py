from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "backend" / "data" / "bookflow.db"
LAUNCH_DATE = date(2026, 2, 1)
WINDOW_START = date(2026, 4, 25)
WINDOW_END = date(2026, 5, 24)
DATE_TOKEN_RE = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)")

FOCUS_TABLES = [
    "loans",
    "loan_events",
    "reservations",
    "notifications",
    "work_tasks",
    "work_task_events",
    "agent_runs",
    "agent_steps",
    "audit_events",
    "risk_warnings",
]

FINAL_RANGE_TABLES = [
    "loans",
    "reservations",
    "notifications",
    "work_tasks",
    "agent_runs",
    "audit_events",
    "risk_warnings",
]

EVENT_DATE_COLUMNS = {
    "loans": ["borrowed_at", "returned_at", "created_at", "updated_at"],
    "loan_events": ["event_time", "created_at"],
    "reservations": ["requested_at", "created_at", "updated_at"],
    "notifications": ["send_at", "sent_at", "read_at", "created_at", "updated_at"],
    "work_tasks": ["claimed_at", "resolved_at", "cancelled_at", "created_at", "updated_at"],
    "work_task_events": ["created_at"],
    "agent_runs": ["started_at", "finished_at", "created_at", "updated_at"],
    "agent_steps": ["started_at", "finished_at", "created_at", "updated_at"],
    "audit_events": ["created_at"],
    "risk_warnings": ["created_at", "updated_at", "resolved_at"],
}

REFERENCE_TABLES = {
    "book": "books",
    "books": "books",
    "copy": "book_copies",
    "book_copy": "book_copies",
    "loan": "loans",
    "reservation": "reservations",
    "work_task": "work_tasks",
    "task": "work_tasks",
    "notification": "notifications",
    "overdue_case": "overdue_cases",
    "risk": "risk_warnings",
    "risk_warning": "risk_warnings",
    "ai_rule": "ai_rules",
    "agent_run": "agent_runs",
    "reader": "reader_accounts",
    "admin": "admin_users",
}

ACTIVE_LOAN_STATUSES = ("active", "overdue")
RETURNED_LOAN_STATUSES = ("returned", "returned_overdue")
ACTIVE_RESERVATION_STATUSES = ("waiting", "ready", "ready_for_pickup", "reserved")
RESERVED_COPY_STATUSES = ("reserved", "S03")
BORROWED_COPY_STATUSES = ("borrowed", "S02")
OPEN_TASK_STATUSES = ("pending", "ai_processing", "waiting_human", "admin_processing")
AI_SUCCESS_RUN_STATUSES = ("completed", "succeeded", "success")
AI_FAILED_RUN_STATUSES = ("failed", "error")
DEFAULT_IMPORTED_ACCOUNT_PASSWORD = "BookFlow@123456"
PASSWORD_ITERATIONS = 180_000


def qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def deterministic_password_hash(password: str, *, namespace: str, subject: str) -> str:
    salt = hashlib.sha256(f"{namespace}:{subject}".encode("utf-8")).hexdigest()[:32]
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def project_path(value: str | Path | None, *, default: Path | None = None) -> Path | None:
    if value is None:
        return default
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def discover_csv_dir() -> Path:
    candidates: list[Path] = []
    direct = ROOT / "bookflow_ops_csv_package"
    if (direct / "00_load_order.txt").exists():
        candidates.append(direct)
    for child in ROOT.iterdir():
        if not child.is_dir():
            continue
        for candidate in (child, child / "bookflow_ops_csv_package"):
            if (candidate / "00_load_order.txt").exists():
                candidates.append(candidate)
    if not candidates:
        raise FileNotFoundError("Could not find a BookFlow CSV package containing 00_load_order.txt.")
    candidates.sort(key=lambda p: len(list((p / "tables").glob("*.csv"))) if (p / "tables").exists() else 0, reverse=True)
    return candidates[0]


def resolve_csv_dir(value: str | Path | None) -> Path:
    csv_dir = project_path(value) if value else discover_csv_dir()
    assert csv_dir is not None
    if not (csv_dir / "00_load_order.txt").exists():
        nested = csv_dir / "bookflow_ops_csv_package"
        if (nested / "00_load_order.txt").exists():
            csv_dir = nested
    if not (csv_dir / "00_load_order.txt").exists():
        raise FileNotFoundError(f"00_load_order.txt not found under {csv_dir}")
    return csv_dir


def resolve_db_path(value: str | Path | None) -> Path:
    if value:
        db_path = project_path(value)
        assert db_path is not None
        return db_path
    if DEFAULT_DB.exists():
        return DEFAULT_DB
    candidates = sorted((ROOT / "backend" / "data").glob("*.db")) if (ROOT / "backend" / "data").exists() else []
    candidates = [path for path in candidates if ".backup_before_csv_import_" not in path.name]
    return candidates[0] if candidates else DEFAULT_DB


def table_csv_path(csv_dir: Path, table: str) -> Path:
    for candidate in (csv_dir / "tables" / f"{table}.csv", csv_dir / f"{table}.csv"):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"CSV for table {table!r} not found in {csv_dir}")


def load_manifest(csv_dir: Path) -> dict[str, Any]:
    path = csv_dir / "manifest.json"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def load_order(csv_dir: Path) -> list[str]:
    path = csv_dir / "00_load_order.txt"
    tables: list[str] = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^(?:\d+\.\s*)?([A-Za-z_][A-Za-z0-9_]*)$", line)
        if not match:
            raise ValueError(f"Invalid load order line: {raw!r}")
        tables.append(match.group(1))
    if not tables:
        raise ValueError("00_load_order.txt is empty.")
    return tables


def load_expected_counts(csv_dir: Path) -> dict[str, int]:
    path = csv_dir / "00_table_counts.csv"
    if not path.exists():
        return {}
    counts: dict[str, int] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            table = str(row.get("table") or "").removesuffix(".csv")
            if table:
                counts[table] = int(row.get("row_count") or 0)
    return counts


def read_csv_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def iter_csv_rows(path: Path) -> Iterable[tuple[int, dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row_no, row in enumerate(reader, start=2):
            yield row_no, row


def ensure_project_schema(db_path: Path) -> None:
    backend = ROOT / "backend"
    if backend.exists() and str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    try:
        from bookflow_core.core.database import ensure_schema

        ensure_schema(f"sqlite:///{db_path.as_posix()}")
    except Exception as exc:
        print(f"[schema] SQLAlchemy schema creation was skipped: {exc}")


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def table_columns(conn: sqlite3.Connection, table: str) -> dict[str, dict[str, Any]]:
    rows = conn.execute(f"PRAGMA table_info({qident(table)})").fetchall()
    return {
        row[1]: {
            "cid": row[0],
            "name": row[1],
            "type": row[2] or "",
            "notnull": bool(row[3]),
            "default": row[4],
            "pk": bool(row[5]),
        }
        for row in rows
    }


def infer_sqlite_type(column: str, values: Iterable[str] = ()) -> str:
    name = column.lower()
    if name == "id":
        return "INTEGER"
    if name.endswith("_id") or name in {"row_no", "sort_order", "version_no", "priority", "layer_no"}:
        return "INTEGER"
    if name.startswith("is_") or name.startswith("has_") or name.endswith("_enabled") or name in {"can_rollback", "rolled_back"}:
        return "INTEGER"
    if name.endswith("_at") or name.endswith("_date") or name.endswith("_until") or name in {"effective_from", "effective_to"}:
        return "TEXT"
    if any(token in name for token in ("count", "days", "score", "rate", "price", "sqm", "tokens", "cost")):
        return "REAL"
    return "TEXT"


def create_table_from_csv(conn: sqlite3.Connection, table: str, headers: list[str]) -> None:
    columns: list[str] = []
    for header in headers:
        if header == "id":
            columns.append(f"{qident(header)} INTEGER PRIMARY KEY")
        else:
            columns.append(f"{qident(header)} {infer_sqlite_type(header)}")
    conn.execute(f"CREATE TABLE {qident(table)} ({', '.join(columns)})")
    print(f"[schema] Created missing table {table} from CSV headers.")


def add_missing_columns(conn: sqlite3.Connection, table: str, headers: list[str]) -> list[str]:
    existing = table_columns(conn, table)
    added: list[str] = []
    for header in headers:
        if header in existing:
            continue
        conn.execute(f"ALTER TABLE {qident(table)} ADD COLUMN {qident(header)} {infer_sqlite_type(header)}")
        added.append(header)
    if added:
        print(f"[schema] Added columns to {table}: {', '.join(added)}")
    return added


def sqlite_sequence_exists(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'").fetchone() is not None


def should_null_empty(column: str, sqlite_type: str) -> bool:
    name = column.lower()
    type_text = (sqlite_type or "").upper()
    if name == "id" or name.endswith("_id") or name.endswith("_at") or name.endswith("_date") or name.endswith("_until"):
        return True
    if name in {"effective_from", "effective_to", "old_due_at", "new_due_at", "reviewed_at", "resolved_at", "cancelled_at"}:
        return True
    return any(token in type_text for token in ("INT", "REAL", "FLOA", "DOUB", "NUM", "DATE", "TIME", "BOOL"))


def coerce_value(value: str | None, column: str, sqlite_type: str) -> Any:
    if value is None:
        return None
    if value == "" and should_null_empty(column, sqlite_type):
        return None
    return value


def insert_table(conn: sqlite3.Connection, table: str, csv_path: Path, *, batch_size: int = 1000) -> int:
    headers = read_csv_header(csv_path)
    if not headers:
        return 0
    columns = table_columns(conn, table)
    placeholders = ", ".join(["?"] * len(headers))
    sql = f"INSERT INTO {qident(table)} ({', '.join(qident(header) for header in headers)}) VALUES ({placeholders})"
    count = 0
    batch: list[tuple[int, tuple[Any, ...], dict[str, str]]] = []

    def flush() -> None:
        nonlocal count, batch
        if not batch:
            return
        conn.execute("SAVEPOINT import_batch")
        try:
            conn.executemany(sql, [values for _row_no, values, _raw in batch])
            conn.execute("RELEASE import_batch")
            count += len(batch)
            batch = []
        except sqlite3.Error as exc:
            conn.execute("ROLLBACK TO import_batch")
            conn.execute("RELEASE import_batch")
            for row_no, values, raw in batch:
                try:
                    conn.execute(sql, values)
                except sqlite3.Error as row_exc:
                    raise RuntimeError(
                        f"Insert failed at table={table}, csv_row={row_no}, error={row_exc}, row={raw}"
                    ) from row_exc
            raise RuntimeError(f"Insert failed at table={table}: {exc}") from exc

    for row_no, row in iter_csv_rows(csv_path):
        values = tuple(coerce_value(row.get(header), header, columns.get(header, {}).get("type", "")) for header in headers)
        batch.append((row_no, values, row))
        if len(batch) >= batch_size:
            flush()
    flush()
    return count


def backfill_work_task_compat_columns(conn: sqlite3.Connection) -> list[str]:
    if not table_exists(conn, "work_tasks"):
        return []
    columns = table_columns(conn, "work_tasks")
    required = {
        "handler_type",
        "claim_status",
        "ai_run_id",
        "ai_started_at",
        "ai_finished_at",
        "ai_error",
        "ai_result",
        "takeover_by_admin_id",
        "takeover_by_code",
        "takeover_at",
        "takeover_reason",
        "last_actor_type",
        "last_actor_id",
        "last_transition",
        "last_transition_at",
    }
    if not required.issubset(columns):
        return []
    statements = [
        """
        UPDATE work_tasks
        SET ai_run_id = (
            SELECT actor_agent_run_id FROM work_task_events e
            WHERE e.task_id = work_tasks.id AND e.actor_agent_run_id IS NOT NULL
            ORDER BY e.id LIMIT 1
        )
        WHERE ai_run_id IS NULL
        """,
        """
        UPDATE work_tasks
        SET ai_started_at = (
            SELECT MIN(created_at) FROM work_task_events e
            WHERE e.task_id = work_tasks.id AND e.event_type = 'ai_start'
        )
        WHERE ai_started_at IS NULL
        """,
        """
        UPDATE work_tasks
        SET ai_finished_at = (
            SELECT MAX(created_at) FROM work_task_events e
            WHERE e.task_id = work_tasks.id AND e.event_type IN ('ai_complete_or_assist', 'ai_fail_to_human')
        )
        WHERE ai_finished_at IS NULL
        """,
        """
        UPDATE work_tasks
        SET handler_type = CASE
            WHEN status = 'ai_processing' THEN 'ai'
            WHEN status = 'waiting_human' THEN 'mixed'
            WHEN claimed_by_admin_id IS NOT NULL OR resolved_by_admin_id IS NOT NULL OR status = 'admin_processing' THEN
                CASE WHEN ai_default_executor = 1 THEN 'mixed' ELSE 'admin' END
            WHEN source_type IN ('ai', 'ai_admin', 'rule_engine', 'patrol') OR ai_default_executor = 1 THEN 'ai'
            ELSE 'admin'
        END
        WHERE handler_type IS NULL OR handler_type = ''
        """,
        """
        UPDATE work_tasks
        SET claim_status = CASE
            WHEN status = 'pending' THEN 'unclaimed'
            WHEN status = 'ai_processing' THEN 'ai_claimed'
            WHEN status = 'waiting_human' THEN 'waiting_human'
            WHEN status = 'admin_processing' THEN 'admin_claimed'
            WHEN status = 'resolved' AND (resolved_by_admin_id IS NOT NULL OR claimed_by_admin_id IS NOT NULL) THEN 'admin_claimed'
            WHEN status = 'resolved' THEN 'ai_completed'
            WHEN status = 'cancelled' THEN 'unclaimed'
            ELSE 'unclaimed'
        END
        WHERE claim_status IS NULL OR claim_status = ''
        """,
        """
        UPDATE work_tasks
        SET ai_error = CASE WHEN status = 'waiting_human' THEN COALESCE(NULLIF(ai_error, ''), 'requires_human_confirmation') ELSE ai_error END,
            ai_result = CASE WHEN status = 'resolved' THEN COALESCE(NULLIF(ai_result, ''), resolution) ELSE ai_result END,
            takeover_by_admin_id = COALESCE(takeover_by_admin_id, claimed_by_admin_id, resolved_by_admin_id),
            takeover_by_code = COALESCE(NULLIF(takeover_by_code, ''), NULLIF(claimed_by_code, ''), NULLIF(resolved_by_code, '')),
            takeover_at = COALESCE(takeover_at, claimed_at),
            takeover_reason = CASE
                WHEN (claimed_by_admin_id IS NOT NULL OR resolved_by_admin_id IS NOT NULL OR status = 'admin_processing')
                THEN COALESCE(NULLIF(takeover_reason, ''), 'admin_takeover_or_claim')
                ELSE takeover_reason
            END
        """,
        """
        UPDATE work_tasks
        SET last_transition = (
                SELECT event_type FROM work_task_events e WHERE e.task_id = work_tasks.id ORDER BY e.created_at DESC, e.id DESC LIMIT 1
            ),
            last_transition_at = (
                SELECT created_at FROM work_task_events e WHERE e.task_id = work_tasks.id ORDER BY e.created_at DESC, e.id DESC LIMIT 1
            ),
            last_actor_type = (
                SELECT actor_type FROM work_task_events e WHERE e.task_id = work_tasks.id ORDER BY e.created_at DESC, e.id DESC LIMIT 1
            ),
            last_actor_id = COALESCE(NULLIF(resolved_by_code, ''), NULLIF(claimed_by_code, ''), '')
        WHERE last_transition IS NULL OR last_transition = ''
        """,
    ]
    for statement in statements:
        conn.execute(statement)
    return sorted(required)


def normalize_imported_password_hashes(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Replace package placeholder hashes with hashes accepted by the app login service."""
    corrections: list[dict[str, Any]] = []
    if table_exists(conn, "admin_users") and "password_hash" in table_columns(conn, "admin_users"):
        imported_admin_hash = deterministic_password_hash(
            DEFAULT_IMPORTED_ACCOUNT_PASSWORD,
            namespace="admin",
            subject="imported-default-password",
        )
        count = conn.execute(
            """
            UPDATE admin_users
            SET password_hash = ?
            WHERE password_hash IS NULL OR password_hash = '' OR password_hash NOT LIKE 'pbkdf2_sha256$%'
            """,
            (imported_admin_hash,),
        ).rowcount
        corrections.append(
            {
                "name": "normalize_admin_password_hashes",
                "count": count,
                "detail": "CSV placeholder password hashes were converted to PBKDF2 for login compatibility; default password is documented in README.",
            }
        )
    if table_exists(conn, "reader_credentials") and "password_hash" in table_columns(conn, "reader_credentials"):
        imported_reader_hash = deterministic_password_hash(
            DEFAULT_IMPORTED_ACCOUNT_PASSWORD,
            namespace="reader",
            subject="imported-default-password",
        )
        count = conn.execute(
            """
            UPDATE reader_credentials
            SET password_hash = ?
            WHERE password_hash IS NULL OR password_hash = '' OR password_hash NOT LIKE 'pbkdf2_sha256$%'
            """,
            (imported_reader_hash,),
        ).rowcount
        corrections.append(
            {
                "name": "normalize_reader_password_hashes",
                "count": count,
                "detail": "CSV placeholder password hashes were converted to PBKDF2 for reader login compatibility.",
            }
        )
    return corrections


def latest_business_date(conn: sqlite3.Connection) -> str:
    if table_exists(conn, "daily_operation_metrics"):
        value = conn.execute("SELECT MAX(metric_date) FROM daily_operation_metrics").fetchone()[0]
        if value:
            return str(value)[:10]
    return str(WINDOW_END)


def apply_post_import_consistency_corrections(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Correct CSV-level state conflicts without changing source CSV files."""
    corrections: list[dict[str, Any]] = []
    if not (table_exists(conn, "reservations") and table_exists(conn, "book_copies")):
        return corrections

    as_of = latest_business_date(conn)

    def record(name: str, count: int, detail: str) -> None:
        corrections.append({"name": name, "count": int(count), "detail": detail})

    expired_rows = conn.execute(
        """
        SELECT r.id, r.fulfilled_copy_id
        FROM reservations r
        WHERE r.status IN ('ready', 'ready_for_pickup', 'reserved')
          AND r.reserved_until IS NOT NULL
          AND date(r.reserved_until) < date(?)
        """,
        (as_of,),
    ).fetchall()
    expired_copy_ids = [row["fulfilled_copy_id"] for row in expired_rows if row["fulfilled_copy_id"] is not None]
    conn.execute(
        """
        UPDATE reservations
        SET status = 'expired'
        WHERE status IN ('ready', 'ready_for_pickup', 'reserved')
          AND reserved_until IS NOT NULL
          AND date(reserved_until) < date(?)
        """,
        (as_of,),
    )
    record("expire_past_hold_reservations", len(expired_rows), f"ready/reserved holds before {as_of} were marked expired")

    released = 0
    for copy_id in expired_copy_ids:
        active_loan = conn.execute(
            "SELECT 1 FROM loans WHERE copy_id=? AND status IN ('active', 'overdue') AND returned_at IS NULL LIMIT 1",
            (copy_id,),
        ).fetchone()
        if active_loan:
            continue
        result = conn.execute(
            """
            UPDATE book_copies
            SET copy_status = 'available', status_code = 'S01', status_name = '在馆可借'
            WHERE id = ?
              AND (copy_status = 'reserved' OR status_code = 'S03')
            """,
            (copy_id,),
        )
        released += result.rowcount
    record("release_expired_reservation_copies", released, "expired holds released reserved copies back to available")

    same_reader = conn.execute(
        """
        UPDATE reservations
        SET status = 'fulfilled'
        WHERE status IN ('ready', 'ready_for_pickup', 'reserved')
          AND fulfilled_copy_id IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM loans l
              WHERE l.copy_id = reservations.fulfilled_copy_id
                AND l.reader_id = reservations.reader_id
                AND l.status IN ('active', 'overdue')
                AND l.returned_at IS NULL
          )
        """
    ).rowcount
    record("fulfill_reservations_with_same_reader_active_loan", same_reader, "ready reservations already borrowed by the same reader were marked fulfilled")

    conflicted = conn.execute(
        """
        UPDATE reservations
        SET status = 'waiting',
            fulfilled_copy_id = NULL,
            reserved_until = NULL
        WHERE status IN ('ready', 'ready_for_pickup', 'reserved')
          AND fulfilled_copy_id IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM loans l
              WHERE l.copy_id = reservations.fulfilled_copy_id
                AND l.reader_id != reservations.reader_id
                AND l.status IN ('active', 'overdue')
                AND l.returned_at IS NULL
          )
        """
    ).rowcount
    record("unassign_ready_reservations_with_conflicting_active_loan", conflicted, "ready reservations whose copy is borrowed by another reader were returned to waiting")

    reserved = conn.execute(
        """
        UPDATE book_copies
        SET copy_status = 'reserved', status_code = 'S03', status_name = '预约保留'
        WHERE id IN (
            SELECT r.fulfilled_copy_id
            FROM reservations r
            WHERE r.status IN ('ready', 'ready_for_pickup', 'reserved')
              AND r.fulfilled_copy_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM loans l
                  WHERE l.copy_id = r.fulfilled_copy_id
                    AND l.status IN ('active', 'overdue')
                    AND l.returned_at IS NULL
              )
        )
          AND (copy_status != 'reserved' OR status_code != 'S03')
        """
    ).rowcount
    record("reserve_current_ready_pickup_copies", reserved, "current ready reservations reserve their assigned copy")
    return corrections


def backup_database(db_path: Path) -> Path | None:
    if not db_path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"{db_path.stem}.backup_before_csv_import_{timestamp}{db_path.suffix}")
    shutil.copy2(db_path, backup_path)
    return backup_path


def import_dataset(csv_dir: Path, db_path: Path, *, mode: str = "replace", backup: bool = True) -> dict[str, Any]:
    if mode != "replace":
        raise ValueError("Only --mode replace is currently supported.")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not db_path.exists():
        db_path.touch()
    ensure_project_schema(db_path)
    tables = load_order(csv_dir)
    manifest = load_manifest(csv_dir)
    backup_path = backup_database(db_path) if backup else None
    print(f"[import] CSV directory: {csv_dir}")
    print(f"[import] Database path: {db_path}")
    print(f"[import] Backup path: {backup_path or 'not created (database was new)'}")
    print(f"[import] Tables in load order: {len(tables)}")

    imported: dict[str, int] = {}
    created_tables: list[str] = []
    altered_columns: dict[str, list[str]] = {}
    compat_columns: list[str] = []
    corrections: list[dict[str, Any]] = []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN")
        for table in tables:
            csv_path = table_csv_path(csv_dir, table)
            headers = read_csv_header(csv_path)
            if not table_exists(conn, table):
                create_table_from_csv(conn, table, headers)
                created_tables.append(table)
            added = add_missing_columns(conn, table, headers)
            if added:
                altered_columns[table] = added

        for table in reversed(tables):
            if table_exists(conn, table):
                conn.execute(f"DELETE FROM {qident(table)}")
                if sqlite_sequence_exists(conn):
                    conn.execute("DELETE FROM sqlite_sequence WHERE name=?", (table,))

        for table in tables:
            imported[table] = insert_table(conn, table, table_csv_path(csv_dir, table))
            print(f"[import] {table}: {imported[table]} rows")

        corrections = apply_post_import_consistency_corrections(conn)
        for item in corrections:
            if item["count"]:
                print(f"[import] correction {item['name']}: {item['count']} rows")

        password_corrections = normalize_imported_password_hashes(conn)
        corrections.extend(password_corrections)
        for item in password_corrections:
            if item["count"]:
                print(f"[import] correction {item['name']}: {item['count']} rows")

        compat_columns = backfill_work_task_compat_columns(conn)
        if compat_columns:
            print("[import] Backfilled work_tasks compatibility lifecycle columns.")

        conn.commit()
        conn.execute("PRAGMA foreign_keys=ON")
        fk_rows = [dict(row) for row in conn.execute("PRAGMA foreign_key_check").fetchall()]
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    validation = validate_database(db_path, csv_dir, tables=tables)
    report_paths = write_reports(
        csv_dir=csv_dir,
        db_path=db_path,
        backup_path=backup_path,
        manifest=manifest,
        imported=imported,
        validation=validation,
        created_tables=created_tables,
        altered_columns=altered_columns,
        compat_columns=compat_columns,
        corrections=corrections,
    )
    validation["pragma_foreign_key_check"] = fk_rows
    return {
        "csv_dir": str(csv_dir),
        "db_path": str(db_path),
        "backup_path": str(backup_path) if backup_path else "",
        "tables": len(tables),
        "imported": imported,
        "created_tables": created_tables,
        "altered_columns": altered_columns,
        "compat_columns": compat_columns,
        "corrections": corrections,
        "validation": validation,
        "reports": report_paths,
    }


def parse_date_token(token: str) -> date | None:
    try:
        return datetime.strptime(token, "%Y-%m-%d").date()
    except ValueError:
        return None


def scalar_count(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    return int(conn.execute(sql, params).fetchone()[0] or 0)


def fetch_sample(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = (), limit: int = 10) -> list[dict[str, Any]]:
    sql_with_limit = f"{sql} LIMIT {int(limit)}"
    return [dict(row) for row in conn.execute(sql_with_limit, params).fetchall()]


def table_count(conn: sqlite3.Connection, table: str) -> int:
    return scalar_count(conn, f"SELECT COUNT(*) FROM {qident(table)}")


def validate_counts(conn: sqlite3.Connection, expected: dict[str, int], tables: list[str]) -> list[dict[str, Any]]:
    results = []
    for table in tables:
        expected_count = expected.get(table)
        actual_count = table_count(conn, table) if table_exists(conn, table) else None
        status = "PASS" if expected_count == actual_count else "FAIL"
        results.append({"table": table, "expected_count": expected_count, "actual_count": actual_count, "status": status})
    return results


def validate_dates(conn: sqlite3.Connection, tables: list[str]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for table in tables:
        if not table_exists(conn, table):
            continue
        columns = table_columns(conn, table)
        names = list(columns)
        pk = "id" if "id" in columns else names[0]
        select_cols = ", ".join(qident(col) for col in [pk, *names])
        for row in conn.execute(f"SELECT {select_cols} FROM {qident(table)}"):
            primary_key = row[0]
            for col in names:
                if col == "publish_year":
                    continue
                value = row[col]
                if value is None:
                    continue
                text = str(value)
                for token in DATE_TOKEN_RE.findall(text):
                    parsed = parse_date_token(token)
                    if parsed and parsed < LAUNCH_DATE:
                        issues.append({"table": table, "column": col, "primary_key": primary_key, "value": text})
    return issues


def date_range_for_columns(conn: sqlite3.Connection, table: str, columns: list[str]) -> dict[str, Any]:
    if not table_exists(conn, table):
        return {"table": table, "status": "SKIP", "reason": "missing table"}
    existing = table_columns(conn, table)
    found: list[date] = []
    col_ranges: dict[str, dict[str, str | int]] = {}
    for column in columns:
        if column not in existing:
            continue
        values = conn.execute(f"SELECT {qident(column)} FROM {qident(table)} WHERE {qident(column)} IS NOT NULL AND {qident(column)} != ''").fetchall()
        dates: list[date] = []
        for (value,) in values:
            for token in DATE_TOKEN_RE.findall(str(value)):
                parsed = parse_date_token(token)
                if parsed:
                    dates.append(parsed)
        if dates:
            found.extend(dates)
            col_ranges[column] = {"count": len(dates), "min": str(min(dates)), "max": str(max(dates))}
    if not found:
        return {"table": table, "status": "WARN", "reason": "no event dates found", "columns": col_ranges}
    return {"table": table, "status": "PASS", "min": str(min(found)), "max": str(max(found)), "columns": col_ranges}


def validate_operation_windows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = []
    for table in FOCUS_TABLES:
        item = date_range_for_columns(conn, table, EVENT_DATE_COLUMNS.get(table, []))
        if item["status"] == "PASS":
            min_date = parse_date_token(str(item["min"]))
            max_date = parse_date_token(str(item["max"]))
            if min_date and min_date < LAUNCH_DATE:
                item["status"] = "FAIL"
                item["reason"] = "event date before launch"
            elif max_date and max_date < WINDOW_START:
                item["status"] = "WARN"
                item["reason"] = "event dates do not reach operation window"
        rows.append(item)
    return rows


def orphan_check(
    conn: sqlite3.Connection,
    *,
    child: str,
    child_col: str,
    parent: str,
    parent_col: str = "id",
    condition: str = "1=1",
) -> dict[str, Any]:
    if not (table_exists(conn, child) and table_exists(conn, parent)):
        return {"check": f"{child}.{child_col}->{parent}.{parent_col}", "status": "SKIP", "count": 0, "sample": []}
    sql = f"""
        SELECT c.id AS child_id, c.{qident(child_col)} AS value
        FROM {qident(child)} c
        LEFT JOIN {qident(parent)} p ON CAST(c.{qident(child_col)} AS TEXT) = CAST(p.{qident(parent_col)} AS TEXT)
        WHERE {condition}
          AND c.{qident(child_col)} IS NOT NULL
          AND CAST(c.{qident(child_col)} AS TEXT) != ''
          AND p.{qident(parent_col)} IS NULL
    """
    sample = fetch_sample(conn, sql)
    count = scalar_count(conn, f"SELECT COUNT(*) FROM ({sql})")
    return {"check": f"{child}.{child_col}->{parent}.{parent_col}", "status": "PASS" if count == 0 else "FAIL", "count": count, "sample": sample}


def polymorphic_reference_check(
    conn: sqlite3.Connection,
    *,
    table: str,
    type_col: str,
    id_col: str,
    prefix: str,
) -> list[dict[str, Any]]:
    if not table_exists(conn, table):
        return [{"check": f"{prefix} polymorphic references", "status": "SKIP", "count": 0, "sample": []}]
    checks: list[dict[str, Any]] = []
    existing = table_columns(conn, table)
    if type_col not in existing or id_col not in existing:
        return [{"check": f"{prefix} polymorphic references", "status": "SKIP", "count": 0, "sample": []}]
    types = [row[0] for row in conn.execute(f"SELECT DISTINCT {qident(type_col)} FROM {qident(table)} WHERE {qident(type_col)} IS NOT NULL AND {qident(type_col)} != ''")]
    for ref_type in sorted(str(value) for value in types if str(value) in REFERENCE_TABLES):
        parent = REFERENCE_TABLES[ref_type]
        if not table_exists(conn, parent):
            continue
        if ref_type == "admin":
            sql = f"""
                SELECT c.id AS child_id, c.{qident(type_col)} AS ref_type, c.{qident(id_col)} AS value
                FROM {qident(table)} c
                LEFT JOIN admin_users p
                  ON CAST(c.{qident(id_col)} AS TEXT) = CAST(p.id AS TEXT)
                  OR CAST(c.{qident(id_col)} AS TEXT) = CAST(p.admin_code AS TEXT)
                WHERE c.{qident(type_col)} = ?
                  AND c.{qident(id_col)} IS NOT NULL
                  AND CAST(c.{qident(id_col)} AS TEXT) != ''
                  AND p.id IS NULL
            """
            params = (ref_type,)
        else:
            sql = f"""
                SELECT c.id AS child_id, c.{qident(type_col)} AS ref_type, c.{qident(id_col)} AS value
                FROM {qident(table)} c
                LEFT JOIN {qident(parent)} p ON CAST(c.{qident(id_col)} AS TEXT) = CAST(p.id AS TEXT)
                WHERE c.{qident(type_col)} = ?
                  AND c.{qident(id_col)} IS NOT NULL
                  AND CAST(c.{qident(id_col)} AS TEXT) != ''
                  AND p.id IS NULL
            """
            params = (ref_type,)
        sample = fetch_sample(conn, sql, params)
        count = scalar_count(conn, f"SELECT COUNT(*) FROM ({sql})", params)
        checks.append({"check": f"{prefix}.{ref_type}->{parent}.id", "status": "PASS" if count == 0 else "FAIL", "count": count, "sample": sample})
    return checks


def validate_references(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    checks = [
        orphan_check(conn, child="books", child_col="category_id", parent="book_categories"),
        orphan_check(conn, child="books", child_col="subcategory_id", parent="book_subcategories"),
        orphan_check(conn, child="book_copies", child_col="book_id", parent="books"),
        orphan_check(conn, child="book_copies", child_col="current_zone_id", parent="library_zones"),
        orphan_check(conn, child="book_copies", child_col="current_shelf_id", parent="shelves"),
        orphan_check(conn, child="loans", child_col="reader_id", parent="reader_accounts"),
        orphan_check(conn, child="loans", child_col="copy_id", parent="book_copies"),
        orphan_check(conn, child="loans", child_col="book_id", parent="books"),
        orphan_check(conn, child="reservations", child_col="reader_id", parent="reader_accounts"),
        orphan_check(conn, child="reservations", child_col="book_id", parent="books"),
        orphan_check(conn, child="reservations", child_col="fulfilled_copy_id", parent="book_copies"),
        orphan_check(conn, child="notifications", child_col="recipient_reader_id", parent="reader_accounts"),
        orphan_check(conn, child="notifications", child_col="recipient_admin_id", parent="admin_users"),
        orphan_check(conn, child="work_tasks", child_col="assigned_to_admin_id", parent="admin_users"),
        orphan_check(conn, child="work_tasks", child_col="claimed_by_admin_id", parent="admin_users"),
        orphan_check(conn, child="work_tasks", child_col="resolved_by_admin_id", parent="admin_users"),
        orphan_check(conn, child="work_task_events", child_col="task_id", parent="work_tasks"),
        orphan_check(conn, child="work_task_events", child_col="actor_agent_run_id", parent="agent_runs"),
        orphan_check(conn, child="agent_steps", child_col="run_id", parent="agent_runs"),
        orphan_check(conn, child="audit_events", child_col="actor_admin_id", parent="admin_users"),
        orphan_check(conn, child="audit_events", child_col="actor_agent_run_id", parent="agent_runs"),
        orphan_check(conn, child="risk_warnings", child_col="created_task_id", parent="work_tasks"),
    ]
    checks.extend(polymorphic_reference_check(conn, table="notifications", type_col="related_entity_type", id_col="related_entity_id", prefix="notifications"))
    checks.extend(polymorphic_reference_check(conn, table="work_tasks", type_col="related_entity_type", id_col="related_entity_id", prefix="work_tasks"))
    checks.extend(polymorphic_reference_check(conn, table="audit_events", type_col="target_entity_type", id_col="target_entity_id", prefix="audit_events"))
    checks.extend(polymorphic_reference_check(conn, table="risk_warnings", type_col="related_entity_type", id_col="related_entity_id", prefix="risk_warnings"))

    pragma = [dict(row) for row in conn.execute("PRAGMA foreign_key_check").fetchall()]
    checks.append({"check": "PRAGMA foreign_key_check", "status": "PASS" if not pragma else "FAIL", "count": len(pragma), "sample": pragma[:10]})
    return checks


def status_check(conn: sqlite3.Connection, name: str, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
    sample = fetch_sample(conn, sql, params)
    count = scalar_count(conn, f"SELECT COUNT(*) FROM ({sql})", params)
    return {"check": name, "status": "PASS" if count == 0 else "FAIL", "count": count, "sample": sample}


def validate_agent_run_task_codes(conn: sqlite3.Connection) -> dict[str, Any]:
    if not (table_exists(conn, "agent_runs") and table_exists(conn, "work_tasks")):
        return {"check": "agent_runs input_json task_code references", "status": "SKIP", "count": 0, "sample": []}
    task_codes = {row[0] for row in conn.execute("SELECT task_code FROM work_tasks WHERE task_code IS NOT NULL")}
    issues: list[dict[str, Any]] = []
    for row in conn.execute("SELECT id, run_code, input_json FROM agent_runs WHERE input_json IS NOT NULL AND input_json != ''"):
        try:
            payload = json.loads(row["input_json"])
        except json.JSONDecodeError:
            continue
        task_code = payload.get("task_code") if isinstance(payload, dict) else None
        if task_code and task_code not in task_codes:
            issues.append({"run_id": row["id"], "run_code": row["run_code"], "task_code": task_code})
    return {"check": "agent_runs input_json task_code references", "status": "PASS" if not issues else "FAIL", "count": len(issues), "sample": issues[:10]}


def validate_status_consistency(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    checks = [
        status_check(
            conn,
            "copy has at most one unreturned active loan",
            """
            SELECT copy_id, COUNT(*) AS active_loan_count
            FROM loans
            WHERE status IN ('active', 'overdue') AND returned_at IS NULL AND copy_id IS NOT NULL
            GROUP BY copy_id
            HAVING COUNT(*) > 1
            """,
        ),
        status_check(
            conn,
            "active loans use borrowed copy state",
            """
            SELECT l.id AS loan_id, l.copy_id, c.copy_status, c.status_code
            FROM loans l
            JOIN book_copies c ON c.id = l.copy_id
            WHERE l.status IN ('active', 'overdue')
              AND l.returned_at IS NULL
              AND COALESCE(c.copy_status, '') NOT IN ('borrowed')
              AND COALESCE(c.status_code, '') NOT IN ('S02')
            """,
        ),
        status_check(
            conn,
            "ready reservations use reserved copy state",
            """
            SELECT r.id AS reservation_id, r.fulfilled_copy_id, c.copy_status, c.status_code
            FROM reservations r
            JOIN book_copies c ON c.id = r.fulfilled_copy_id
            WHERE r.status IN ('ready', 'ready_for_pickup', 'reserved')
              AND COALESCE(c.copy_status, '') NOT IN ('reserved')
              AND COALESCE(c.status_code, '') NOT IN ('S03')
            """,
        ),
        status_check(
            conn,
            "returned loans have returned_at",
            """
            SELECT id, status, returned_at FROM loans
            WHERE status IN ('returned', 'returned_overdue')
              AND returned_at IS NULL
            """,
        ),
        status_check(
            conn,
            "unreturned loans do not have returned_at",
            """
            SELECT id, status, returned_at FROM loans
            WHERE status IN ('active', 'overdue')
              AND returned_at IS NOT NULL
            """,
        ),
        status_check(
            conn,
            "work_tasks use canonical statuses",
            """
            SELECT id, task_code, status FROM work_tasks
            WHERE status NOT IN ('pending', 'ai_processing', 'waiting_human', 'admin_processing', 'resolved', 'cancelled')
            """,
        ),
        status_check(
            conn,
            "waiting_human tasks have human-transfer reason",
            """
            SELECT t.id, t.task_code, t.requires_human_confirmation, t.ai_error
            FROM work_tasks t
            WHERE t.status = 'waiting_human'
              AND COALESCE(t.requires_human_confirmation, 0) NOT IN (1, '1', 'true', 'True')
              AND COALESCE(t.ai_error, '') = ''
              AND NOT EXISTS (
                  SELECT 1 FROM work_task_events e
                  WHERE e.task_id = t.id AND e.event_type = 'ai_fail_to_human'
              )
            """,
        ),
        status_check(
            conn,
            "admin processed tasks have takeover event",
            """
            SELECT t.id, t.task_code, t.status
            FROM work_tasks t
            WHERE (t.status = 'admin_processing' OR t.claimed_by_admin_id IS NOT NULL OR t.resolved_by_admin_id IS NOT NULL)
              AND NOT EXISTS (
                  SELECT 1 FROM work_task_events e
                  WHERE e.task_id = t.id AND e.actor_type = 'admin'
              )
            """,
        ),
        status_check(
            conn,
            "AI failure to human has audit event for run",
            """
            SELECT e.id AS event_id, e.task_id, e.actor_agent_run_id
            FROM work_task_events e
            WHERE e.event_type = 'ai_fail_to_human'
              AND e.actor_agent_run_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM audit_events a
                  WHERE a.actor_agent_run_id = e.actor_agent_run_id OR (a.target_entity_type = 'agent_run' AND CAST(a.target_entity_id AS TEXT) = CAST(e.actor_agent_run_id AS TEXT))
              )
            """,
        ),
        status_check(
            conn,
            "admin takeover has audit event",
            """
            SELECT e.id AS event_id, e.task_id
            FROM work_task_events e
            WHERE e.event_type = 'admin_takeover_or_claim'
              AND NOT EXISTS (
                  SELECT 1 FROM audit_events a
                  WHERE a.action = 'admin_takeover_task'
                    AND a.target_entity_type = 'work_task'
                    AND CAST(a.target_entity_id AS TEXT) = CAST(e.task_id AS TEXT)
              )
            """,
        ),
        validate_agent_run_task_codes(conn),
    ]
    return checks


def validate_database(db_path: Path, csv_dir: Path, *, tables: list[str] | None = None) -> dict[str, Any]:
    resolved_tables = tables or load_order(csv_dir)
    expected = load_expected_counts(csv_dir)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        counts = validate_counts(conn, expected, resolved_tables)
        date_issues = validate_dates(conn, resolved_tables)
        operation_windows = validate_operation_windows(conn)
        final_ranges = {table: date_range_for_columns(conn, table, EVENT_DATE_COLUMNS.get(table, [])) for table in FINAL_RANGE_TABLES}
        references = validate_references(conn)
        statuses = validate_status_consistency(conn)
    finally:
        conn.close()
    return {
        "counts": counts,
        "date_issues": date_issues,
        "operation_windows": operation_windows,
        "final_ranges": final_ranges,
        "references": references,
        "status_consistency": statuses,
        "ok": all(row["status"] == "PASS" for row in counts)
        and not date_issues
        and all(row["status"] in {"PASS", "SKIP"} for row in references)
        and all(row["status"] == "PASS" for row in statuses),
    }


def validation_rows(validation: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in validation["counts"]:
        rows.append({"section": "counts", "name": item["table"], "expected": item["expected_count"], "actual": item["actual_count"], "status": item["status"], "detail": ""})
    rows.append({"section": "dates", "name": "full_date_after_launch", "expected": ">=2026-02-01", "actual": len(validation["date_issues"]), "status": "PASS" if not validation["date_issues"] else "FAIL", "detail": json.dumps(validation["date_issues"][:20], ensure_ascii=False)})
    for item in validation["operation_windows"]:
        rows.append({"section": "operation_window", "name": item["table"], "expected": "2026-04-25..2026-05-24 focus", "actual": f"{item.get('min', '')}..{item.get('max', '')}", "status": item["status"], "detail": item.get("reason", "")})
    for item in validation["references"]:
        rows.append({"section": "references", "name": item["check"], "expected": 0, "actual": item["count"], "status": item["status"], "detail": json.dumps(item.get("sample", []), ensure_ascii=False)})
    for item in validation["status_consistency"]:
        rows.append({"section": "status", "name": item["check"], "expected": 0, "actual": item["count"], "status": item["status"], "detail": json.dumps(item.get("sample", []), ensure_ascii=False)})
    return rows


def write_reports(
    *,
    csv_dir: Path,
    db_path: Path,
    backup_path: Path | None,
    manifest: dict[str, Any],
    imported: dict[str, int],
    validation: dict[str, Any],
    created_tables: list[str],
    altered_columns: dict[str, list[str]],
    compat_columns: list[str],
    corrections: list[dict[str, Any]],
) -> dict[str, str]:
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_report = reports / f"import_validation_{timestamp}.csv"
    md_report = reports / f"import_report_{timestamp}.md"

    rows = validation_rows(validation)
    with csv_report.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["section", "name", "expected", "actual", "status", "detail"])
        writer.writeheader()
        writer.writerows(rows)

    count_failures = [row for row in validation["counts"] if row["status"] != "PASS"]
    ref_failures = [row for row in validation["references"] if row["status"] == "FAIL"]
    status_failures = [row for row in validation["status_consistency"] if row["status"] == "FAIL"]
    lines = [
        "# BookFlow CSV Import Report",
        "",
        f"- generated_at: {datetime.now().isoformat(timespec='seconds')}",
        f"- csv_dir: {csv_dir}",
        f"- db_path: {db_path}",
        f"- backup_path: {backup_path or ''}",
        f"- manifest_tables: {manifest.get('tables', '')}",
        f"- validation_ok: {validation['ok']}",
        f"- created_tables: {', '.join(created_tables) if created_tables else 'none'}",
        f"- altered_columns: {json.dumps(altered_columns, ensure_ascii=False) if altered_columns else 'none'}",
        f"- backfilled_work_task_columns: {', '.join(compat_columns) if compat_columns else 'none'}",
        f"- post_import_corrections: {json.dumps(corrections, ensure_ascii=False)}",
        "",
        "## Imported Rows",
        "",
        "| table | rows |",
        "| --- | ---: |",
    ]
    for table, count in imported.items():
        lines.append(f"| {table} | {count} |")
    lines.extend(
        [
            "",
            "## Validation Summary",
            "",
            f"- count_failures: {len(count_failures)}",
            f"- date_issues_before_2026_02_01: {len(validation['date_issues'])}",
            f"- reference_failures: {len(ref_failures)}",
            f"- status_failures: {len(status_failures)}",
            "",
            "## Focus Table Date Ranges",
            "",
            "| table | min | max | status |",
            "| --- | --- | --- | --- |",
        ]
    )
    for table, item in validation["final_ranges"].items():
        lines.append(f"| {table} | {item.get('min', '')} | {item.get('max', '')} | {item.get('status', '')} |")
    if validation["date_issues"]:
        lines.extend(["", "## Date Issues", ""])
        lines.append("```json")
        lines.append(json.dumps(validation["date_issues"][:50], ensure_ascii=False, indent=2))
        lines.append("```")
    if ref_failures:
        lines.extend(["", "## Reference Failures", ""])
        lines.append("```json")
        lines.append(json.dumps(ref_failures[:50], ensure_ascii=False, indent=2))
        lines.append("```")
    if status_failures:
        lines.extend(["", "## Status Failures", ""])
        lines.append("```json")
        lines.append(json.dumps(status_failures[:50], ensure_ascii=False, indent=2))
        lines.append("```")
    md_report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"markdown": str(md_report), "csv": str(csv_report)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the full BookFlow 64-table CSV dataset into SQLite.")
    parser.add_argument("--csv-dir", type=Path, default=None, help="CSV package directory containing 00_load_order.txt.")
    parser.add_argument("--db", type=Path, default=None, help="SQLite database path. Defaults to backend/data/bookflow.db.")
    parser.add_argument("--mode", choices=["replace"], default="replace")
    parser.add_argument("--backup", action="store_true", default=True, help="Create a timestamped database backup before import. Enabled by default.")
    args = parser.parse_args()

    csv_dir = resolve_csv_dir(args.csv_dir)
    db_path = resolve_db_path(args.db)
    result = import_dataset(csv_dir, db_path, mode=args.mode, backup=args.backup)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["validation"]["ok"] else 1)


if __name__ == "__main__":
    main()
