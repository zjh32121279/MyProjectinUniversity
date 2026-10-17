from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from bookflow_core.api.deps import require_permission
from bookflow_core.core.database import get_db
from bookflow_core.services.rule_service import list_borrow_rules, rule_to_dict

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("/borrow")
def borrow_rules(db: Session = Depends(get_db), current_admin=Depends(require_permission("rules:read"))):
    return {"success": True, "data": {"items": [rule_to_dict(row) for row in list_borrow_rules(db)]}, "message": None}
