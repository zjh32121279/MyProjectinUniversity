from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import or_, select, func
from sqlalchemy.orm import Session

from bookflow_core.core.exceptions import NotFoundError
from bookflow_core.models import Book, BookCopy, CirculationRule, CirculationServiceRequest, Loan, OverdueCase, ReaderAccount, ReaderCreditEvent, Reservation, ShelfPosition
from bookflow_core.services.circulation_service import _normalize_circulation_type, _normalize_reader_type
from bookflow_core.services.reader_service import reader_borrow_suspended
from bookflow_core.services.statistics_service import get_business_date


LOAN_STATUS_ALIASES = {
    "borrowed": ["active"],
    "active": ["active"],
    "renewable": ["active", "overdue"],
    "overdue": ["overdue"],
    "returned": ["returned", "returned_overdue"],
}

RESERVATION_STATUS_ALIASES = {
    "active": ["waiting", "ready_for_pickup"],
    "reserved": ["ready_for_pickup"],
    "ready": ["ready_for_pickup"],
    "ready_for_pickup": ["ready_for_pickup"],
    "waiting": ["waiting"],
    "fulfilled": ["fulfilled"],
    "cancelled": ["cancelled"],
    "expired": ["expired"],
}


def _page(items: list[dict], total: int, limit: int, offset: int) -> dict:
    data = {"items": items, "total": int(total), "limit": limit, "offset": offset}
    if total == 0:
        data["empty_state"] = True
    return data


def _date_only(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()




def _copy_location_text(copy: BookCopy | None) -> str | None:
    if not copy:
        return None
    # shelf_position may be a ShelfPosition ORM object (relationship override)
    shelf_pos = copy.shelf_position
    if isinstance(shelf_pos, ShelfPosition):
        layer = f"第{shelf_pos.layer_no}层" if shelf_pos.layer_no else ""
        side_raw = (shelf_pos.side or "").strip()
        side_label = {"左": "左侧", "右": "右侧", "中": "中间", "left": "左侧", "right": "右侧", "middle": "中间"}.get(side_raw, f"{side_raw}侧" if side_raw else "")
        shelf_pos_text = f"{layer}{side_label}" if (layer or side_label) else shelf_pos.position_code
    else:
        shelf_pos_text = str(shelf_pos) if shelf_pos else None
    home_pos_text = copy.home_shelf_position
    parts = [
        copy.current_zone_code or copy.home_zone_code,
        copy.shelf_code or copy.home_shelf_code,
        shelf_pos_text or home_pos_text,
    ]
    text = " · ".join(str(item) for item in parts if item)
    return text or None

def renew_state_for_loan(db: Session, record: Loan, reader: ReaderAccount, book: Book) -> dict:
    if record.status not in {"active", "overdue"}:
        return {"can_renew": False, "renew_blocked_reason": "这条借阅记录已经结束，不能续借。"}
    if reader_borrow_suspended(reader) or reader.status != "active":
        return {"can_renew": False, "renew_blocked_reason": "当前账号借阅权限暂停，不能续借。"}

    rule = db.scalar(
        select(CirculationRule).where(
            CirculationRule.reader_type_code == _normalize_reader_type(reader.reader_type_code),
            CirculationRule.circulation_type == _normalize_circulation_type(book.circulation_type),
            CirculationRule.is_active == True,
        )
    )
    if not rule:
        return {"can_renew": False, "renew_blocked_reason": "当前读者类型没有可用的续借规则。"}

    max_renewals = int(rule.max_renewals or 0)
    renewal_count = int(record.renewal_count or 0)
    if renewal_count >= max_renewals:
        return {"can_renew": False, "renew_blocked_reason": "已达到最大续借次数。", "max_renewals": max_renewals}
    return {"can_renew": True, "renew_blocked_reason": None, "max_renewals": max_renewals}


def loan_to_dict(db: Session, record: Loan, reader: ReaderAccount, book: Book, copy: BookCopy, *, as_of: date) -> dict:
    overdue_days = 0
    due_at = _date_only(record.due_at)
    borrowed_at = _date_only(record.borrowed_at)
    returned_at = _date_only(record.returned_at)
    if record.status in {"active", "overdue"} and due_at and due_at < as_of:
        overdue_days = (as_of - due_at).days
    renew_state = renew_state_for_loan(db, record, reader, book)
    return {
        "loan_id": record.id,
        "renewal_count": record.renewal_count,
        **renew_state,
        "reader_code": reader.reader_code,
        "reader_name": reader.name,
        "reader_type_code": reader.reader_type_code,
        "reader": {"id": reader.id, "reader_code": reader.reader_code, "name": reader.name, "reader_type_code": reader.reader_type_code},
        "book_code": book.book_code,
        "title": book.title,
        "author": book.author,
        "cover_url": book.cover_url,
        "circulation_type": book.circulation_type,
        "book": {"id": book.id, "book_code": book.book_code, "title": book.title, "author": book.author, "cover_url": book.cover_url, "circulation_type": book.circulation_type},
        "copy_code": copy.copy_code,
        "copy": {"id": copy.id, "copy_code": copy.copy_code, "copy_status": copy.copy_status},
        "location": _copy_location_text(copy),
        "borrowed_at": str(borrowed_at),
        "due_at": str(due_at),
        "returned_at": str(returned_at) if returned_at else None,
        "status": record.status,
        "overdue_days": overdue_days,
        "handled_by": {"admin_id": record.handled_by_admin_id, "admin_code": record.handled_by_code},
    }


def list_loans(
    db: Session,
    *,
    status: str | None = None,
    reader_id: int | None = None,
    book_id: int | None = None,
    copy_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    keyword: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    stmt = select(Loan, ReaderAccount, Book, BookCopy).join(ReaderAccount, Loan.reader_id == ReaderAccount.id).join(Book, Loan.book_id == Book.id).join(BookCopy, Loan.copy_id == BookCopy.id)
    if status:
        stmt = stmt.where(Loan.status.in_(LOAN_STATUS_ALIASES.get(status, [status])))
    if reader_id is not None:
        stmt = stmt.where(Loan.reader_id == reader_id)
    if book_id is not None:
        stmt = stmt.where(Loan.book_id == book_id)
    if copy_id is not None:
        stmt = stmt.where(Loan.copy_id == copy_id)
    if start_date is not None:
        stmt = stmt.where(func.date(Loan.borrowed_at) >= str(start_date))
    if end_date is not None:
        stmt = stmt.where(func.date(Loan.borrowed_at) <= str(end_date))
    if keyword:
        stmt = stmt.where(or_(ReaderAccount.reader_code.contains(keyword), ReaderAccount.name.contains(keyword), Book.book_code.contains(keyword), Book.title.contains(keyword), BookCopy.copy_code.contains(keyword)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.order_by(Loan.id.desc()).offset(offset).limit(limit)).all()
    as_of = get_business_date(db)
    return _page([loan_to_dict(db, record, reader, book, copy, as_of=as_of) for record, reader, book, copy in rows], total, limit, offset)


def overdue_case_to_dict(row: OverdueCase, reader: ReaderAccount, book: Book, copy: BookCopy, *, as_of: date) -> dict:
    overdue_start = _date_only(row.overdue_start_at)
    overdue_days = (as_of - overdue_start).days + 1 if row.status == "active" and overdue_start else row.overdue_days
    return {
        "overdue_case_id": row.id,
        "reader": {"id": reader.id, "reader_code": reader.reader_code, "name": reader.name},
        "book": {"id": book.id, "book_code": book.book_code, "title": book.title},
        "copy": {"id": copy.id, "copy_code": copy.copy_code},
        "overdue_start_date": str(overdue_start),
        "overdue_days": max(0, overdue_days),
        "penalty_score": row.penalty_score,
        "status": row.status,
    }


def list_overdue_cases(
    db: Session,
    *,
    status: str | None = None,
    min_overdue_days: int | None = None,
    max_overdue_days: int | None = None,
    reader_keyword: str | None = None,
    book_keyword: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    stmt = select(OverdueCase, ReaderAccount, Book, BookCopy).join(ReaderAccount, OverdueCase.reader_id == ReaderAccount.id).join(BookCopy, OverdueCase.copy_id == BookCopy.id).join(Book, BookCopy.book_id == Book.id)
    if status:
        stmt = stmt.where(OverdueCase.status == status)
    if min_overdue_days is not None:
        stmt = stmt.where(OverdueCase.overdue_days >= min_overdue_days)
    if max_overdue_days is not None:
        stmt = stmt.where(OverdueCase.overdue_days <= max_overdue_days)
    if reader_keyword:
        stmt = stmt.where(or_(ReaderAccount.reader_code.contains(reader_keyword), ReaderAccount.name.contains(reader_keyword)))
    if book_keyword:
        stmt = stmt.where(or_(Book.book_code.contains(book_keyword), Book.title.contains(book_keyword), BookCopy.copy_code.contains(book_keyword)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.order_by(OverdueCase.id.desc()).offset(offset).limit(limit)).all()
    as_of = get_business_date(db)
    return _page([overdue_case_to_dict(row, reader, book, copy, as_of=as_of) for row, reader, book, copy in rows], total, limit, offset)


def reservation_to_dict(row: Reservation, reader: ReaderAccount, book: Book, copy: BookCopy | None) -> dict:
    return {
        "reservation_id": row.id,
        "reader": {"id": reader.id, "reader_code": reader.reader_code, "name": reader.name},
        "book": {"id": book.id, "book_code": book.book_code, "title": book.title},
        "copy": {"id": copy.id, "copy_code": copy.copy_code} if copy else None,
        "location": _copy_location_text(copy),
        "status": row.status,
        "reserved_until": str(row.reserved_until) if row.reserved_until else None,
        "created_at": str(row.created_at),
        "created_by": {"admin_id": row.created_by_admin_id, "admin_code": row.created_by_code},
    }


def list_reservations(
    db: Session,
    *,
    status: str | None = None,
    reader_id: int | None = None,
    book_id: int | None = None,
    copy_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    keyword: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    stmt = select(Reservation, ReaderAccount, Book, BookCopy).join(ReaderAccount, Reservation.reader_id == ReaderAccount.id).join(Book, Reservation.book_id == Book.id).outerjoin(BookCopy, Reservation.fulfilled_copy_id == BookCopy.id)
    if status:
        stmt = stmt.where(Reservation.status.in_(RESERVATION_STATUS_ALIASES.get(status, [status])))
    if reader_id is not None:
        stmt = stmt.where(Reservation.reader_id == reader_id)
    if book_id is not None:
        stmt = stmt.where(Reservation.book_id == book_id)
    if copy_id is not None:
        stmt = stmt.where(Reservation.fulfilled_copy_id == copy_id)
    if start_date is not None:
        stmt = stmt.where(func.date(Reservation.created_at) >= str(start_date))
    if end_date is not None:
        stmt = stmt.where(func.date(Reservation.created_at) <= str(end_date))
    if keyword:
        stmt = stmt.where(or_(ReaderAccount.reader_code.contains(keyword), ReaderAccount.name.contains(keyword), Book.book_code.contains(keyword), Book.title.contains(keyword), BookCopy.copy_code.contains(keyword)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.order_by(Reservation.id.desc()).offset(offset).limit(limit)).all()
    return _page([reservation_to_dict(row, reader, book, copy) for row, reader, book, copy in rows], total, limit, offset)


def pending_request_to_dict(row: CirculationServiceRequest, reader: ReaderAccount, book: Book | None, copy: BookCopy | None) -> dict:
    return {
        "id": row.id,
        "request_code": row.request_code,
        "voucher_code": row.voucher_code,
        "request_type": row.request_type,
        "status": row.status,
        "source_type": row.source_type,
        "source_actor_type": row.source_actor_type,
        "source_actor_id": row.source_actor_id,
        "reader_id": row.reader_id,
        "reader_code": row.reader_code,
        "book_id": row.book_id,
        "book_code": row.book_code,
        "copy_id": row.copy_id,
        "copy_code": row.copy_code,
        "loan_id": row.loan_id,
        "loan_code": row.loan_code,
        "reservation_id": row.reservation_id,
        "reservation_code": row.reservation_code,
        "task_code": row.task_code,
        "expires_at": str(row.expires_at) if row.expires_at else None,
        "completed_at": str(row.completed_at) if row.completed_at else None,
        "cancelled_at": str(row.cancelled_at) if row.cancelled_at else None,
        "handled_by_code": row.handled_by_code,
        "created_at": str(row.created_at) if row.created_at else None,
        "updated_at": str(row.updated_at) if row.updated_at else None,
        "reader": {"id": reader.id, "reader_code": reader.reader_code, "name": reader.name, "reader_type_code": reader.reader_type_code},
        "book": {"id": book.id, "book_code": book.book_code, "title": book.title, "circulation_type": book.circulation_type} if book else None,
        "copy": {"id": copy.id, "copy_code": copy.copy_code, "copy_status": copy.copy_status} if copy else None,
        "location": _copy_location_text(copy),
    }


def list_pending_requests(
    db: Session,
    *,
    reader_id: int | None = None,
    keyword: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    statuses = ["ready"]
    if status:
        statuses = [status]
    stmt = (
        select(CirculationServiceRequest, ReaderAccount, Book, BookCopy)
        .join(ReaderAccount, CirculationServiceRequest.reader_id == ReaderAccount.id)
        .outerjoin(Book, CirculationServiceRequest.book_id == Book.id)
        .outerjoin(BookCopy, CirculationServiceRequest.copy_id == BookCopy.id)
        .where(CirculationServiceRequest.status.in_(statuses))
        .where(CirculationServiceRequest.request_type == "borrow")
    )
    if reader_id is not None:
        stmt = stmt.where(CirculationServiceRequest.reader_id == reader_id)
    if keyword:
        stmt = stmt.where(
            or_(
                CirculationServiceRequest.voucher_code.contains(keyword),
                CirculationServiceRequest.request_code.contains(keyword),
                CirculationServiceRequest.reader_code.contains(keyword),
                ReaderAccount.name.contains(keyword),
                Book.book_code.contains(keyword),
                Book.title.contains(keyword),
                BookCopy.copy_code.contains(keyword),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.order_by(CirculationServiceRequest.id.desc()).offset(offset).limit(limit)).all()
    return _page([pending_request_to_dict(row, reader, book, copy) for row, reader, book, copy in rows], total, limit, offset)


def reader_borrow_summary(db: Session, reader_id: int) -> dict:
    reader = db.get(ReaderAccount, reader_id)
    if not reader:
        raise NotFoundError("ReaderAccount not found.", code="READER_NOT_FOUND", details={"reader_id": reader_id})
    current = list_loans(db, reader_id=reader.id, status="active", limit=100, offset=0)["items"]
    overdue = list_loans(db, reader_id=reader.id, status="overdue", limit=100, offset=0)["items"]
    history = list_loans(db, reader_id=reader.id, status="returned", limit=100, offset=0)["items"]
    reservations = list_reservations(db, reader_id=reader.id, limit=100, offset=0)["items"]
    credit_events = db.scalars(select(ReaderCreditEvent).where(ReaderCreditEvent.reader_id == reader.id).order_by(ReaderCreditEvent.id.desc()).limit(20)).all()
    return {
        "reader": {
            "id": reader.id,
            "reader_code": reader.reader_code,
            "name": reader.name,
            "reader_type_code": reader.reader_type_code,
            "credit_score": reader.credit_score,
            "borrow_suspended_until": reader.borrow_suspended_until,
            "borrow_suspended": reader_borrow_suspended(reader),
            "status": reader.status,
        },
        "current_borrows": current,
        "historical_borrows": history,
        "current_overdues": overdue,
        "reservations": reservations,
        "credit_events": [
            {
                "event_id": event.id,
                "delta": event.delta,
                "old_score": event.old_score,
                "new_score": event.new_score,
                "reason": event.reason,
                "created_at": event.created_at,
            }
            for event in credit_events
        ],
    }
