from __future__ import annotations

from sqlalchemy import delete as sql_delete, select
from sqlalchemy.orm import Session

from bookflow_core.core.exceptions import NotFoundError
from bookflow_core.core.time import now
from bookflow_core.models import AIChatMessage, AIConversation


def _conversation_code() -> str:
    from datetime import datetime, timezone

    return f"CHAT-{int(datetime.now(timezone.utc).timestamp() * 1000000)}"


def ensure_conversation(db: Session, conversation_id: str, actor_id: str) -> AIConversation:
    row = db.scalar(select(AIConversation).where(AIConversation.conversation_code == conversation_id))
    if not row:
        stamp = now()
        row = AIConversation(conversation_code=conversation_id, actor_type="admin", actor_code=actor_id, title="BookFlow AI", created_at=stamp, updated_at=stamp)
        db.add(row)
        db.flush()
    return row


def create_conversation(db: Session, *, actor_id: str, title: str | None = None, commit: bool = True) -> AIConversation:
    try:
        stamp = now()
        row = AIConversation(conversation_code=_conversation_code(), actor_type="admin", actor_code=actor_id, title=title or "BookFlow AI", created_at=stamp, updated_at=stamp)
        db.add(row)
        db.flush()
        if commit:
            db.commit()
            db.refresh(row)
        return row
    except Exception:
        if commit:
            db.rollback()
        raise


def get_conversation(db: Session, conversation_id: str) -> AIConversation:
    row = db.scalar(select(AIConversation).where(AIConversation.conversation_code == conversation_id))
    if not row:
        raise NotFoundError("AI conversation not found.", details={"conversation_id": conversation_id})
    return row


def list_conversations(db: Session, *, actor_id: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    from sqlalchemy import func

    stmt = select(AIConversation)
    if actor_id:
        stmt = stmt.where(AIConversation.actor_code == actor_id)
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = db.scalars(stmt.order_by(AIConversation.updated_at.desc().nullslast(), AIConversation.id.desc()).offset(offset).limit(limit)).all()
    items = []
    for row in rows:
        message_count = int(db.scalar(select(func.count(AIChatMessage.id)).where(AIChatMessage.conversation_id == row.id)) or 0)
        items.append(conversation_to_dict(row, message_count=message_count))
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def conversation_to_dict(row: AIConversation, *, message_count: int | None = None) -> dict:
    return {
        "id": row.id,
        "conversation_id": row.conversation_code,
        "conversation_code": row.conversation_code,
        "title": row.title or "BookFlow AI",
        "actor_type": row.actor_type,
        "actor_code": row.actor_code,
        "message_count": message_count,
        "created_at": str(row.created_at) if row.created_at else "",
        "updated_at": str(row.updated_at) if row.updated_at else "",
    }


def recent_messages(db: Session, conversation_id: str, *, limit: int = 8) -> list[dict]:
    conversation = get_conversation(db, conversation_id)
    rows = db.scalars(
        select(AIChatMessage)
        .where(AIChatMessage.conversation_id == conversation.id)
        .order_by(AIChatMessage.id.desc())
        .limit(limit)
    ).all()
    return [message_to_dict(row) for row in reversed(rows)]


def list_messages(db: Session, conversation_id: str, *, limit: int = 100, offset: int = 0) -> dict:
    from sqlalchemy import func

    conversation = get_conversation(db, conversation_id)
    stmt = select(AIChatMessage).where(AIChatMessage.conversation_id == conversation.id)
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = db.scalars(stmt.order_by(AIChatMessage.id).offset(offset).limit(limit)).all()
    return {"items": [message_to_dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}


def message_to_dict(row: AIChatMessage) -> dict:
    return {
        "id": row.id,
        "role": row.role,
        "content": row.content,
        "created_at": str(row.created_at) if row.created_at else "",
    }


def rename_conversation(db: Session, conversation_id: str, title: str, *, commit: bool = True) -> dict:
    try:
        row = get_conversation(db, conversation_id)
        row.title = title or "BookFlow AI"
        row.updated_at = now()
        if commit:
            db.commit()
            db.refresh(row)
        return conversation_to_dict(row)
    except Exception:
        if commit:
            db.rollback()
        raise


def delete_conversation(db: Session, conversation_id: str, *, commit: bool = True) -> None:
    try:
        row = get_conversation(db, conversation_id)
        db.execute(sql_delete(AIChatMessage).where(AIChatMessage.conversation_id == row.id))
        db.delete(row)
        if commit:
            db.commit()
    except Exception:
        if commit:
            db.rollback()
        raise


def save_message_pair(db: Session, *, conversation_id: str, user_text: str, assistant_text: str) -> None:
    conversation = ensure_conversation(db, conversation_id, actor_id="admin")
    stamp = now()
    db.add(AIChatMessage(conversation_id=conversation.id, role="user", content=user_text, created_at=stamp, updated_at=stamp))
    db.add(AIChatMessage(conversation_id=conversation.id, role="assistant", content=assistant_text, created_at=now(), updated_at=now()))
    conversation.updated_at = now()
