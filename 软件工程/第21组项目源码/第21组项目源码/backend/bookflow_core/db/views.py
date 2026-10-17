from __future__ import annotations

from sqlalchemy.engine import Engine


VIEW_SQL: dict[str, str] = {
    "v_book_availability": """
CREATE VIEW v_book_availability AS
SELECT
    b.id AS book_id,
    b.book_code,
    b.title,
    b.category_code,
    b.category_name,
    COUNT(c.id) AS total_copies,
    SUM(CASE WHEN c.copy_status = 'available' THEN 1 ELSE 0 END) AS available_copies,
    SUM(CASE WHEN c.copy_status = 'borrowed' THEN 1 ELSE 0 END) AS borrowed_copies,
    SUM(CASE WHEN c.copy_status = 'reserved' THEN 1 ELSE 0 END) AS reserved_copies,
    SUM(CASE WHEN c.copy_status IN ('maintenance', 'unavailable') THEN 1 ELSE 0 END) AS maintenance_copies,
    SUM(CASE WHEN c.copy_status = 'lost' THEN 1 ELSE 0 END) AS lost_copies
FROM books b
LEFT JOIN book_copies c ON c.book_id = b.id
GROUP BY b.id, b.book_code, b.title, b.category_code, b.category_name
""",
    "v_reader_borrow_summary": """
CREATE VIEW v_reader_borrow_summary AS
SELECT
    r.id AS reader_id,
    r.reader_code,
    r.name,
    r.status,
    COUNT(DISTINCT CASE WHEN l.status IN ('active', 'borrowed') THEN l.id END) AS active_loans,
    COUNT(DISTINCT CASE WHEN l.status = 'overdue' THEN l.id END) AS overdue_loans,
    COUNT(DISTINCT CASE WHEN l.status IN ('returned', 'returned_overdue') THEN l.id END) AS returned_loans,
    COUNT(DISTINCT CASE WHEN rv.status IN ('waiting', 'ready_for_pickup') THEN rv.id END) AS active_reservations,
    MAX(l.borrowed_at) AS last_borrowed_at
FROM reader_accounts r
LEFT JOIN loans l ON l.reader_id = r.id
LEFT JOIN reservations rv ON rv.reader_id = r.id
GROUP BY r.id, r.reader_code, r.name, r.status
""",
    "v_admin_home_kpis": """
CREATE VIEW v_admin_home_kpis AS
SELECT 'book_titles' AS metric_key, COUNT(*) AS metric_value FROM books
UNION ALL
SELECT 'book_copies' AS metric_key, COUNT(*) AS metric_value FROM book_copies
UNION ALL
SELECT 'readers' AS metric_key, COUNT(*) AS metric_value FROM reader_accounts
UNION ALL
SELECT 'active_loans' AS metric_key, COUNT(*) AS metric_value FROM loans WHERE status IN ('active', 'borrowed', 'overdue')
UNION ALL
SELECT 'pending_reservations' AS metric_key, COUNT(*) AS metric_value FROM reservations WHERE status IN ('waiting', 'ready_for_pickup')
UNION ALL
SELECT 'open_tasks' AS metric_key, COUNT(*) AS metric_value FROM work_tasks WHERE status IN ('pending', 'ai_processing', 'waiting_human', 'admin_processing')
UNION ALL
SELECT 'open_risks' AS metric_key, COUNT(*) AS metric_value FROM risk_warnings WHERE status IN ('active', 'open', 'reviewing')
""",
    "v_collection_health_by_zone": """
CREATE VIEW v_collection_health_by_zone AS
SELECT
    z.id AS zone_id,
    z.zone_code,
    z.zone_name,
    COUNT(c.id) AS copy_count,
    SUM(CASE WHEN c.copy_status = 'available' THEN 1 ELSE 0 END) AS available_count,
    SUM(CASE WHEN c.copy_status = 'borrowed' THEN 1 ELSE 0 END) AS borrowed_count,
    SUM(CASE WHEN c.copy_status IN ('maintenance', 'unavailable', 'lost', 'withdrawn') THEN 1 ELSE 0 END) AS unavailable_count
FROM library_zones z
LEFT JOIN book_copies c ON c.current_zone_id = z.id
GROUP BY z.id, z.zone_code, z.zone_name
""",
    "v_task_pool": """
CREATE VIEW v_task_pool AS
SELECT
    t.id,
    t.task_code,
    t.title,
    t.task_type,
    t.task_group,
    t.priority,
    t.priority_score,
    t.risk_level,
    t.queue_name,
    t.status,
    t.handler_type,
    t.claim_status,
    t.lease_owner,
    t.lease_expires_at,
    t.attempt_count,
    t.max_attempts,
    t.interrupted_at,
    t.interrupt_reason,
    t.ai_default_executor,
    t.assigned_to_admin_id,
    t.claimed_by_admin_id,
    t.related_entity_type,
    t.related_entity_id,
    t.sla_due_at,
    t.created_at,
    t.updated_at
FROM work_tasks t
""",
    "v_notification_summary": """
CREATE VIEW v_notification_summary AS
SELECT
    channel,
    notification_type,
    status,
    COUNT(*) AS notification_count,
    MIN(created_at) AS first_created_at,
    MAX(created_at) AS last_created_at
FROM notifications
GROUP BY channel, notification_type, status
""",
    "v_superadmin_governance_overview": """
CREATE VIEW v_superadmin_governance_overview AS
SELECT 'admins' AS metric_key, COUNT(*) AS metric_value FROM admin_users
UNION ALL
SELECT 'super_admins' AS metric_key, COUNT(*) AS metric_value FROM admin_users WHERE is_super_admin = 1
UNION ALL
SELECT 'enabled_ai_rules' AS metric_key, COUNT(*) AS metric_value FROM ai_rules WHERE is_enabled = 1 AND status = 'active'
UNION ALL
SELECT 'pending_ai_approvals' AS metric_key, COUNT(*) AS metric_value FROM ai_approval_requests WHERE status = 'pending'
UNION ALL
SELECT 'open_risk_warnings' AS metric_key, COUNT(*) AS metric_value FROM risk_warnings WHERE status IN ('active', 'open', 'reviewing')
UNION ALL
SELECT 'audit_events' AS metric_key, COUNT(*) AS metric_value FROM audit_events
""",
    "v_ai_rule_runtime_status": """
CREATE VIEW v_ai_rule_runtime_status AS
SELECT
    r.id AS rule_id,
    r.rule_code,
    r.rule_name,
    r.module,
    r.status,
    r.is_enabled,
    r.current_version_id,
    COUNT(l.id) AS execution_count,
    MAX(l.created_at) AS last_executed_at
FROM ai_rules r
LEFT JOIN ai_rule_execution_logs l ON l.rule_id = r.id
GROUP BY r.id, r.rule_code, r.rule_name, r.module, r.status, r.is_enabled, r.current_version_id
""",
    "v_audit_risk_distribution": """
CREATE VIEW v_audit_risk_distribution AS
SELECT
    'audit' AS distribution_type,
    action AS bucket,
    result AS sub_bucket,
    COUNT(*) AS event_count
FROM audit_events
GROUP BY action, result
UNION ALL
SELECT
    'risk' AS distribution_type,
    warning_type AS bucket,
    severity AS sub_bucket,
    COUNT(*) AS event_count
FROM risk_warnings
GROUP BY warning_type, severity
""",
}


def drop_views(engine: Engine) -> None:
    with engine.begin() as connection:
        for view_name in VIEW_SQL:
            connection.exec_driver_sql(f"DROP VIEW IF EXISTS {view_name}")


def create_views(engine: Engine) -> None:
    with engine.begin() as connection:
        for view_name, sql in VIEW_SQL.items():
            connection.exec_driver_sql(f"DROP VIEW IF EXISTS {view_name}")
            connection.exec_driver_sql(sql)
