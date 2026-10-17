from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from bookflow_core.api.deps import require_reader
from bookflow_core.core.database import get_db
from bookflow_core.models import ReaderAccount
from bookflow_core.schemas.reader_ai import ReaderAIChatRequest
from bookflow_core.services.reader_ai_service import reader_ai_chat, reader_ai_suggestions

router = APIRouter(prefix="/reader-ai", tags=["reader-ai"])


@router.get("/suggestions")
def suggestions(db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return {"success": True, "data": reader_ai_suggestions(db), "message": None}


@router.post("/chat")
def chat(req: ReaderAIChatRequest, db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return {"success": True, "data": reader_ai_chat(db, current_reader, message=req.message, history=req.history), "message": None}
