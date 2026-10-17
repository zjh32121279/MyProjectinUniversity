from __future__ import annotations

from sqlalchemy.orm import Session

from bookflow_core.services.reader_service import (
    adjust_credit,
    list_readers,
    reader_activity,
    reader_to_dict,
    restore_reader,
    suspend_reader,
)


def ai_get_readers(db: Session, payload: dict, *, actor_id: str) -> dict:
    return list_readers(
        db,
        reader_type_code=payload.get("reader_type_code"),
        status=payload.get("status"),
        credit_status=payload.get("credit_status"),
        keyword=payload.get("keyword"),
        limit=int(payload.get("limit", 50)),
        offset=int(payload.get("offset", 0)),
    )


def ai_get_reader_activity(db: Session, payload: dict, *, actor_id: str) -> dict:
    return reader_activity(db, reader_code=payload["reader_code"])


def ai_adjust_reader_credit(db: Session, payload: dict, *, actor_id: str) -> dict:
    event = adjust_credit(
        db,
        payload["reader_code"],
        delta=int(payload["delta"]),
        reason=payload.get("reason", "ai_adjust"),
        actor_type="ai_admin",
        actor_id=actor_id,
        related_loan_id=payload.get("related_loan_id"),
        commit=False,
    )
    return {"event_id": event.id, "delta": event.delta, "old_score": event.old_score, "new_score": event.new_score, "reason": event.reason}


def ai_suspend_reader(db: Session, payload: dict, *, actor_id: str) -> dict:
    reader = suspend_reader(db, payload["reader_code"], reason=payload.get("reason", "ai_suspend"), actor_type="ai_admin", actor_id=actor_id, commit=False)
    return reader_to_dict(reader, db)


def ai_restore_reader(db: Session, payload: dict, *, actor_id: str) -> dict:
    reader = restore_reader(db, payload["reader_code"], reason=payload.get("reason", "ai_restore"), actor_type="ai_admin", actor_id=actor_id, commit=False)
    return reader_to_dict(reader, db)
