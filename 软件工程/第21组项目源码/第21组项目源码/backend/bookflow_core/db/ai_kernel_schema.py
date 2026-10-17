from __future__ import annotations

from sqlalchemy.engine import Engine


WORK_TASK_COLUMNS: dict[str, str] = {
    "queue_name": "VARCHAR DEFAULT 'default'",
    "priority_score": "INTEGER DEFAULT 0",
    "risk_level": "VARCHAR DEFAULT 'low'",
    "urgency_reason": "TEXT",
    "source_payload_json": "TEXT",
    "execution_context_json": "TEXT",
    "ai_plan_json": "TEXT",
    "ai_trace_json": "TEXT",
    "lease_owner": "VARCHAR",
    "lease_expires_at": "DATETIME",
    "attempt_count": "INTEGER DEFAULT 0",
    "max_attempts": "INTEGER DEFAULT 3",
    "next_attempt_at": "DATETIME",
    "interrupted_at": "DATETIME",
    "interrupt_reason": "TEXT",
}


def _sqlite_columns(engine: Engine, table_name: str) -> set[str]:
    with engine.begin() as connection:
        rows = connection.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def ensure_ai_kernel_schema(engine: Engine) -> None:
    """Backfill AI Kernel columns on existing SQLite databases.

    SQLAlchemy ``create_all`` is intentionally non-destructive and will not add
    columns to an existing table. BookFlow's local runtime uses SQLite, so the
    AI task-pool migration is handled here in a small idempotent pass.
    """
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
CREATE TABLE IF NOT EXISTS ai_task_checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checkpoint_code VARCHAR UNIQUE,
    task_id INTEGER REFERENCES work_tasks(id),
    run_id INTEGER REFERENCES agent_runs(id),
    worker_id VARCHAR,
    node_name VARCHAR,
    status VARCHAR,
    state_json TEXT,
    resume_token VARCHAR,
    created_at DATETIME,
    updated_at DATETIME
)
"""
        )
        connection.exec_driver_sql(
            """
CREATE TABLE IF NOT EXISTS ai_execution_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ledger_code VARCHAR UNIQUE,
    task_id INTEGER REFERENCES work_tasks(id),
    task_code VARCHAR,
    run_id INTEGER REFERENCES agent_runs(id),
    sop_id VARCHAR,
    phase VARCHAR,
    tool_name VARCHAR,
    idempotency_key VARCHAR UNIQUE,
    target_type VARCHAR,
    target_id VARCHAR,
    status VARCHAR,
    reason TEXT,
    request_json TEXT,
    result_json TEXT,
    created_at DATETIME,
    updated_at DATETIME
)
"""
        )

    existing_columns = _sqlite_columns(engine, "work_tasks")
    if not existing_columns:
        return

    with engine.begin() as connection:
        for column_name, column_sql in WORK_TASK_COLUMNS.items():
            if column_name not in existing_columns:
                connection.exec_driver_sql(f"ALTER TABLE work_tasks ADD COLUMN {column_name} {column_sql}")
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_work_tasks_queue_lease "
            "ON work_tasks (queue_name, status, lease_expires_at)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_work_tasks_priority_score "
            "ON work_tasks (status, priority_score)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_ai_task_checkpoints_task_run "
            "ON ai_task_checkpoints (task_id, run_id, status)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_ai_execution_ledger_task "
            "ON ai_execution_ledger (task_code, phase, status)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_ai_execution_ledger_target "
            "ON ai_execution_ledger (target_type, target_id, tool_name)"
        )
