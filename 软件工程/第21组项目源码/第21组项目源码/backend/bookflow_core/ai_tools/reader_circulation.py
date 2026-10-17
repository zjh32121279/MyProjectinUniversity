from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from bookflow_core.core.exceptions import NotFoundError
from bookflow_core.models import Book, ReaderAccount
from bookflow_core.services.circulation_request_service import (
    create_borrow_request,
    create_renew_request,
    create_reservation_request,
    create_return_request,
    service_request_to_dict,
)


def _reader(db: Session, reader_code: str) -> ReaderAccount:
    row = db.scalar(select(ReaderAccount).where(ReaderAccount.reader_code == reader_code))
    if not row:
        raise NotFoundError("ReaderAccount not found.", code="READER_NOT_FOUND", details={"reader_code": reader_code})
    return row


def _book_id(db: Session, payload: dict) -> int | None:
    if payload.get("book_id"):
        return int(payload["book_id"])
    if payload.get("book_code"):
        book = db.scalar(select(Book).where(Book.book_code == str(payload["book_code"])))
        if not book:
            raise NotFoundError("Book not found.", code="BOOK_NOT_FOUND", details={"book_code": payload.get("book_code")})
        return int(book.id)
    return None


def ai_reader_create_borrow_request(db: Session, payload: dict, *, actor_id: str) -> dict:
    reader = _reader(db, str(payload["reader_code"]))
    row = create_borrow_request(
        db,
        reader,
        book_id=_book_id(db, payload),
        copy_id=int(payload["copy_id"]) if payload.get("copy_id") else None,
        source_type="reader_ai",
        source_actor_type="reader",
        source_actor_id=reader.reader_code,
        ai_plan=payload.get("ai_plan") if isinstance(payload.get("ai_plan"), dict) else None,
        ai_trace=payload.get("ai_trace") if isinstance(payload.get("ai_trace"), dict) else None,
        payload=payload,
        commit=False,
    )
    return service_request_to_dict(row)


def ai_reader_create_return_request(db: Session, payload: dict, *, actor_id: str) -> dict:
    reader = _reader(db, str(payload["reader_code"]))
    row = create_return_request(
        db,
        reader,
        loan_id=int(payload["loan_id"]) if payload.get("loan_id") else None,
        copy_code=str(payload["copy_code"]) if payload.get("copy_code") else None,
        source_type="reader_ai",
        source_actor_type="reader",
        source_actor_id=reader.reader_code,
        ai_plan=payload.get("ai_plan") if isinstance(payload.get("ai_plan"), dict) else None,
        ai_trace=payload.get("ai_trace") if isinstance(payload.get("ai_trace"), dict) else None,
        payload=payload,
        commit=False,
    )
    return service_request_to_dict(row)


def ai_reader_create_reservation(db: Session, payload: dict, *, actor_id: str) -> dict:
    reader = _reader(db, str(payload["reader_code"]))
    book_id = _book_id(db, payload)
    if book_id is None:
        raise NotFoundError("Book not found.", code="BOOK_NOT_FOUND", details={"payload": payload})
    row = create_reservation_request(
        db,
        reader,
        book_id=book_id,
        source_type="reader_ai",
        source_actor_type="reader",
        source_actor_id=reader.reader_code,
        ai_plan=payload.get("ai_plan") if isinstance(payload.get("ai_plan"), dict) else None,
        ai_trace=payload.get("ai_trace") if isinstance(payload.get("ai_trace"), dict) else None,
        payload=payload,
        commit=False,
    )
    return service_request_to_dict(row)


def ai_reader_renew_borrow(db: Session, payload: dict, *, actor_id: str) -> dict:
    reader = _reader(db, str(payload["reader_code"]))
    row = create_renew_request(
        db,
        reader,
        loan_id=int(payload["loan_id"]),
        source_type="reader_ai",
        source_actor_type="reader",
        source_actor_id=reader.reader_code,
        ai_plan=payload.get("ai_plan") if isinstance(payload.get("ai_plan"), dict) else None,
        ai_trace=payload.get("ai_trace") if isinstance(payload.get("ai_trace"), dict) else None,
        payload=payload,
        commit=False,
    )
    return service_request_to_dict(row)
