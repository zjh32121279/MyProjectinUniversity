from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from bookflow_core.models import Book, BookCopy, Loan, ReaderAccount, Reservation
from bookflow_core.services.statistics_service import ACTIVE_RESERVATION_STATUSES


def _first_active_reader(db: Session) -> ReaderAccount | None:
    return db.scalar(select(ReaderAccount).where(ReaderAccount.status == "active").order_by(ReaderAccount.id).limit(1))


def _first_available_copy(db: Session, book: Book | None = None) -> BookCopy | None:
    stmt = select(BookCopy).where(BookCopy.copy_status == "available")
    if book is not None:
        stmt = stmt.where(BookCopy.book_id == book.id)
    return db.scalar(stmt.order_by(BookCopy.id).limit(1))


def circulation_operation_state(db: Session, mode: str) -> dict:
    if mode == "borrow":
        reader = _first_active_reader(db)
        copy = _first_available_copy(db)
        book = db.get(Book, copy.book_id) if copy else None
        return {
            "reader_code": reader.reader_code if reader else None,
            "book_code": book.book_code if book else None,
            "copy_code": copy.copy_code if copy else None,
        }
    if mode == "return":
        record = db.scalar(select(Loan).where(Loan.status.in_(["active", "overdue"])).order_by(Loan.borrowed_at.desc()).limit(1))
        copy = db.get(BookCopy, record.copy_id) if record else None
        return {"copy_code": copy.copy_code if copy else None, "loan_id": record.id if record else None}
    if mode == "renew":
        record = db.scalar(select(Loan).where(Loan.status.in_(["active", "overdue"])).order_by(Loan.borrowed_at.desc()).limit(1))
        reader = db.get(ReaderAccount, record.reader_id) if record else _first_active_reader(db)
        copy = db.get(BookCopy, record.copy_id) if record else _first_available_copy(db)
        return {"reader_code": reader.reader_code if reader else None, "copy_code": copy.copy_code if copy else None, "loan_id": record.id if record else None}
    if mode == "reservation":
        reader = _first_active_reader(db)
        reservation_rows = db.scalars(select(Reservation).where(Reservation.status.in_(ACTIVE_RESERVATION_STATUSES)).order_by(Reservation.id).limit(2)).all()
        return {"reader_code": reader.reader_code if reader else None, "reservation_ids": [row.id for row in reservation_rows]}
    return {"error": f"Unknown mode: {mode}"}


