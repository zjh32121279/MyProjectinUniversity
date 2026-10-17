from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from bookflow_core.api.deps import get_current_admin
from bookflow_core.core.database import get_db
from bookflow_core.services.admin_portal_service import circulation_operation_state

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/circulation/operation-state")
def operation_state(mode: str, db: Session = Depends(get_db), current_admin=Depends(get_current_admin)):
    return {"success": True, "data": circulation_operation_state(db, mode), "message": None}
