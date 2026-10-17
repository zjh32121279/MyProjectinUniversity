from __future__ import annotations

from datetime import date, datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from bookflow_core.core.exceptions import NotFoundError, BusinessRuleError
from bookflow_core.models import (
    ReaderAccount, Book, BookCopy, Loan, Reservation, LoanEvent, ReservationEvent, OverdueCase,
    ReaderStatusEvent, CirculationServiceRequest, NotificationDelivery, NotificationMessage,
    CirculationRule, CirculationPolicy, SystemSetting, ReaderCreditEvent,
)
from bookflow_core.services.common import write_audit, write_status_event, utc_text, create_snapshot
from bookflow_core.services.catalog_service import get_copy_by_code, get_or_create_book_stats, recalculate_book_inventory
from bookflow_core.services.reader_service import reader_borrow_suspended
from bookflow_core.services.statistics_service import ACTIVE_RESERVATION_STATUSES, get_business_date


def get_reservation_hold_days(db: Session) -> int:
    policy = db.scalar(select(CirculationPolicy).where(CirculationPolicy.is_active == True).order_by(CirculationPolicy.id.desc()))
    if policy and policy.reservation_hold_days:
        return int(policy.reservation_hold_days)
    return 3


def _enqueue_business_event(
    db: Session,
    *,
    action: str,
    title: str,
    priority: str = "low",
    task_group: str = "borrow",
    related_entity_type: str = "",
    related_entity_id: str = "",
    payload: dict | None = None,
    actor_type: str,
    actor_id: str,
) -> None:
    from bookflow_core.ai.kernel.intake import create_business_event_task

    create_business_event_task(
        db,
        action=action,
        title=title,
        priority=priority,
        task_group=task_group,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        payload=payload or {},
        actor_type=actor_type,
        actor_id=actor_id,
        commit=False,
    )


def _int_rule(db: Session, key: str, default: int) -> int:
    row = db.scalar(select(SystemSetting).where(SystemSetting.setting_key == key, SystemSetting.is_active == True))
    return int(row.setting_value) if row else default


def _reader_by_code(db: Session, code: str) -> ReaderAccount:
    reader = db.scalar(select(ReaderAccount).where(ReaderAccount.reader_code == code))
    if not reader:
        raise NotFoundError("ReaderAccount not found.", details={"reader_code": code})
    return reader


READER_TYPE_ALIASES = {
    "R01": "child",
    "R02": "teen",
    "R03": "adult",
    "R04": "senior",
    "R05": "institution",
    "儿童": "child",
    "青少年": "teen",
    "成人": "adult",
    "老年": "senior",
    "机构": "institution",
}

CIRCULATION_TYPE_ALIASES = {
    "热门": "hot",
    "普通": "normal",
    "冷门": "cold",
    "hot": "hot",
    "normal": "normal",
    "cold": "cold",
}


def _normalize_reader_type(code: str | None) -> str:
    if code is None:
        return ""
    raw = str(code).strip()
    return READER_TYPE_ALIASES.get(raw, raw)


def _normalize_circulation_type(value: str | None) -> str:
    if value is None:
        return ""
    raw = str(value).strip()
    return CIRCULATION_TYPE_ALIASES.get(raw, raw)


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise BusinessRuleError("Invalid empty date value.")
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    raise BusinessRuleError("Invalid date value.", details={"value": str(value)})


def _rule_for(db: Session, reader_type_code: str, circulation_type: str) -> CirculationRule:
    normalized_reader_type = _normalize_reader_type(reader_type_code)
    normalized_circulation_type = _normalize_circulation_type(circulation_type)
    rule = db.scalar(
        select(CirculationRule).where(
            CirculationRule.reader_type_code == normalized_reader_type,
            CirculationRule.circulation_type == normalized_circulation_type,
            CirculationRule.is_active == True,
        )
    )
    if not rule:
        raise BusinessRuleError(
            "Borrow rule not found.",
            details={
                "reader_type_code": reader_type_code,
                "circulation_type": circulation_type,
                "normalized_reader_type_code": normalized_reader_type,
                "normalized_circulation_type": normalized_circulation_type,
            },
        )
    return rule


def _loan_code() -> str:
    from datetime import datetime, timezone

    return f"LOAN-{int(datetime.now(timezone.utc).timestamp() * 1000000)}"


def _reservation_code() -> str:
    from datetime import datetime, timezone

    return f"RSV-{int(datetime.now(timezone.utc).timestamp() * 1000000)}"


def _code(prefix: str) -> str:
    from datetime import datetime, timezone

    return f"{prefix}-{int(datetime.now(timezone.utc).timestamp() * 1000000)}"


def _voucher_code(prefix: str) -> str:
    from datetime import datetime, timezone

    return f"{prefix}{int(datetime.now(timezone.utc).timestamp() * 1000) % 100000000:08d}"


def _notify_reservation_ready(
    db: Session,
    *,
    reader_id: int,
    reader_code: str,
    book_title: str,
    voucher_code: str,
    reserved_until: str,
    stamp: datetime,
) -> None:
    """直接创建通知：预约已到馆，包含取书凭证号。"""
    title = "预约图书已到馆"
    content = (
        f"你预约的《{book_title}》已到馆，请在保留期内到馆办理借阅。"
        f"取书凭证号：{voucher_code}。"
        f"保留截止日期：{reserved_until}。"
    )
    idempotency_key = f"reservation_ready:{reader_code}:{voucher_code}"
    msg = NotificationMessage(
        message_code=f"MSG-{int(stamp.timestamp() * 1000000)}",
        title=title,
        content=content,
        notification_type="reservation",
        source_type="system",
        related_entity_type="reservation",
        related_entity_id=voucher_code,
        lifecycle_status="completed",
        created_by_type="admin",
        created_by_code="system",
        idempotency_key=idempotency_key,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(msg)
    db.flush()
    delivery = NotificationDelivery(
        delivery_code=f"DLV-{int(stamp.timestamp() * 1000000)}",
        message_id=msg.id,
        recipient_type="reader",
        recipient_id=reader_id,
        channel="in_app",
        delivery_status="sent",
        read_status="unread",
        idempotency_key=idempotency_key,
        sent_at=stamp,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(delivery)


def active_borrow_count(db: Session, reader_id: int) -> int:
    return int(db.scalar(select(func.count(Loan.id)).where(Loan.reader_id == reader_id, Loan.status.in_(["active", "overdue"]))) or 0)


def _reader_credit_score(reader: ReaderAccount) -> int:
    try:
        return int(float(reader.credit_score or 0))
    except (TypeError, ValueError):
        return 0


def borrow_copy(db: Session, *, reader_code: str, copy_code: str, actor_type: str = "admin", actor_id: str = "admin", commit: bool = True) -> Loan:
    try:
        reader = _reader_by_code(db, reader_code)
        if reader_borrow_suspended(reader) or reader.status != "active":
            raise BusinessRuleError("ReaderAccount borrowing is suspended.")
        copy = get_copy_by_code(db, copy_code)
        if copy.copy_status != "available":
            raise BusinessRuleError("Copy is not available for borrowing.", details={"copy_code": copy_code, "copy_status": copy.copy_status})
        book = db.get(Book, copy.book_id)
        if not book or book.status != "active":
            raise BusinessRuleError("Book is not active.")
        rule = _rule_for(db, reader.reader_type_code, book.circulation_type)
        if active_borrow_count(db, reader.id) >= rule.max_borrow_count:
            raise BusinessRuleError("ReaderAccount has reached max borrow count.")
        t = get_business_date(db)
        stamp = utc_text()
        record = Loan(loan_code=_loan_code(), reader_id=reader.id, book_id=book.id, copy_id=copy.id, borrowed_at=t, due_at=t + timedelta(days=rule.borrow_days), status="active", renewal_count=0, handled_by_code=actor_id, created_at=stamp, updated_at=stamp)
        db.add(record)
        old = copy.copy_status
        copy.copy_status = "borrowed"
        write_status_event(db, copy, old, "borrowed", "borrow_copy", actor_type, actor_id)
        db.flush()
        db.add(LoanEvent(loan_id=record.id, event_type="borrowed", actor_code=actor_id, event_time=utc_text(), detail=f"copy_code={copy.copy_code};reader_code={reader.reader_code}"))
        recalculate_book_inventory(db, book.id)
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="borrow_copy", target_table="loans", target_id=copy.copy_code, detail={"reader_code": reader_code, "due_at": record.due_at})
        _enqueue_business_event(
            db,
            action="borrow_copy",
            title="Borrow completed",
            related_entity_type="loan",
            related_entity_id=str(record.id),
            payload={"reader_code": reader.reader_code, "copy_code": copy.copy_code, "book_id": book.id, "due_at": record.due_at},
            actor_type=actor_type,
            actor_id=actor_id,
        )
        if commit:
            db.commit()
            db.refresh(record)
        return record
    except Exception:
        if commit:
            db.rollback()
        raise


def _deduct_credit_for_overdue(db: Session, reader: ReaderAccount, record: Loan, overdue_days: int, actor_type: str, actor_id: str) -> int:
    per_day = _int_rule(db, "overdue_penalty_per_day", 1)
    max_penalty = _int_rule(db, "overdue_penalty_max_per_book", 20)
    threshold = _int_rule(db, "credit_suspend_threshold", 60)
    penalty = min(overdue_days * per_day, max_penalty)
    if penalty <= 0:
        return 0
    old = _reader_credit_score(reader)
    old_status = reader.status
    reader.credit_score = max(0, old - penalty)
    if _reader_credit_score(reader) < threshold:
        reader.status = "suspended"
    if old_status != reader.status:
        db.add(ReaderStatusEvent(reader_id=reader.id, old_status=old_status, new_status=reader.status, reason="overdue_return", actor_code=actor_id, created_at=utc_text()))
    db.add(ReaderCreditEvent(reader_id=reader.id, delta=-penalty, old_score=old, new_score=reader.credit_score, reason="overdue_return", related_loan_id=record.id, actor_code=actor_id, created_at=utc_text()))
    return penalty


def return_copy(db: Session, *, copy_code: str, actor_type: str = "admin", actor_id: str = "admin", commit: bool = True) -> Loan:
    try:
        copy = get_copy_by_code(db, copy_code)
        record = db.scalar(select(Loan).where(Loan.copy_id == copy.id, Loan.status.in_(["active", "overdue"])).order_by(Loan.id.desc()))
        if not record:
            raise BusinessRuleError("No active borrow record for copy.")
        reader = db.get(ReaderAccount, record.reader_id)
        t = get_business_date(db)
        record.returned_at = t
        due_date = _as_date(record.due_at)
        overdue_days = max(0, (t - due_date).days)
        penalty = 0
        if overdue_days > 0:
            record.status = "returned"
            penalty = _deduct_credit_for_overdue(db, reader, record, overdue_days, actor_type, actor_id)
            existing = db.scalar(select(OverdueCase).where(OverdueCase.loan_id == record.id))
            if existing:
                existing.status = "resolved"
                existing.overdue_days = overdue_days
                existing.penalty_score = penalty
            else:
                db.add(OverdueCase(loan_id=record.id, reader_id=reader.id, copy_id=copy.id, overdue_start_at=due_date + timedelta(days=1), overdue_days=overdue_days, penalty_score=penalty, status="resolved"))
        else:
            record.status = "returned"
            existing = db.scalar(select(OverdueCase).where(OverdueCase.loan_id == record.id))
            if existing:
                existing.status = "resolved"
                existing.overdue_days = overdue_days
        waiting = db.scalar(select(Reservation).where(Reservation.book_id == record.book_id, Reservation.status == "waiting").order_by(Reservation.created_at, Reservation.id))
        old = copy.copy_status
        if waiting:
            waiting.status = "ready_for_pickup"
            waiting.fulfilled_copy_id = copy.id
            waiting.reserved_until = t + timedelta(days=get_reservation_hold_days(db))
            copy.copy_status = "reserved"
            new_status = "reserved"
        else:
            pending_borrow = db.scalar(
                select(CirculationServiceRequest).where(
                    CirculationServiceRequest.book_id == record.book_id,
                    CirculationServiceRequest.request_type == "borrow",
                    CirculationServiceRequest.status == "pending",
                ).order_by(CirculationServiceRequest.created_at)
            )
            if pending_borrow:
                from datetime import datetime, timezone
                pending_borrow.status = "ready"
                pending_borrow.copy_id = copy.id
                pending_borrow.copy_code = copy.copy_code
                pending_borrow.expires_at = now() + timedelta(hours=24)
                copy.copy_status = "reserved"
                new_status = "reserved"
            else:
                copy.copy_status = "available"
                new_status = "available"
        write_status_event(db, copy, old, new_status, "return_copy", actor_type, actor_id)
        db.flush()
        db.add(LoanEvent(loan_id=record.id, event_type="returned", actor_code=actor_id, event_time=utc_text(), detail=f"copy_code={copy.copy_code};overdue_days={overdue_days};penalty={penalty}"))
        recalculate_book_inventory(db, record.book_id)
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="return_copy", target_table="loans", target_id=record.id, detail={"copy_code": copy_code, "overdue_days": overdue_days, "penalty": penalty})
        _enqueue_business_event(
            db,
            action="return_copy",
            title="Return completed",
            priority="normal" if overdue_days else "low",
            related_entity_type="loan",
            related_entity_id=str(record.id),
            payload={"copy_code": copy.copy_code, "overdue_days": overdue_days, "penalty": penalty, "new_status": new_status},
            actor_type=actor_type,
            actor_id=actor_id,
        )
        if commit:
            db.commit()
            db.refresh(record)
        return record
    except Exception:
        if commit:
            db.rollback()
        raise


def renew_borrow(db: Session, *, loan_id: int, actor_type: str = "admin", actor_id: str = "admin", commit: bool = True) -> LoanEvent:
    try:
        record = db.get(Loan, loan_id)
        if not record or record.status not in {"active", "overdue"}:
            raise BusinessRuleError("Borrow record cannot be renewed.")
        reader = db.get(ReaderAccount, record.reader_id)
        if reader_borrow_suspended(reader) or reader.status != "active":
            raise BusinessRuleError("ReaderAccount borrowing is suspended.")
        book = db.get(Book, record.book_id)
        rule = _rule_for(db, reader.reader_type_code, book.circulation_type)
        current_renewals = int(record.renewal_count or 0)
        if current_renewals >= rule.max_renewals:
            raise BusinessRuleError("Max renewals reached.")
        old_due = _as_date(record.due_at)
        new_due = old_due + timedelta(days=rule.borrow_days)
        record.renewal_count = current_renewals + 1
        record.due_at = new_due
        renewal = LoanEvent(loan_id=record.id, event_type="renewed", actor_code=actor_id, event_time=utc_text(), old_due_at=old_due, new_due_at=new_due, detail=f"renewal_no={record.renewal_count}")
        db.add(renewal)
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="renew_borrow", target_table="loans", target_id=record.id, detail={"old_due_at": old_due, "new_due_at": new_due})
        _enqueue_business_event(
            db,
            action="renew_borrow",
            title="Renewal completed",
            related_entity_type="loan",
            related_entity_id=str(record.id),
            payload={"loan_id": record.id, "old_due_at": old_due, "new_due_at": new_due, "renewal_count": record.renewal_count},
            actor_type=actor_type,
            actor_id=actor_id,
        )
        if commit:
            db.commit()
            db.refresh(renewal)
        return renewal
    except Exception:
        if commit:
            db.rollback()
        raise


def create_reservation(db: Session, *, reader_code: str, book_code: str, actor_type: str = "admin", actor_id: str = "admin", commit: bool = True) -> Reservation:
    try:
        reader = _reader_by_code(db, reader_code)
        book = db.scalar(select(Book).where(Book.book_code == book_code))
        if not book:
            raise NotFoundError("Book not found.", details={"book_code": book_code})
        existing_reservation = db.scalar(
            select(Reservation).where(
                Reservation.reader_id == reader.id,
                Reservation.book_id == book.id,
                Reservation.status.in_(ACTIVE_RESERVATION_STATUSES),
            )
        )
        if existing_reservation:
            raise BusinessRuleError(
                "Reader already has an active reservation for this book.",
                details={"reader_code": reader_code, "book_code": book_code, "reservation_id": existing_reservation.id},
            )
        copy = db.scalar(select(BookCopy).where(BookCopy.book_id == book.id, BookCopy.copy_status == "available").order_by(BookCopy.id))
        if copy:
            old = copy.copy_status
            copy.copy_status = "reserved"
            t = get_business_date(db)
            stamp = utc_text()
            reserved_until = t + timedelta(days=get_reservation_hold_days(db))
            reservation = Reservation(reservation_code=_reservation_code(), reader_id=reader.id, book_id=book.id, fulfilled_copy_id=copy.id, status="ready_for_pickup", requested_at=stamp, reserved_until=reserved_until, created_by_code=actor_id, created_at=stamp, updated_at=stamp)
            db.add(reservation)
            write_status_event(db, copy, old, "reserved", "create_reservation", actor_type, actor_id)
            db.flush()
            # 生成取书凭证码（与 create_borrow_request 一致的 BR 格式）
            voucher_code = _voucher_code("BR")
            # 同步创建 CirculationServiceRequest，使预约出现在"预约记录处理"列表中
            csr = CirculationServiceRequest(
                request_code=_code("CSR"),
                voucher_code=voucher_code,
                request_type="borrow",
                status="ready",
                source_type="admin_portal",
                source_actor_type=actor_type,
                source_actor_id=actor_id,
                reader_id=reader.id,
                reader_code=reader.reader_code,
                book_id=book.id,
                book_code=book.book_code,
                copy_id=copy.id,
                copy_code=copy.copy_code,
                reservation_id=reservation.id,
                reservation_code=reservation.reservation_code,
                expires_at=stamp + timedelta(days=get_reservation_hold_days(db)),
                created_at=stamp,
                updated_at=stamp,
            )
            db.add(csr)
            # 同步发送通知给读者，包含取书凭证号
            _notify_reservation_ready(
                db,
                reader_id=reader.id,
                reader_code=reader.reader_code,
                book_title=book.title,
                voucher_code=voucher_code,
                reserved_until=str(reserved_until),
                stamp=stamp,
            )
            recalculate_book_inventory(db, book.id)
        else:
            stamp = utc_text()
            reservation = Reservation(reservation_code=_reservation_code(), reader_id=reader.id, book_id=book.id, status="waiting", requested_at=stamp, created_by_code=actor_id, created_at=stamp, updated_at=stamp)
            db.add(reservation)
            db.flush()
        db.add(ReservationEvent(reservation_id=reservation.id, event_type="created", actor_code=actor_id, event_time=utc_text(), detail=f"book_code={book.book_code};reader_code={reader.reader_code};status={reservation.status}"))
        stats = get_or_create_book_stats(db, book.id)
        stats.reserve_90d = (stats.reserve_90d or 0) + 1
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="create_reservation", target_table="reservations", target_id=book.book_code, detail={"reader_code": reader_code, "status": reservation.status})
        _enqueue_business_event(
            db,
            action="create_reservation",
            title="Reservation created",
            priority="normal",
            task_group="reservation",
            related_entity_type="reservation",
            related_entity_id=str(reservation.id),
            payload={"reader_code": reader.reader_code, "book_code": book.book_code, "book_title": book.title, "status": reservation.status, "copy_id": reservation.fulfilled_copy_id, "reservation_code": reservation.reservation_code, "reserved_until": str(reservation.reserved_until) if reservation.reserved_until else None, "suppress_reader_notification": True},
            actor_type=actor_type,
            actor_id=actor_id,
        )
        if commit:
            db.commit()
            db.refresh(reservation)
        return reservation
    except Exception:
        if commit:
            db.rollback()
        raise


def cancel_reservation(db: Session, *, reservation_id: int, actor_type: str = "admin", actor_id: str = "admin", commit: bool = True) -> Reservation:
    try:
        reservation = db.get(Reservation, reservation_id)
        if not reservation or reservation.status not in ACTIVE_RESERVATION_STATUSES:
            raise BusinessRuleError("Reservation cannot be cancelled.")
        before = {"id": reservation.id, "status": reservation.status, "fulfilled_copy_id": reservation.fulfilled_copy_id, "reserved_until": reservation.reserved_until}
        if reservation.status == "ready_for_pickup" and reservation.fulfilled_copy_id:
            copy = db.get(BookCopy, reservation.fulfilled_copy_id)
            old = copy.copy_status
            copy.copy_status = "available"
            write_status_event(db, copy, old, "available", "cancel_reservation", actor_type, actor_id)
            db.flush()
            recalculate_book_inventory(db, copy.book_id)
        reservation.status = "cancelled"
        reservation.updated_at = utc_text()
        after = {"id": reservation.id, "status": reservation.status, "fulfilled_copy_id": reservation.fulfilled_copy_id, "reserved_until": reservation.reserved_until}
        db.add(ReservationEvent(reservation_id=reservation.id, event_type="cancelled", actor_code=actor_id, event_time=utc_text(), detail=f"reason=cancel_reservation;previous_status={before['status']}"))
        create_snapshot(db, action_type="cancel_reservation", target_table="reservations", target_id=str(reservation.id), before=before, after=after, actor_type=actor_type, actor_id=actor_id)
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="cancel_reservation", target_table="reservations", target_id=reservation.id)
        _enqueue_business_event(
            db,
            action="cancel_reservation",
            title="Reservation cancelled",
            priority="normal",
            task_group="reservation",
            related_entity_type="reservation",
            related_entity_id=str(reservation.id),
            payload={"before": before, "after": after},
            actor_type=actor_type,
            actor_id=actor_id,
        )
        if commit:
            db.commit()
            db.refresh(reservation)
        return reservation
    except Exception:
        if commit:
            db.rollback()
        raise


def fulfill_reservation(db: Session, *, reservation_id: int, actor_type: str = "admin", actor_id: str = "admin", commit: bool = True) -> Loan:
    try:
        reservation = db.get(Reservation, reservation_id)
        if not reservation or reservation.status != "ready_for_pickup" or not reservation.fulfilled_copy_id:
            raise BusinessRuleError("Reservation is not ready to fulfill.")
        reader = db.get(ReaderAccount, reservation.reader_id)
        if not reader or reader_borrow_suspended(reader) or reader.status != "active":
            raise BusinessRuleError("ReaderAccount borrowing is suspended.")
        copy = db.get(BookCopy, reservation.fulfilled_copy_id)
        if not copy or copy.copy_status != "reserved":
            raise BusinessRuleError("Reserved copy is not available for fulfillment.")
        book = db.get(Book, copy.book_id)
        rule = _rule_for(db, reader.reader_type_code, book.circulation_type)
        if active_borrow_count(db, reader.id) >= rule.max_borrow_count:
            raise BusinessRuleError("ReaderAccount has reached max borrow count.")
        before = {"id": reservation.id, "status": reservation.status, "fulfilled_copy_id": reservation.fulfilled_copy_id, "reserved_until": reservation.reserved_until}
        reservation.status = "fulfilled"
        reservation.updated_at = utc_text()
        old = copy.copy_status
        copy.copy_status = "borrowed"
        t = get_business_date(db)
        stamp = utc_text()
        record = Loan(loan_code=_loan_code(), reader_id=reader.id, book_id=book.id, copy_id=copy.id, borrowed_at=t, due_at=t + timedelta(days=rule.borrow_days), status="active", renewal_count=0, handled_by_code=actor_id, created_at=stamp, updated_at=stamp)
        db.add(record)
        write_status_event(db, copy, old, "borrowed", "fulfill_reservation", actor_type, actor_id)
        db.flush()
        db.add(ReservationEvent(reservation_id=reservation.id, event_type="fulfilled", actor_code=actor_id, event_time=utc_text(), detail=f"loan_id={record.id};copy_code={copy.copy_code}"))
        db.add(LoanEvent(loan_id=record.id, event_type="borrowed_from_reservation", actor_code=actor_id, event_time=utc_text(), detail=f"reservation_id={reservation.id};copy_code={copy.copy_code}"))
        recalculate_book_inventory(db, book.id)
        after = {"id": reservation.id, "status": reservation.status, "fulfilled_copy_id": reservation.fulfilled_copy_id, "reserved_until": reservation.reserved_until}
        create_snapshot(db, action_type="fulfill_reservation", target_table="reservations", target_id=str(reservation.id), before=before, after=after, actor_type=actor_type, actor_id=actor_id)
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="fulfill_reservation", target_table="reservations", target_id=reservation.id)
        _enqueue_business_event(
            db,
            action="fulfill_reservation",
            title="Reservation fulfilled",
            priority="normal",
            task_group="reservation",
            related_entity_type="reservation",
            related_entity_id=str(reservation.id),
            payload={"reservation_id": reservation.id, "loan_id": record.id, "copy_code": copy.copy_code},
            actor_type=actor_type,
            actor_id=actor_id,
        )
        if commit:
            db.commit()
            db.refresh(record)
        return record
    except Exception:
        if commit:
            db.rollback()
        raise


def scan_overdues(db: Session, *, actor_type: str = "system", actor_id: str = "overdue_scan", commit: bool = True) -> int:
    try:
        count = 0
        t = get_business_date(db)
        records = db.scalars(select(Loan).where(Loan.status == "active", Loan.due_at < t)).all()
        for record in records:
            record.status = "overdue"
            overdue_days = (t - record.due_at).days
            due_date = _as_date(record.due_at)
            existing = db.scalar(select(OverdueCase).where(OverdueCase.loan_id == record.id))
            if existing:
                existing.overdue_days = overdue_days
            else:
                db.add(OverdueCase(loan_id=record.id, reader_id=record.reader_id, copy_id=record.copy_id, overdue_start_at=due_date + timedelta(days=1), overdue_days=overdue_days, penalty_score=0, status="active"))
            reader = db.get(ReaderAccount, record.reader_id)
            copy = db.get(BookCopy, record.copy_id)
            book = db.get(Book, record.book_id)
            from bookflow_core.models import WorkTask
            from bookflow_core.services.notification_service import create_deliveries, create_message, send_message
            from bookflow_core.services.task_service import ACTIVE_TASK_STATUSES, create_task
            existing_task = db.scalar(
                select(WorkTask).where(
                    WorkTask.source_type == "overdue",
                    WorkTask.related_entity_type == "loan",
                    WorkTask.related_entity_id == str(record.id),
                    WorkTask.status.in_(ACTIVE_TASK_STATUSES),
                )
            )
            if not existing_task:
                create_task(
                    db,
                    title="逾期借阅待处理",
                    description=f"{reader.name if reader else '读者'} 的《{book.title if book else '图书'}》已逾期 {overdue_days} 天，副本 {copy.copy_code if copy else record.copy_id}。",
                    priority="high" if overdue_days < 7 else "urgent",
                    source_type="overdue",
                    related_entity_type="loan",
                    related_entity_id=str(record.id),
                    task_group="borrow",
                    source_payload={
                        "kernel_intent": "overdue_case",
                        "loan_id": record.id,
                        "reader_code": reader.reader_code if reader else "",
                        "copy_code": copy.copy_code if copy else "",
                        "book_id": book.id if book else None,
                        "overdue_days": overdue_days,
                    },
                    execution_context={"entrypoint": "scan_overdues"},
                    requires_human_confirmation=overdue_days >= 14,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    commit=False,
                )
            if reader:
                notice = create_message(
                    db,
                    title="借阅已逾期",
                    content=f"您借阅的《{book.title if book else '图书'}》已逾期 {overdue_days} 天，请尽快归还或联系馆员处理。",
                    notification_type="overdue",
                    source_type="system",
                    related_entity_type="loan",
                    related_entity_id=str(record.id),
                    target_scope_json='{"reader_count":1,"source":"overdue_scan"}',
                    lifecycle_status="queued",
                    created_by_type="system",
                    created_by_code=str(actor_id or "overdue_scan"),
                    idempotency_key=f"overdue_scan:loan:{record.id}:message",
                    actor_type=actor_type,
                    actor_id=actor_id,
                    commit=False,
                )
                create_deliveries(
                    db,
                    message_id=notice.id,
                    recipients=[{"recipient_type": "reader", "recipient_id": reader.id}],
                    actor_type=actor_type,
                    actor_id=actor_id,
                    commit=False,
                )
                if notice.lifecycle_status in {"draft", "queued"}:
                    send_message(db, notice.id, actor_type=actor_type, actor_id=actor_id, commit=False)
            count += 1
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="scan_overdues", target_table="loans", detail={"count": count, "generated_tasks_and_notifications": True})
        if commit:
            db.commit()
        return count
    except Exception:
        if commit:
            db.rollback()
        raise
