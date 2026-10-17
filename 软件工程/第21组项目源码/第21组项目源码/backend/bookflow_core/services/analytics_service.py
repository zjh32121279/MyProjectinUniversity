from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

import bookflow_core.services.dashboard_service as dashboard_service


def get_admin_dashboard(db: Session, *, business_date: date | str | None = None) -> dict:
    return dashboard_service.admin_dashboard(db, business_date=business_date, generate_home_ai_summary=True)


def get_analytics_overview(db: Session, *, business_date: date | str | None = None) -> dict:
    return dashboard_service.analytics_overview(db, business_date=business_date)


def get_collection_health(db: Session, *, business_date: date | str | None = None) -> dict:
    return dashboard_service.collection_health(db, business_date=business_date)


def get_circulation_analytics(db: Session, *, business_date: date | str | None = None, limit: int = 10) -> dict:
    return dashboard_service.circulation_analytics(db, business_date=business_date, limit=limit)


def get_reader_analytics(db: Session, *, business_date: date | str | None = None) -> dict:
    return dashboard_service.reader_analytics(db, business_date=business_date)


def get_risk_analytics(db: Session, *, business_date: date | str | None = None) -> dict:
    return dashboard_service.risk_analytics(db, business_date=business_date)


def get_ai_efficiency(db: Session, *, business_date: date | str | None = None) -> dict:
    return dashboard_service.ai_efficiency(db, business_date=business_date)
