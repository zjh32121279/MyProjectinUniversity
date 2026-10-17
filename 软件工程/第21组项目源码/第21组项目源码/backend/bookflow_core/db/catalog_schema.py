from __future__ import annotations

from sqlalchemy.engine import Engine


BOOK_COVER_COLUMNS: dict[str, str] = {
    "cover_url": "VARCHAR",
    "cover_source": "VARCHAR",
    "cover_status": "VARCHAR DEFAULT 'missing'",
    "cover_updated_at": "DATETIME",
}


def _sqlite_columns(engine: Engine, table_name: str) -> set[str]:
    with engine.begin() as connection:
        rows = connection.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def ensure_catalog_schema(engine: Engine) -> None:
    """Backfill catalog columns on existing SQLite databases."""
    if engine.dialect.name != "sqlite":
        return

    existing_columns = _sqlite_columns(engine, "books")
    if not existing_columns:
        return

    with engine.begin() as connection:
        for column_name, column_sql in BOOK_COVER_COLUMNS.items():
            if column_name not in existing_columns:
                connection.exec_driver_sql(f"ALTER TABLE books ADD COLUMN {column_name} {column_sql}")
