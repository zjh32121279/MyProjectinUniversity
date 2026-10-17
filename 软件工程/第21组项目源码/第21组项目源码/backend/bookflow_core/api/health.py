from __future__ import annotations
from fastapi import APIRouter
router = APIRouter(prefix="/health", tags=["health"])

@router.get("")
def health():
    return {"success": True, "data": {"status": "ok", "service": "bookflow_core"}, "message": None}
