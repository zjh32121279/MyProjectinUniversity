from __future__ import annotations

from sqlalchemy.engine import Engine


READER_ACCOUNT_COLUMNS: dict[str, str] = {
    "avatar_url": "VARCHAR",
}


def _sqlite_columns(engine: Engine, table_name: str) -> set[str]:
    with engine.begin() as connection:
        rows = connection.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def ensure_reader_schema(engine: Engine) -> None:
    """Backfill reader-profile columns on existing SQLite databases."""
    if engine.dialect.name != "sqlite":
        return

    existing_columns = _sqlite_columns(engine, "reader_accounts")
    if not existing_columns:
        return

    with engine.begin() as connection:
        for column_name, column_sql in READER_ACCOUNT_COLUMNS.items():
            if column_name not in existing_columns:
                connection.exec_driver_sql(f"ALTER TABLE reader_accounts ADD COLUMN {column_name} {column_sql}")
