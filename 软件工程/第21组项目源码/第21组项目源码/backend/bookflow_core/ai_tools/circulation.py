from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.orm import Session
from bookflow_core.models import Loan
from bookflow_core.services.circulation_query_service import list_loans, list_overdue_cases, list_reservations
from bookflow_core.services.circulation_service import borrow_copy, cancel_reservation, create_reservation, fulfill_reservation, renew_borrow, return_copy, scan_overdues
from bookflow_core.services.common import create_snapshot


def ai_borrow_copy(db: Session, payload: dict, *, actor_id: str) -> dict:
    record = borrow_copy(db, reader_code=payload["reader_code"], copy_code=payload["copy_code"], actor_type="ai_admin", actor_id=actor_id, commit=False)
    return {"loan_id": record.id, "due_at": str(record.due_at)}


def ai_return_copy(db: Session, payload: dict, *, actor_id: str) -> dict:
    record = return_copy(db, copy_code=payload["copy_code"], actor_type="ai_admin", actor_id=actor_id, commit=False)
    return {"loan_id": record.id, "status": record.status}


def ai_renew_borrow(db: Session, payload: dict, *, actor_id: str) -> dict:
    record = db.get(Loan, payload["loan_id"])
    before = {"loan_id": record.id, "due_at": str(record.due_at), "renewal_count": record.renewal_count} if record else {}
    renewal = renew_borrow(db, loan_id=payload["loan_id"], actor_type="ai_admin", actor_id=actor_id, commit=False)
    updated = db.get(Loan, payload["loan_id"])
    after = {"loan_id": updated.id, "due_at": str(updated.due_at), "renewal_count": updated.renewal_count}
    create_snapshot(db, action_type="ai_renew_borrow", target_table="loans", target_id=str(updated.id), before=before, after=after, actor_type="ai_admin", actor_id=actor_id, can_rollback=False)
    return {"renewal_id": renewal.id, "loan_id": updated.id, "new_due_at": str(updated.due_at)}


def ai_cancel_reservation(db: Session, payload: dict, *, actor_id: str) -> dict:
    row = cancel_reservation(db, reservation_id=payload["reservation_id"], actor_type="ai_admin", actor_id=actor_id, commit=False)
    return {"reservation_id": row.id, "status": row.status}


def ai_get_loans(db: Session, payload: dict, *, actor_id: str) -> dict:
    return list_loans(
        db,
        status=payload.get("status"),
        reader_id=payload.get("reader_id"),
        book_id=payload.get("book_id"),
        copy_id=payload.get("copy_id"),
        keyword=payload.get("keyword"),
        limit=int(payload.get("limit", 20)),
        offset=int(payload.get("offset", 0)),
    )


def ai_get_overdue_cases(db: Session, payload: dict, *, actor_id: str) -> dict:
    return list_overdue_cases(
        db,
        status=payload.get("status", "active"),
        min_overdue_days=payload.get("min_overdue_days"),
        max_overdue_days=payload.get("max_overdue_days"),
        reader_keyword=payload.get("reader_keyword"),
        book_keyword=payload.get("book_keyword"),
        limit=int(payload.get("limit", 20)),
        offset=int(payload.get("offset", 0)),
    )


def ai_get_reservations(db: Session, payload: dict, *, actor_id: str) -> dict:
    return list_reservations(
        db,
        status=payload.get("status"),
        reader_id=payload.get("reader_id"),
        book_id=payload.get("book_id"),
        copy_id=payload.get("copy_id"),
        keyword=payload.get("keyword"),
        limit=int(payload.get("limit", 20)),
        offset=int(payload.get("offset", 0)),
    )


def ai_create_reservation(db: Session, payload: dict, *, actor_id: str) -> dict:
    row = create_reservation(db, reader_code=payload["reader_code"], book_code=payload["book_code"], actor_type="ai_admin", actor_id=actor_id, commit=False)
    return {"reservation_id": row.id, "reservation_code": row.reservation_code, "status": row.status, "fulfilled_copy_id": row.fulfilled_copy_id}


def ai_fulfill_reservation(db: Session, payload: dict, *, actor_id: str) -> dict:
    record = fulfill_reservation(db, reservation_id=payload["reservation_id"], actor_type="ai_admin", actor_id=actor_id, commit=False)
    return {"loan_id": record.id, "loan_code": record.loan_code, "status": record.status, "due_at": str(record.due_at)}


def ai_scan_overdues(db: Session, payload: dict, *, actor_id: str) -> dict:
    count = scan_overdues(db, actor_type="ai_admin", actor_id=actor_id, commit=False)
    return {"overdue_count": count}
