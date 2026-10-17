from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from bookflow_core.core.database import get_db
from bookflow_core.api.deps import require_permission
from bookflow_core.schemas import CreateReaderRequest, UpdateReaderRequest
from bookflow_core.services.reader_service import list_readers, get_reader, create_reader, update_reader, suspend_reader, restore_reader, reader_activity, recent_readers_activity, reader_to_dict, admin_reset_reader_password


class ResetReaderPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=6)
    confirm_password: str = Field(..., min_length=6)


router = APIRouter(prefix="/readers", tags=["readers"])

@router.get("/recent-activity")
def recent_activity(limit: int = Query(20, le=100), db: Session = Depends(get_db)):
    return {"success": True, "data": {"items": recent_readers_activity(db, limit=limit)}, "message": None}

@router.get("")
def readers(reader_type_code: str | None = None, status: str | None = None, credit_status: str | None = None, keyword: str | None = None, limit: int = Query(50, le=200), offset: int = 0, db: Session = Depends(get_db)):
    result = list_readers(db, reader_type_code=reader_type_code, status=status, credit_status=credit_status, keyword=keyword, limit=limit, offset=offset)
    return {"success": True, "data": result, "message": None}

@router.get("/{reader_code}")
def reader_detail(reader_code: str, db: Session = Depends(get_db)):
    return {"success": True, "data": reader_to_dict(get_reader(db, reader_code), db), "message": None}

@router.post("")
def create(req: CreateReaderRequest, db: Session = Depends(get_db), current_admin=Depends(require_permission("readers:write"))):
    row = create_reader(db, reader_code=req.reader_code, name=req.name, reader_type_code=req.reader_type_code, phone_masked=req.phone_masked, email=req.email, actor_id=current_admin.admin_code)
    data = reader_to_dict(row, db)
    data["login_name"] = row.reader_code
    data["initial_password"] = getattr(row, "_initial_password", None)
    return {"success": True, "data": data, "message": None}

@router.put("/{reader_code}")
def update(reader_code: str, req: UpdateReaderRequest, db: Session = Depends(get_db), current_admin=Depends(require_permission("readers:write"))):
    row = update_reader(db, reader_code, name=req.name, reader_type_code=req.reader_type_code, phone_masked=req.phone_masked, email=req.email, status=req.status, actor_id=current_admin.admin_code)
    return {"success": True, "data": reader_to_dict(row, db), "message": None}

@router.post("/{reader_code}/suspend")
def suspend(reader_code: str, req: dict | None = None, db: Session = Depends(get_db), current_admin=Depends(require_permission("readers:write"))):
    req = req or {}
    row = suspend_reader(db, reader_code, reason=req.get("reason", "manual_suspend"), actor_id=current_admin.admin_code)
    return {"success": True, "data": reader_to_dict(row, db), "message": None}

@router.post("/{reader_code}/restore")
def restore(reader_code: str, req: dict | None = None, db: Session = Depends(get_db), current_admin=Depends(require_permission("readers:write"))):
    req = req or {}
    row = restore_reader(db, reader_code, reason=req.get("reason", "manual_restore"), actor_id=current_admin.admin_code)
    return {"success": True, "data": reader_to_dict(row, db), "message": None}

@router.post("/{reader_code}/reset-password")
def reset_password(reader_code: str, req: ResetReaderPasswordRequest, db: Session = Depends(get_db), current_admin=Depends(require_permission("readers:write"))):
    return {
        "success": True,
        "data": admin_reset_reader_password(
            db,
            reader_code=reader_code,
            new_password=req.new_password,
            confirm_password=req.confirm_password,
            actor_id=current_admin.admin_code,
        ),
        "message": "密码已重置",
    }


@router.get("/{reader_code}/activity")
def activity(reader_code: str, db: Session = Depends(get_db)):
    return {"success": True, "data": reader_activity(db, reader_code), "message": None}

