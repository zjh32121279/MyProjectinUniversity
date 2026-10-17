from __future__ import annotations
from sqlalchemy.orm import Session
from bookflow_core.services.risk_service import list_risk_warnings, risk_to_dict
from bookflow_core.services.dashboard_service import admin_dashboard, collection_health, circulation_analytics, reader_analytics, risk_analytics, ai_efficiency
from bookflow_core.services.insight_service import overdue_summary, notification_summary, task_summary, rule_summary, reader_detail_summary, dashboard_explanation, full_operational_brief
from bookflow_core.services.circulation_query_service import reader_borrow_summary
from bookflow_core.services.admin_service import admin_security_summary, list_admin_events, list_admins


def ai_get_active_risks(db: Session, payload: dict, *, actor_id: str) -> dict:
    risk_result = list_risk_warnings(db, status="active", limit=int(payload.get("limit", 10)))
    return {"items": [risk_to_dict(r) for r in risk_result["items"]], "total": risk_result["total"]}


def ai_get_risk_warnings(db: Session, payload: dict, *, actor_id: str) -> dict:
    return ai_get_active_risks(db, payload, actor_id=actor_id)


def ai_get_dashboard(db: Session, payload: dict, *, actor_id: str) -> dict:
    return admin_dashboard(db)


def ai_get_collection_health(db: Session, payload: dict, *, actor_id: str) -> dict:
    return collection_health(db)


def ai_get_circulation_analytics(db: Session, payload: dict, *, actor_id: str) -> dict:
    return circulation_analytics(db)


def ai_get_reader_analytics(db: Session, payload: dict, *, actor_id: str) -> dict:
    return reader_analytics(db)


def ai_get_risk_analytics(db: Session, payload: dict, *, actor_id: str) -> dict:
    return risk_analytics(db)


def ai_get_efficiency(db: Session, payload: dict, *, actor_id: str) -> dict:
    return ai_efficiency(db)


def ai_get_overdue_summary(db: Session, payload: dict, *, actor_id: str) -> dict:
    return overdue_summary(db, limit=int(payload.get("limit", 10)))


def ai_get_notification_summary(db: Session, payload: dict, *, actor_id: str) -> dict:
    return notification_summary(db)


def ai_get_task_summary(db: Session, payload: dict, *, actor_id: str) -> dict:
    return task_summary(db)


def ai_get_rule_summary(db: Session, payload: dict, *, actor_id: str) -> dict:
    return rule_summary(db)


def ai_get_reader_detail(db: Session, payload: dict, *, actor_id: str) -> dict:
    return reader_detail_summary(db, reader_code=payload["reader_code"])


def ai_get_reader_borrow_summary(db: Session, payload: dict, *, actor_id: str) -> dict:
    return reader_borrow_summary(db, reader_id=int(payload["reader_id"]))


def ai_get_dashboard_explanation(db: Session, payload: dict, *, actor_id: str) -> dict:
    return dashboard_explanation(db)


def ai_get_operational_brief(db: Session, payload: dict, *, actor_id: str) -> dict:
    return full_operational_brief(db)


def ai_get_admin_security_summary(db: Session, payload: dict, *, actor_id: str) -> dict:
    return admin_security_summary(db)


def ai_get_admin_events(db: Session, payload: dict, *, actor_id: str) -> dict:
    return list_admin_events(db, event_type=payload.get("event_type"), limit=int(payload.get("limit", 20)))


def ai_get_admins(db: Session, payload: dict, *, actor_id: str) -> dict:
    return list_admins(db, is_super_admin=payload.get("is_super_admin"), status=payload.get("status"), keyword=payload.get("keyword"), limit=int(payload.get("limit", 20)))
