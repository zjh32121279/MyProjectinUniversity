from __future__ import annotations

from datetime import date, datetime, timedelta

import hashlib

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from bookflow_core.core.exceptions import BookFlowError
from bookflow_core.core.security import hash_password, verify_password
from bookflow_core.core.time import now
from bookflow_core.models import (
    Book,
    BookCirculationStats,
    BookCopy,
    CirculationRule,
    CirculationServiceRequest,
    Loan,
    ReaderAccount,
    ReaderCredential,
    ReaderCreditEvent,
    ReaderLoginEvent,
    ReaderPreference,
    Reservation,
    ReservationEvent,
    SystemSetting,
)
from bookflow_core.services.catalog_service import copy_to_dict, recalculate_book_inventory
from bookflow_core.services.circulation_query_service import RESERVATION_STATUS_ALIASES, _copy_location_text, list_loans, list_reservations, renew_state_for_loan
from bookflow_core.services.circulation_service import get_reservation_hold_days, renew_borrow
from bookflow_core.services.common import utc_text, write_audit, write_status_event
from bookflow_core.services.public_catalog_service import library_profile, list_public_books, list_public_categories

import json
from bookflow_core.services.reader_auth_service import current_reader_to_dict, get_reader_notification_settings, upsert_reader_notification_settings
from bookflow_core.services.statistics_service import ACTIVE_RESERVATION_STATUSES, get_business_date

READER_TYPE_LABELS = {
    "child": "儿童读者",
    "teen": "青少年读者",
    "adult": "成人读者",
    "senior": "老年读者",
    "institution": "机构读者",
}

READER_STATUS_LABELS = {
    "active": "正常",
    "inactive": "停用",
    "suspended": "暂停借阅",
}


def _date_only(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _reader_type_name(reader: ReaderAccount) -> str:
    raw_name = str(reader.reader_type_name or "").strip()
    if raw_name and raw_name != reader.reader_type_code:
        return raw_name
    return READER_TYPE_LABELS.get(str(reader.reader_type_code or ""), raw_name or "普通读者")


def _status_name(status: str | None) -> str:
    return READER_STATUS_LABELS.get(str(status or ""), str(status or "—"))


def _setting_value(db: Session, key: str, fallback: str) -> str:
    value = db.scalar(select(SystemSetting.setting_value).where(SystemSetting.setting_key == key, SystemSetting.is_active == True))
    return str(value or fallback)


def _account_hash(value: str | None) -> str | None:
    text_value = str(value or "").strip()
    return hashlib.sha256(text_value.encode("utf-8")).hexdigest() if text_value else None


def _stat_total(db: Session, model, *conditions) -> int:
    return int(db.scalar(select(func.count(model.id)).where(*conditions)) or 0)


def _profile_item(label: str, value, *, description: str | None = None) -> dict:
    return {"label": label, "value": value if value not in (None, "") else "—", **({"description": description} if description else {})}


def get_reader_preferences(db: Session, reader: ReaderAccount) -> dict:
    row = db.scalar(select(ReaderPreference).where(ReaderPreference.reader_id == reader.id))
    if row:
        try:
            codes = json.loads(row.favorite_category_codes or "[]")
        except (json.JSONDecodeError, TypeError):
            codes = []
        return {
            "favorite_category_codes": codes,
            "recommendation_source": row.recommendation_source or "both",
        }
    return {"favorite_category_codes": [], "recommendation_source": "both"}


def update_reader_preferences(
    db: Session,
    reader: ReaderAccount,
    *,
    favorite_category_codes: list[str] | None = None,
    recommendation_source: str | None = None,
) -> dict:
    row = db.scalar(select(ReaderPreference).where(ReaderPreference.reader_id == reader.id))
    if not row:
        row = ReaderPreference(reader_id=reader.id)
        db.add(row)
    if favorite_category_codes is not None:
        row.favorite_category_codes = json.dumps(favorite_category_codes, ensure_ascii=False)
    if recommendation_source is not None:
        row.recommendation_source = recommendation_source
    db.commit()
    return get_reader_preferences(db, reader)


def borrow_history(db: Session, reader: ReaderAccount, limit: int = 50, offset: int = 0) -> list[dict]:
    rows = db.execute(
        select(Loan, Book, BookCopy)
        .join(Book, Loan.book_id == Book.id)
        .outerjoin(BookCopy, Loan.copy_id == BookCopy.id)
        .where(Loan.reader_id == reader.id)
        .order_by(Loan.borrowed_at.desc().nullslast())
        .offset(offset)
        .limit(limit)
    ).all()
    return [
        {
            "loan_id": loan.id,
            "book_id": book.id,
            "title": book.title,
            "author": book.author,
            "cover_url": book.cover_url,
            "borrowed_at": str(loan.borrowed_at) if loan.borrowed_at else None,
            "returned_at": str(loan.returned_at) if loan.returned_at else None,
            "due_at": str(loan.due_at) if loan.due_at else None,
            "status": loan.status,
            "copy_code": copy.copy_code if copy else None,
            "copy_id": copy.id if copy else None,
        }
        for loan, book, copy in rows
    ]


def _book_recommendations(db: Session, reader: ReaderAccount, *, limit: int = 12) -> list[dict]:
    prefs = get_reader_preferences(db, reader)
    source = prefs.get("recommendation_source", "both")
    fav_codes = prefs.get("favorite_category_codes", [])

    if source == "popular" or not fav_codes:
        data = list_public_books(db, circulation_type="热门", sort="popular", page=1, page_size=limit)
        return data["items"]
    elif source == "preference":
        books: list[dict] = []
        per_cat = max(3, limit // max(1, len(fav_codes)))
        for code in fav_codes:
            result = list_public_books(db, category=code, sort="popular", page=1, page_size=per_cat)
            books.extend(result["items"])
        return books[:limit]
    else:  # "both" — 热门 + 偏好混合
        hot = list_public_books(db, circulation_type="热门", sort="popular", page=1, page_size=limit // 2)["items"]
        pref: list[dict] = []
        if fav_codes:
            per_cat = max(2, (limit - len(hot)) // max(1, min(3, len(fav_codes))))
            for code in fav_codes[:3]:
                result = list_public_books(db, category=code, sort="popular", page=1, page_size=per_cat)
                pref.extend(result["items"])
        return (hot + pref)[:limit]


def reader_profile(reader: ReaderAccount, db: Session) -> dict:
    data = current_reader_to_dict(reader, db)
    data["reader_type_name"] = _reader_type_name(reader)
    data["status_name"] = _status_name(reader.status)
    return data


def reader_stats(db: Session, reader: ReaderAccount) -> dict:
    as_of = get_business_date(db)
    due_limit = as_of + timedelta(days=7)
    current = int(db.scalar(select(func.count(Loan.id)).where(Loan.reader_id == reader.id, Loan.status.in_(["active", "overdue"]))) or 0)
    active_reservations = int(db.scalar(select(func.count(Reservation.id)).where(Reservation.reader_id == reader.id, Reservation.status.in_(ACTIVE_RESERVATION_STATUSES))) or 0)
    due_reminders = int(
        db.scalar(
            select(func.count(Loan.id)).where(
                Loan.reader_id == reader.id,
                Loan.status.in_(["active", "overdue"]),
                Loan.due_at <= due_limit,
            )
        )
        or 0
    )
    history = int(db.scalar(select(func.count(Loan.id)).where(Loan.reader_id == reader.id, Loan.status == "returned")) or 0)
    return {
        "current_borrows": current,
        "active_reservations": active_reservations,
        "due_reminders": due_reminders,
        "history_borrows": history,
        "credit_score": reader.credit_score,
    }


def borrow_summary(db: Session, reader: ReaderAccount) -> dict:
    stats = reader_stats(db, reader)
    renewable_rows = db.execute(
        select(Loan, Book)
        .join(Book, Loan.book_id == Book.id)
        .where(
            Loan.reader_id == reader.id,
            Loan.status.in_(["active", "overdue"]),
        )
    ).all()
    renewable = sum(1 for loan, book in renewable_rows if renew_state_for_loan(db, loan, reader, book)["can_renew"])
    return {
        "current": stats["current_borrows"],
        "dueSoon": stats["due_reminders"],
        "overdue": int(db.scalar(select(func.count(Loan.id)).where(Loan.reader_id == reader.id, Loan.status == "overdue")) or 0),
        "renewable": renewable,
    }


def reader_home(db: Session, reader: ReaderAccount) -> dict:
    stats = reader_stats(db, reader)
    return {
        "library": library_profile(db),
        "categories": list_public_categories(db),
        "recommendations": _book_recommendations(db, reader, limit=12),
        "recent_notifications": notifications(db, reader, status="unread", limit=4, offset=0)["items"],
        "borrow_summary": {
            "current_count": stats["current_borrows"],
            "due_this_week": stats["due_reminders"],
            "reservation_count": stats["active_reservations"],
            "credit_score": stats["credit_score"],
        },
        "due_soon": due_reminders(db, reader),
    }


def borrows(db: Session, reader: ReaderAccount, *, status: str | None = None, limit: int = 20, offset: int = 0) -> dict:
    return list_loans(db, status=status or "renewable", reader_id=reader.id, limit=limit, offset=offset)


def due_reminders(db: Session, reader: ReaderAccount) -> list[dict]:
    as_of = get_business_date(db)
    due_limit = as_of + timedelta(days=7)
    data = list_loans(db, reader_id=reader.id, limit=100, offset=0)
    return [
        item
        for item in data["items"]
        if item.get("status") in {"active", "overdue"}
        and (due := _date_only(item.get("due_at"))) is not None
        and due <= due_limit
    ]


def renew_reader_borrow(db: Session, reader: ReaderAccount, loan_id: int) -> dict:
    loan = db.get(Loan, loan_id)
    if not loan or loan.reader_id != reader.id:
        raise BookFlowError("不能续借其他读者的借阅记录。", code="BORROW_RENEW_NOT_ALLOWED")
    book = db.get(Book, loan.book_id)
    if not book:
        raise BookFlowError("图书记录不存在，不能续借。", code="BORROW_RENEW_NOT_ALLOWED")
    renew_state = renew_state_for_loan(db, loan, reader, book)
    if not renew_state["can_renew"]:
        raise BookFlowError(renew_state["renew_blocked_reason"] or "这条借阅记录不能续借。", code="BORROW_RENEW_NOT_ALLOWED")
    event = renew_borrow(db, loan_id=loan_id, actor_type="reader", actor_id=reader.reader_code)
    return {
        "renewal_id": event.id,
        "loan_id": loan_id,
        "old_due_at": str(event.old_due_at) if getattr(event, "old_due_at", None) else None,
        "new_due_at": str(event.new_due_at) if getattr(event, "new_due_at", None) else None,
    }


def borrow_rules(db: Session, reader: ReaderAccount) -> dict | None:
    rows = db.scalars(
        select(CirculationRule)
        .where(CirculationRule.reader_type_code == reader.reader_type_code, CirculationRule.is_active == True)
        .order_by(CirculationRule.circulation_type)
    ).all()
    if not rows:
        return None
    return {
        "reader_type_code": reader.reader_type_code,
        "reader_type_name": _reader_type_name(reader),
        "items": [
            {
                "circulation_type": row.circulation_type,
                "max_borrow_count": row.max_borrow_count,
                "borrow_days": row.borrow_days,
                "max_renewals": row.max_renewals,
            }
            for row in rows
        ],
    }


def reservation_rules(db: Session, reader: ReaderAccount) -> dict | None:
    rows = db.scalars(
        select(CirculationRule)
        .where(CirculationRule.reader_type_code == reader.reader_type_code, CirculationRule.is_active == True)
        .order_by(CirculationRule.circulation_type)
    ).all()
    if not rows:
        return {
            "reader_type_code": reader.reader_type_code,
            "reader_type_name": _reader_type_name(reader),
            "reservation_limit": 0,
            "hold_days": 3,
            "items": [],
        }
    limits = [int(row.reservation_limit or 0) for row in rows if row.reservation_limit is not None]
    return {
        "reader_type_code": reader.reader_type_code,
        "reader_type_name": _reader_type_name(reader),
        "reservation_limit": max(limits or [0]),
        "hold_days": 3,
        "items": [
            {
                "circulation_type": row.circulation_type,
                "reservation_limit": row.reservation_limit,
                "borrow_days": row.borrow_days,
                "max_renewals": row.max_renewals,
            }
            for row in rows
        ],
        "statuses": [
            {"status": "waiting", "label": "排队中"},
            {"status": "ready_for_pickup", "label": "待取书"},
            {"status": "fulfilled", "label": "已完成"},
            {"status": "cancelled", "label": "已取消"},
            {"status": "expired", "label": "已失效"},
        ],
    }


def _csr_borrow_to_dict(row: CirculationServiceRequest, reader: ReaderAccount, book: Book, copy: BookCopy | None) -> dict:
    return {
        "reservation_id": None,
        "request_code": row.request_code,
        "voucher_code": row.voucher_code,
        "request_type": row.request_type,
        "reader": {"id": reader.id, "reader_code": reader.reader_code, "name": reader.name},
        "book": {"id": book.id, "book_code": book.book_code, "title": book.title},
        "copy": {"id": copy.id, "copy_code": copy.copy_code} if copy else None,
        "location": _copy_location_text(copy),
        "status": "ready_for_pickup" if row.status == "ready" else row.status,
        "reserved_until": str(row.expires_at) if row.expires_at else None,
        "created_at": str(row.created_at),
        "created_by": {"admin_code": row.handled_by_code},
        "pickup_code_available": bool(row.voucher_code),
    }


def reservations(db: Session, reader: ReaderAccount, *, status: str | None = None, limit: int = 20, offset: int = 0) -> dict:
    data = list_reservations(db, status=status, reader_id=reader.id, limit=limit, offset=offset)
    items = list(data["items"])
    total = int(data["total"])

    # Also include borrow circulation service requests (readers see them as reservations)
    csr_stmt = (
        select(CirculationServiceRequest, Book, BookCopy)
        .join(Book, CirculationServiceRequest.book_id == Book.id)
        .outerjoin(BookCopy, CirculationServiceRequest.copy_id == BookCopy.id)
        .where(
            CirculationServiceRequest.reader_id == reader.id,
            CirculationServiceRequest.request_type == "borrow",
            CirculationServiceRequest.status.in_(["ready", "pending"]),
        )
        .order_by(CirculationServiceRequest.id.desc())
    )
    csr_rows = db.execute(csr_stmt).all()
    for csr, book, copy in csr_rows:
        csr_item = _csr_borrow_to_dict(csr, reader, book, copy)
        if status:
            requested_statuses = RESERVATION_STATUS_ALIASES.get(status, [status])
            if csr_item["status"] not in requested_statuses:
                continue
        items.append(csr_item)
        total += 1

    # Re-sort by created_at descending
    items.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    # Apply pagination at the end
    paginated = items[offset : offset + limit] if offset < len(items) else []
    result = {"items": paginated, "total": total, "limit": limit, "offset": offset}
    if total == 0:
        result["empty_state"] = True
    return result


def reservation_summary(db: Session, reader: ReaderAccount) -> dict:
    data = reservations(db, reader, limit=500, offset=0)
    items = data["items"]
    active = [item for item in items if item.get("status") in ACTIVE_RESERVATION_STATUSES]
    ready = [item for item in active if item.get("status") == "ready_for_pickup"]
    history = [item for item in items if item.get("status") not in ACTIVE_RESERVATION_STATUSES]
    return {
        "active": len(active),
        "ready": len(ready),
        "expiring": len([item for item in active if item.get("reserved_until")]),
        "history": len(history),
    }


def pickup_reminders(db: Session, reader: ReaderAccount) -> list[dict]:
    data = reservations(db, reader, status="ready_for_pickup", limit=100, offset=0)
    return data["items"]


def _reservation_code() -> str:
    return f"RSV-{int(datetime.utcnow().timestamp() * 1000000)}"


def create_reader_reservation(db: Session, reader: ReaderAccount, *, book_id: int | None = None, copy_id: int | None = None) -> dict:
    if book_id is None and copy_id is None:
        raise BookFlowError("book_id or copy_id is required.", code="VALIDATION_ERROR")
    copy = db.get(BookCopy, copy_id) if copy_id is not None else None
    if copy_id is not None and not copy:
        raise BookFlowError("Copy not found.", code="COPY_NOT_FOUND", details={"copy_id": copy_id})
    book = db.get(Book, copy.book_id if copy else book_id)
    if not book:
        raise BookFlowError("Book not found.", code="BOOK_NOT_FOUND", details={"book_id": book_id})
    if copy is None:
        copy = db.scalar(select(BookCopy).where(BookCopy.book_id == book.id, BookCopy.copy_status == "available").order_by(BookCopy.id))
    business_day = get_business_date(db)
    status = "waiting"
    reserved_until = None
    fulfilled_copy_id = None
    if copy and copy.copy_status == "available":
        old_status = copy.copy_status
        copy.copy_status = "reserved"
        status = "ready_for_pickup"
        reserved_until = business_day + timedelta(days=get_reservation_hold_days(db))
        fulfilled_copy_id = copy.id
        write_status_event(db, copy, old_status, "reserved", "create_reader_reservation", "reader", reader.reader_code)
    row = Reservation(
        reservation_code=_reservation_code(),
        reader_id=reader.id,
        book_id=book.id,
        status=status,
        requested_at=now(),
        reserved_until=reserved_until,
        fulfilled_copy_id=fulfilled_copy_id,
        created_by_code=reader.reader_code,
        created_at=now(),
        updated_at=now(),
    )
    db.add(row)
    stats = db.scalar(select(BookCirculationStats).where(BookCirculationStats.book_id == book.id))
    if stats:
        stats.reserve_90d = (stats.reserve_90d or 0) + 1
    write_audit(db, actor_type="reader", actor_id=reader.reader_code, action="create_reader_reservation", target_table="reservations", target_id=book.book_code)
    db.flush()
    db.add(ReservationEvent(reservation_id=row.id, event_type="created", actor_code=reader.reader_code, event_time=utc_text(), detail=f"book_code={book.book_code};status={row.status}"))
    recalculate_book_inventory(db, book.id)
    from bookflow_core.ai.kernel.intake import create_business_event_task

    create_business_event_task(
        db,
        action="create_reader_reservation",
        title="Reader reservation created",
        priority="normal",
        task_group="reservation",
        related_entity_type="reservation",
        related_entity_id=str(row.id),
        payload={"reader_code": reader.reader_code, "book_id": book.id, "book_code": book.book_code, "status": row.status, "copy_id": fulfilled_copy_id},
        actor_type="reader",
        actor_id=reader.reader_code,
        commit=False,
    )
    db.commit()
    return {"reservation_id": row.id, "status": row.status, "fulfilled_copy_id": row.fulfilled_copy_id}


def cancel_reader_reservation(db: Session, reader: ReaderAccount, reservation_id: int) -> dict:
    row = db.get(Reservation, reservation_id)
    if not row or row.reader_id != reader.id:
        raise BookFlowError("不能取消其他读者的预约。", code="RESERVATION_CANCEL_NOT_ALLOWED")
    if row.status not in ACTIVE_RESERVATION_STATUSES:
        raise BookFlowError("当前预约不能取消。", code="RESERVATION_CANCEL_NOT_ALLOWED")
    copy_id = row.fulfilled_copy_id
    if copy_id:
        copy = db.get(BookCopy, copy_id)
        if copy and copy.copy_status == "reserved":
            old_status = copy.copy_status
            copy.copy_status = "available"
            write_status_event(db, copy, old_status, "available", "cancel_reader_reservation", "reader", reader.reader_code)
            recalculate_book_inventory(db, copy.book_id)
    previous_status = row.status
    row.status = "cancelled"
    row.updated_at = now()
    db.add(ReservationEvent(reservation_id=row.id, event_type="cancelled", actor_code=reader.reader_code, event_time=utc_text(), detail=f"previous_status={previous_status}"))
    write_audit(db, actor_type="reader", actor_id=reader.reader_code, action="cancel_reader_reservation", target_table="reservations", target_id=str(row.id))
    from bookflow_core.ai.kernel.intake import create_business_event_task

    create_business_event_task(
        db,
        action="cancel_reader_reservation",
        title="Reader reservation cancelled",
        priority="normal",
        task_group="reservation",
        related_entity_type="reservation",
        related_entity_id=str(row.id),
        payload={"reader_code": reader.reader_code, "reservation_id": row.id, "previous_status": previous_status},
        actor_type="reader",
        actor_id=reader.reader_code,
        commit=False,
    )
    db.commit()
    return {"reservation_id": row.id, "status": row.status}


def pickup_code(db: Session, reader: ReaderAccount, reservation_id: int) -> dict | None:
    row = db.get(Reservation, reservation_id)
    if not row or row.reader_id != reader.id:
        raise BookFlowError("Reservation not found.", code="RESOURCE_NOT_FOUND")
    if row.status != "ready_for_pickup":
        raise BookFlowError("预约仍在排队中，到书后会生成取书码。", code="RESERVATION_NOT_READY")
    if not row.fulfilled_copy_id:
        raise BookFlowError("尚未分配副本，请联系馆员。", code="RESERVATION_NO_COPY")
    copy = db.get(BookCopy, row.fulfilled_copy_id)
    from datetime import datetime, timezone
    voucher = f"PU{int(datetime.now(timezone.utc).timestamp() * 1000) % 100000000:08d}"
    return {
        "reservation_id": row.id,
        "reservation_code": row.reservation_code,
        "voucher_code": voucher,
        "copy_code": copy.copy_code if copy else None,
        "copy_location": copy_to_dict(db, copy)["location"] if copy else None,
        "reserved_until": str(row.reserved_until) if row.reserved_until else None,
        "status": row.status,
    }


def _favorite_categories(db: Session, reader: ReaderAccount) -> list[dict]:
    loan_rows = db.execute(
        select(Book.category_code, Book.category_name, func.count(Loan.id))
        .join(Book, Loan.book_id == Book.id)
        .where(Loan.reader_id == reader.id)
        .group_by(Book.category_code, Book.category_name)
    ).all()
    reservation_rows = db.execute(
        select(Book.category_code, Book.category_name, func.count(Reservation.id))
        .join(Book, Reservation.book_id == Book.id)
        .where(Reservation.reader_id == reader.id)
        .group_by(Book.category_code, Book.category_name)
    ).all()
    scores: dict[str, dict] = {}
    for code, name, count in [*loan_rows, *reservation_rows]:
        key = str(code or name or "unknown")
        item = scores.setdefault(key, {"category_code": code, "category_name": name or code or "未分类", "count": 0})
        item["count"] += int(count or 0)
    return sorted(scores.values(), key=lambda item: item["count"], reverse=True)[:6]


def _profile_section(key: str, group: str, title: str, summary: str, items: list[dict], *, actions: list[dict] | None = None) -> dict:
    return {
        "key": key,
        "group": group,
        "title": title,
        "summary": summary,
        "items": items,
        "actions": actions or [],
    }


def profile_center(db: Session, reader: ReaderAccount) -> dict:
    profile = reader_profile(reader, db)
    settings = get_reader_notification_settings(db, reader) or upsert_reader_notification_settings(
        db,
        reader,
        {
            "borrow_due_enabled": True,
            "reservation_arrival_enabled": True,
            "system_notice_enabled": True,
            "email_enabled": bool(reader.email),
        },
    )
    borrow_rule = borrow_rules(db, reader)
    reservation_rule = reservation_rules(db, reader)
    stats = reader_stats(db, reader)
    reservation_stats = reservation_summary(db, reader)
    returned_count = _stat_total(db, Loan, Loan.reader_id == reader.id, Loan.status == "returned")
    credit_events = db.scalars(select(ReaderCreditEvent).where(ReaderCreditEvent.reader_id == reader.id).order_by(ReaderCreditEvent.id.desc()).limit(5)).all()
    login_events = db.scalars(select(ReaderLoginEvent).where(ReaderLoginEvent.reader_id == reader.id).order_by(ReaderLoginEvent.id.desc()).limit(5)).all()
    credential = db.scalar(select(ReaderCredential).where(ReaderCredential.reader_id == reader.id).order_by(ReaderCredential.id))
    library = library_profile(db) or {}
    favorite_categories = _favorite_categories(db, reader)
    prefs = get_reader_preferences(db, reader)
    all_categories = list_public_categories(db)
    fav_codes = prefs.get("favorite_category_codes", [])
    rec_source = prefs.get("recommendation_source", "both")
    rec_source_label = {"popular": "热门馆藏", "preference": "基于偏好分类", "both": "热门馆藏 + 偏好分类"}.get(rec_source, "热门馆藏 + 偏好分类")
    selected_names = [c["name"] for c in all_categories if c.get("code") in fav_codes]
    sections = [
        _profile_section(
            "basic_info",
            "完善个人信息",
            "基本信息",
            "读者身份、联系方式与账户状态",
            [
                _profile_item("姓名", reader.name),
                _profile_item("读者证号", reader.reader_code),
                _profile_item("读者类型", _reader_type_name(reader)),
                _profile_item("账户状态", _status_name(reader.status)),
                _profile_item("手机号", reader.phone_masked),
                _profile_item("邮箱", reader.email),
                _profile_item("注册时间", str(reader.registered_at or reader.created_at) if (reader.registered_at or reader.created_at) else None),
            ],
            actions=[{"type": "contact_form", "label": "更新手机号/邮箱"}],
        ),
        _profile_section(
            "pickup_point",
            "完善个人信息",
            "常用取书点",
            "根据预约和馆藏位置生成默认取书说明",
            [
                _profile_item("默认取书点", "服务台 / 预约保留区"),
                _profile_item("待取预约", reservation_stats["ready"]),
                _profile_item("当前说明", "到书后系统会在预约记录中显示取书截止日期和副本信息"),
            ],
            actions=[{"type": "navigate", "label": "查看我的预约", "to": "/reservations"}],
        ),
        _profile_section(
            "identity_info",
            "完善个人信息",
            "证件信息",
            "读者证和借阅资格信息",
            [
                _profile_item("读者证号", reader.reader_code),
                _profile_item("来源编号", reader.source_reader_id),
                _profile_item("信用分", profile.get("credit_score")),
                _profile_item("借阅暂停", "是" if profile.get("borrow_suspended") else "否"),
            ],
        ),
        _profile_section(
            "change_password",
            "账号与安全",
            "修改密码",
            "使用当前密码修改登录密码",
            [
                _profile_item("登录账号", credential.login_name if credential else reader.reader_code),
                _profile_item("凭据状态", credential.status if credential else "暂无凭据"),
                _profile_item("上次登录", str(credential.last_login_at) if credential and credential.last_login_at else "暂无记录"),
            ],
            actions=[{"type": "password_form", "label": "修改密码"}],
        ),
        _profile_section(
            "bind_phone",
            "账号与安全",
            "绑定手机号",
            "维护本人手机号和邮箱",
            [
                _profile_item("当前手机号", reader.phone_masked),
                _profile_item("当前邮箱", reader.email),
                _profile_item("用途", "登录、通知和馆员联系"),
            ],
            actions=[{"type": "contact_form", "label": "更新联系方式"}],
        ),
        _profile_section(
            "login_devices",
            "账号与安全",
            "登录设备管理",
            "最近登录记录",
            [
                _profile_item("最近登录次数", len(login_events)),
                *[
                    _profile_item(str(event.created_at) if event.created_at else "登录记录", event.result or event.event_type or "—", description=event.ip_address or None)
                    for event in login_events
                ],
            ],
        ),
        _profile_section(
            "notification_settings",
            "系统设置",
            "消息通知设置",
            "借阅、预约、系统通知开关",
            [
                _profile_item(item.get("label", item.get("key")), "开" if item.get("enabled") else "关")
                for item in settings.get("items", [])
            ],
            actions=[{"type": "navigate", "label": "打开通知中心设置", "to": "/notifications"}],
        ),
        _profile_section(
            "privacy_settings",
            "系统设置",
            "隐私设置",
            "个人资料展示和通知隐私",
            [
                _profile_item("联系方式展示", "仅本人账号页显示完整值"),
                _profile_item("馆员可见范围", "读者服务和借阅处理所需信息"),
                _profile_item("通知内容", "系统只展示与本人借阅、预约、公告相关消息"),
            ],
        ),
        _profile_section(
            "general_settings",
            "系统设置",
            "通用设置",
            "界面和服务默认项",
            [
                _profile_item("语言", "简体中文"),
                _profile_item("日期格式", "YYYY-MM-DD"),
                _profile_item("默认入口", "首页"),
            ],
        ),
        _profile_section(
            "favorite_categories",
            "阅读偏好",
            "感兴趣的分类",
            "选择感兴趣的一级分类，首页推荐将优先展示这些分类的图书",
            [
                _profile_item("已选分类", "、".join(selected_names) if selected_names else "尚未选择，点击编辑"),
                _profile_item("可选分类数", len(all_categories)),
            ],
            actions=[{"type": "category_select", "label": "编辑偏好分类"}],
        ),
        _profile_section(
            "reading_history",
            "阅读偏好",
            "阅读历史",
            "查看借阅时间线与信用记录",
            [
                _profile_item("历史借阅", returned_count),
                _profile_item("当前借阅", stats["current_borrows"]),
                _profile_item("逾期记录", stats["due_reminders"]),
            ],
            actions=[{"type": "borrow_history", "label": "查看借阅历史"}],
        ),
        _profile_section(
            "recommendation_settings",
            "阅读偏好",
            "推荐设置",
            "选择首页推荐策略：热门图书、偏好分类，或两者混合",
            [
                _profile_item("当前策略", rec_source_label),
                _profile_item("偏好分类数", len(fav_codes)),
            ],
            actions=[{"type": "recommendation_select", "label": "修改推荐策略"}],
        ),
        _profile_section(
            "feedback",
            "反馈与帮助",
            "意见反馈",
            "提交问题或建议给馆员",
            [
                _profile_item("反馈对象", library.get("name") or library.get("library_name") or "图书馆"),
                _profile_item("服务邮箱", library.get("service_email")),
            ],
            actions=[{"type": "feedback_form", "label": "提交反馈"}],
        ),
        _profile_section(
            "faq",
            "反馈与帮助",
            "常见问题",
            "读者端常用操作说明",
            [
                _profile_item("如何找书", "在找书页搜索书名、作者或分类，点击定位取书"),
                _profile_item("何时预约", "没有可借副本时可预约，系统会排队或保留副本"),
                _profile_item("如何续借", "在我的借阅中点击可续借记录的续借按钮"),
            ],
        ),
        _profile_section(
            "contact_service",
            "反馈与帮助",
            "联系客服",
            "馆内服务联系方式",
            [
                _profile_item("服务电话", library.get("service_phone") or library.get("phone")),
                _profile_item("服务邮箱", library.get("service_email")),
                _profile_item("开放时间", library.get("opening_hours")),
            ],
        ),
        _profile_section(
            "about_bookflow",
            "关于我们",
            "关于 BookFlow",
            "BookFlow Core 图书馆读者服务系统",
            [
                _profile_item("系统架构", "FastAPI + React + SQLite，前后端分离，支持 Windows / Linux 部署"),
                _profile_item("服务对象", "公共图书馆、高校图书馆、社区图书馆读者及馆员"),
                _profile_item("核心能力", "在线书目检索、馆内平面地图与书架定位、借阅续借、预约排队、到期与逾期自动提醒、AI 辅助编目与任务调度"),
                _profile_item("读者端功能", "首页概览、找书与地图定位、我的借阅、我的预约、通知中心、个人中心与信用分"),
                _profile_item("数据来源", "馆藏书目由后台导入或馆员编目维护，流通策略与借阅规则由馆员在普管端配置"),
            ],
        ),
        _profile_section(
            "terms",
            "关于我们",
            "服务条款",
            "使用本系统即视为已阅读并同意以下条款",
            [
                _profile_item("读者类型", f"本馆按读者类型（儿童、青少年、成人、老年、机构）分别设置最大可借册数、借阅天数与续借次数，具体数值以普管端\"流通规则\"为准"),
                _profile_item("热门与冷门", f"近 90 天借阅或预约达到阈值的图书标记为\"热门\"，缩短借期；近 365 天低借阅且长期未流通的标记为\"冷门\"，可正常借阅"),
                _profile_item("预约取书", f"无可用副本时读者可提交预约，到书后系统发送通知，保留取书期限以流通策略中的预约保留天数为准，超时未取自动取消"),
                _profile_item("逾期暂停", "任一借阅逾期未还期间，账号自动暂停借阅权限，归还所有逾期图书后即时恢复"),
                _profile_item("信用分", "系统依据借阅归还及时性、逾期次数与严重程度自动计算读者信用分，信用分过低可能影响借阅额度"),
                _profile_item("行为规范", "读者须使用本人真实身份注册登录，妥善保管账号密码，不得转借、转让或利用本系统从事违法违规活动"),
                _profile_item("服务变更", "系统升级维护可能短暂影响访问，流通规则变更将在通知中心提前公告，重大调整须经馆员审批后生效"),
            ],
        ),
        _profile_section(
            "privacy_policy",
            "关于我们",
            "隐私政策",
            "依据《个人信息保护法》说明信息处理规则",
            [
                _profile_item("收集内容", "注册与登录所需的姓名与读者证号，借阅与预约产生的业务记录，通知投递所需的联系方式（手机号或邮箱）"),
                _profile_item("手机号保护", "完整手机号经哈希处理后存储，读者端仅展示掩码（如 138****1234），馆员端经授权方可查看脱敏值"),
                _profile_item("数据存储", "所有数据存储于馆内或指定服务器，借阅与预约记录保留至还书或取消后不少于 2 年，日志定期归档"),
                _profile_item("安全措施", "登录密码加密存储（SHA-256 + 盐值），API 传输强制 HTTPS，数据库访问基于角色权限控制，关键操作写入审计日志"),
                _profile_item("第三方接入", "本系统未集成第三方统计或广告 SDK，不向馆外机构共享、转让或公开披露读者个人信息"),
                _profile_item("用户权利", "读者可在本页面更新联系方式与通知偏好，可申请查询、更正或删除个人信息，可随时注销账号"),
                _profile_item("政策更新", "隐私政策如有重大变更，将在系统通知中心以消息形式推送，并在登录页公示更新日期"),
            ],
        ),
    ]
    return {
        "profile": profile,
        "summary": {
            "borrow": {**stats, "history_borrows": returned_count},
            "reservation": reservation_stats,
            "notification_settings": settings,
        },
        "sections": sections,
    }


def update_reader_contact(db: Session, reader: ReaderAccount, *, phone: str | None = None, email: str | None = None) -> dict:
    phone_value = str(phone or "").strip()
    email_value = str(email or "").strip()
    if phone is not None:
        reader.phone_masked = phone_value or None
        reader.phone_hash = _account_hash(phone_value)
    if email is not None:
        reader.email = email_value or None
    credential = db.scalar(select(ReaderCredential).where(ReaderCredential.reader_id == reader.id).order_by(ReaderCredential.id))
    if credential:
        if phone is not None:
            credential.phone_hash = _account_hash(phone_value)
        if email is not None:
            credential.email = email_value or None
        credential.updated_at = now()
    reader.updated_at = now()
    write_audit(db, actor_type="reader", actor_id=reader.reader_code, action="update_reader_contact", target_table="reader_accounts", target_id=reader.reader_code)
    db.commit()
    return reader_profile(reader, db)


def change_reader_password(db: Session, reader: ReaderAccount, *, old_password: str, new_password: str, confirm_password: str) -> dict:
    if not new_password or len(new_password) < 6:
        raise BookFlowError("新密码至少需要 6 位。", code="VALIDATION_ERROR")
    if new_password != confirm_password:
        raise BookFlowError("两次输入的新密码不一致。", code="VALIDATION_ERROR")
    credential = db.scalar(select(ReaderCredential).where(ReaderCredential.reader_id == reader.id).order_by(ReaderCredential.id))
    if not credential or not verify_password(old_password, credential.password_hash):
        raise BookFlowError("当前密码不正确。", code="VALIDATION_ERROR")
    credential.password_hash = hash_password(new_password)
    credential.updated_at = now()
    write_audit(db, actor_type="reader", actor_id=reader.reader_code, action="change_reader_password", target_table="reader_credentials", target_id=str(credential.id))
    db.commit()
    return {"changed": True}


def submit_reader_feedback(db: Session, reader: ReaderAccount, *, category: str | None, content: str) -> dict:
    text_value = str(content or "").strip()
    if len(text_value) < 4:
        raise BookFlowError("反馈内容至少需要 4 个字。", code="VALIDATION_ERROR")
    write_audit(
        db,
        actor_type="reader",
        actor_id=reader.reader_code,
        action="submit_reader_feedback",
        target_table="reader_feedback",
        target_id=reader.reader_code,
        detail={"category": category or "general", "content": text_value[:500]},
    )
    db.commit()
    return {"submitted": True, "category": category or "general"}


def _delivery_to_dict(row, reader: ReaderAccount, db: Session) -> dict:
    """将投递记录转为读者端字典。"""
    from bookflow_core.services.notification_service import delivery_to_dict
    return delivery_to_dict(row, db)


def notifications(
    db: Session,
    reader: ReaderAccount,
    *,
    status: str | None = None,
    notification_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """读者通知列表 —— 使用 NotificationDelivery 模型。
    只显示已发送且未归档的投递记录。
    status 参数映射: unread -> read_status='unread', read -> read_status='read'
    """
    from bookflow_core.models import NotificationDelivery, NotificationMessage

    stmt = select(NotificationDelivery).where(
        NotificationDelivery.recipient_type == "reader",
        NotificationDelivery.recipient_id == reader.id,
        NotificationDelivery.delivery_status == "sent",
        NotificationDelivery.archived_at == None,
    )
    if status:
        read_status_map = {"unread": "unread", "read": "read"}
        mapped = read_status_map.get(status, status)
        if mapped in ("unread", "read"):
            stmt = stmt.where(NotificationDelivery.read_status == mapped)
    if notification_type:
        msg_ids = select(NotificationMessage.id).where(
            NotificationMessage.notification_type == notification_type
        )
        stmt = stmt.where(NotificationDelivery.message_id.in_(msg_ids))

    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = db.scalars(
        stmt.order_by(NotificationDelivery.id.desc()).offset(offset).limit(limit)
    ).all()
    return {
        "items": [_delivery_to_dict(row, reader, db) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        **({"empty_state": True} if total == 0 else {}),
    }


def notification_summary(db: Session, reader: ReaderAccount) -> dict:
    """读者通知概览 —— 基于 NotificationDelivery 统计。"""
    from bookflow_core.services.notification_service import reader_delivery_summary
    return reader_delivery_summary(db, reader.id)


def notification_overview(db: Session, reader: ReaderAccount) -> dict:
    return {
        "summary": notification_summary(db, reader),
        "latest": notifications(db, reader, limit=5, offset=0)["items"],
    }


def mark_notification_read(
    db: Session, reader: ReaderAccount, notification_id: int
) -> dict:
    """读者标记单条通知已读 —— 按 delivery id 操作，校验归属。"""
    from bookflow_core.services.notification_service import mark_delivery_read

    return mark_delivery_read(
        db,
        notification_id,
        recipient_type="reader",
        recipient_id=reader.id,
        actor_type="reader",
        actor_id=reader.reader_code,
    )


def mark_all_notifications_read(
    db: Session, reader: ReaderAccount
) -> dict:
    """读者一键全部标为已读。"""
    from bookflow_core.services.notification_service import (
        mark_all_reader_deliveries_read,
    )

    return mark_all_reader_deliveries_read(
        db,
        reader.id,
        actor_type="reader",
        actor_id=reader.reader_code,
    )


def clear_read_notifications(db: Session, reader: ReaderAccount) -> dict:
    """读者清空已读 —— 归档已读投递，不物理删除。"""
    from bookflow_core.services.notification_service import (
        archive_read_reader_deliveries,
    )

    return archive_read_reader_deliveries(
        db,
        reader.id,
        actor_type="reader",
        actor_id=reader.reader_code,
    )


def notification_settings(db: Session, reader: ReaderAccount) -> dict | None:
    return get_reader_notification_settings(db, reader) or upsert_reader_notification_settings(
        db,
        reader,
        {
            "borrow_due_enabled": True,
            "reservation_arrival_enabled": True,
            "system_notice_enabled": True,
            "email_enabled": bool(reader.email),
        },
    )


def update_notification_settings(db: Session, reader: ReaderAccount, updates: dict[str, bool]) -> dict:
    return upsert_reader_notification_settings(db, reader, updates)
