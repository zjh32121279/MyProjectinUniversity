from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from bookflow_core.core.database import get_db
from bookflow_core.services.analytics_service import (
    get_admin_dashboard,
    get_analytics_overview,
    get_collection_health,
    get_circulation_analytics,
    get_reader_analytics,
    get_ai_efficiency,
)
from bookflow_core.services.insight_service import task_summary, full_operational_brief

router = APIRouter(prefix="", tags=["dashboard"])

@router.get("/dashboard/admin")
def dashboard(business_date: str | None = None, db: Session = Depends(get_db)):
    return {"success": True, "data": get_admin_dashboard(db, business_date=business_date), "message": None}

@router.get("/analytics/overview")
def overview(business_date: str | None = None, db: Session = Depends(get_db)):
    return {"success": True, "data": get_analytics_overview(db, business_date=business_date), "message": None}

@router.get("/analytics/collection-health")
def collection(business_date: str | None = None, db: Session = Depends(get_db)):
    return {"success": True, "data": get_collection_health(db, business_date=business_date), "message": None}

@router.get("/analytics/circulation")
def circulation(business_date: str | None = None, limit: int = 10, db: Session = Depends(get_db)):
    return {"success": True, "data": get_circulation_analytics(db, business_date=business_date, limit=limit), "message": None}

@router.get("/analytics/readers")
def readers(business_date: str | None = None, db: Session = Depends(get_db)):
    return {"success": True, "data": get_reader_analytics(db, business_date=business_date), "message": None}


@router.get("/analytics/ai-efficiency")
def ai(business_date: str | None = None, db: Session = Depends(get_db)):
    return {"success": True, "data": get_ai_efficiency(db, business_date=business_date), "message": None}


@router.get("/analytics/tasks")
def task_stats(db: Session = Depends(get_db)):
    return {"success": True, "data": task_summary(db), "message": None}

@router.get("/analytics/brief")
def brief(db: Session = Depends(get_db)):
    return {"success": True, "data": full_operational_brief(db), "message": None}
