from __future__ import annotations

from sqlalchemy.orm import Session

from bookflow_core.ai.chat.conversation_memory import (
    conversation_to_dict,
    create_conversation,
    delete_conversation,
    list_conversations,
    list_messages,
    rename_conversation,
)
from bookflow_core.ai.chat.chat_service import chat as chat_service


def chat(db: Session, *, conversation_id: str, text: str, actor_id: str = "admin", commit: bool = True, llm_client=None) -> dict:
    return chat_service(db, conversation_id=conversation_id, text=text, actor_id=actor_id, commit=commit, llm_client=llm_client)


def create_ai_conversation(db: Session, *, actor_id: str, title: str | None = None) -> dict:
    return conversation_to_dict(create_conversation(db, actor_id=actor_id, title=title))


def list_ai_conversations(db: Session, *, actor_id: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    return list_conversations(db, actor_id=actor_id, limit=limit, offset=offset)


def list_ai_messages(db: Session, *, conversation_id: str, limit: int = 100, offset: int = 0) -> dict:
    return list_messages(db, conversation_id, limit=limit, offset=offset)


__all__ = [
    "chat",
    "create_ai_conversation",
    "list_ai_conversations",
    "list_ai_messages",
]
