from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from bookflow_core.ai.tools.registry import registered_tool_names
from bookflow_core.db.models import Base
from bookflow_core.db.views import VIEW_SQL

DEFAULT_DB = BACKEND_ROOT / "data" / "bookflow.db"
OLD_TABLES = {"books", "bibliographic_stats", "bibliographic_subjects"}
METADATA_MINIMUMS = {
    "admin_roles": 2,
    "admin_permissions": 14,
    "admin_role_permissions": 1,
    "system_settings": 5,
    "circulation_rules": 15,
}


def _table_count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] or 0)


def _foreign_key_probe(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("BEGIN")
        try:
            conn.execute("INSERT INTO admin_user_roles (admin_id, role_id) VALUES (-999999, -999999)")
            return False
        except sqlite3.IntegrityError:
            return True
    finally:
        conn.rollback()


def validate(db_path: Path = DEFAULT_DB) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if db_path.stem != "bookflow":
        errors.append(f"database file stem must be bookflow: {db_path.name}")
    if not db_path.exists():
        return {"ok": False, "database": str(db_path), "errors": [f"database not found: {db_path}"], "warnings": []}

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        fk_enabled = int(conn.execute("PRAGMA foreign_keys").fetchone()[0] or 0) == 1
        if not fk_enabled:
            errors.append("SQLite PRAGMA foreign_keys is not enabled on validation connection")
        elif not _foreign_key_probe(conn):
            errors.append("foreign key probe did not reject an invalid relation")

        physical_tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        expected_tables = set(Base.metadata.tables)
        missing_tables = sorted(expected_tables - physical_tables)
        extra_old_tables = sorted((OLD_TABLES - expected_tables) & physical_tables)
        if missing_tables:
            errors.append(f"missing tables: {missing_tables}")
        if extra_old_tables:
            errors.append(f"old physical tables still exist: {extra_old_tables}")

        physical_views = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='view'").fetchall()
        }
        missing_views = sorted(set(VIEW_SQL) - physical_views)
        if missing_views:
            errors.append(f"missing views: {missing_views}")

        fk_tables = {}
        indexed_tables = {}
        for table in expected_tables & physical_tables:
            fk_tables[table] = len(conn.execute(f"PRAGMA foreign_key_list({table})").fetchall())
            indexed_tables[table] = len(conn.execute(f"PRAGMA index_list({table})").fetchall())
        if sum(fk_tables.values()) < 50:
            errors.append(f"too few foreign keys discovered: {sum(fk_tables.values())}")
        if sum(indexed_tables.values()) < 20:
            errors.append(f"too few indexes discovered: {sum(indexed_tables.values())}")

        metadata_counts = {}
        for table, minimum in METADATA_MINIMUMS.items():
            if table in physical_tables:
                count = _table_count(conn, table)
                metadata_counts[table] = count
                if count < minimum:
                    errors.append(f"{table} metadata count {count} is below required minimum {minimum}")
        if "ai_capabilities" in physical_tables:
            ai_count = _table_count(conn, "ai_capabilities")
            metadata_counts["ai_capabilities"] = ai_count
            expected_ai = len(registered_tool_names())
            if ai_count < expected_ai:
                warnings.append(f"ai_capabilities count {ai_count} is below registered tool count {expected_ai}")

        status_rows = [
            row[0]
            for row in conn.execute(
                """
                SELECT DISTINCT status
                FROM work_tasks
                WHERE status NOT IN ('pending', 'ai_processing', 'waiting_human', 'admin_processing', 'resolved', 'cancelled')
                """
            ).fetchall()
        ] if "work_tasks" in physical_tables else []
        if status_rows:
            errors.append(f"invalid work_tasks.status values: {status_rows}")

        row_counts = {
            table: _table_count(conn, table)
            for table in sorted(expected_tables & physical_tables)
        }
        return {
            "ok": not errors,
            "database": str(db_path),
            "table_count": len(expected_tables & physical_tables),
            "view_count": len(set(VIEW_SQL) & physical_views),
            "foreign_keys": sum(fk_tables.values()),
            "indexes": sum(indexed_tables.values()),
            "metadata_counts": metadata_counts,
            "row_counts": row_counts,
            "errors": errors,
            "warnings": warnings,
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the BookFlow database structure and metadata.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    result = validate(args.db)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()

