from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from bookflow_core.ai.engine.openai_compatible_client import ai_engine_status
from bookflow_core.api.deps import require_permission
from bookflow_core.core.database import get_db
from bookflow_core.schemas import AIChatRequest
from bookflow_core.services.ai_service import (
    chat,
    create_ai_conversation,
    delete_conversation,
    list_ai_conversations,
    list_ai_messages,
    rename_conversation,
)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat")
def ai_chat(req: AIChatRequest, db: Session = Depends(get_db), current_admin=Depends(require_permission("ai:chat"))):
    return {"success": True, "data": chat(db, conversation_id=req.conversation_id, text=req.text, actor_id=current_admin.admin_code), "message": None}


@router.get("/conversations")
def conversations(limit: int = Query(50, le=100), offset: int = 0, db: Session = Depends(get_db), current_admin=Depends(require_permission("ai:chat"))):
    return {"success": True, "data": list_ai_conversations(db, actor_id=current_admin.admin_code, limit=limit, offset=offset), "message": None}


@router.post("/conversations")
def create_conversation(body: dict | None = None, db: Session = Depends(get_db), current_admin=Depends(require_permission("ai:chat"))):
    body = body or {}
    return {"success": True, "data": create_ai_conversation(db, actor_id=current_admin.admin_code, title=body.get("title")), "message": None}


@router.get("/conversations/{conversation_code}/messages")
def conversation_messages(conversation_code: str, limit: int = Query(100, le=200), offset: int = 0, db: Session = Depends(get_db), current_admin=Depends(require_permission("ai:chat"))):
    return {"success": True, "data": list_ai_messages(db, conversation_id=conversation_code, limit=limit, offset=offset), "message": None}


@router.put("/conversations/{conversation_code}")
def rename_conversation_endpoint(conversation_code: str, body: dict, db: Session = Depends(get_db), current_admin=Depends(require_permission("ai:chat"))):
    title = str(body.get("title", "") or "BookFlow AI")
    return {"success": True, "data": rename_conversation(db, conversation_code, title), "message": "已重命名"}


@router.delete("/conversations/{conversation_code}")
def delete_conversation_endpoint(conversation_code: str, db: Session = Depends(get_db), current_admin=Depends(require_permission("ai:chat"))):
    delete_conversation(db, conversation_code)
    return {"success": True, "data": None, "message": "已删除"}


@router.get("/engine/status")
def ai_engine_status_endpoint(probe: bool = Query(False), current_admin=Depends(require_permission("ai:chat"))):
    return {"success": True, "data": ai_engine_status(probe=probe), "message": None}
