from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from bookflow_core.core.exceptions import BookFlowError, BusinessRuleError, NotFoundError
from bookflow_core.core.time import now
from bookflow_core.models import Book, BookCopy, CirculationServiceRequest, Loan, LoanEvent, NotificationDelivery, NotificationMessage, OverdueCase, ReaderAccount, Reservation, ReservationEvent, WorkTask
from bookflow_core.services.catalog_service import get_copy_by_code, recalculate_book_inventory
from bookflow_core.services.circulation_service import _loan_code, _rule_for, active_borrow_count, create_reservation, renew_borrow, return_copy
from bookflow_core.services.common import as_json, utc_text, write_audit, write_status_event
from bookflow_core.services.reader_service import reader_borrow_suspended
from bookflow_core.services.statistics_service import get_business_date
from bookflow_core.services.task_service import ACTIVE_TASK_STATUSES, create_task, resolve_task


REQUEST_STATUSES = {"draft", "pending", "ready", "completed", "cancelled", "expired", "failed", "waiting_human"}
REQUEST_TYPES = {"borrow", "reservation", "renew", "return"}
TERMINAL_STATUSES = {"completed", "cancelled", "expired", "failed"}


def _code(prefix: str) -> str:
    from datetime import datetime, timezone

    return f"{prefix}-{int(datetime.now(timezone.utc).timestamp() * 1000000)}"


def _voucher_code(prefix: str) -> str:
    from datetime import datetime, timezone

    return f"{prefix}{int(datetime.now(timezone.utc).timestamp() * 1000) % 100000000:08d}"


def _create_reader_notification(
    db: Session,
    *,
    reader_id: int,
    title: str,
    content: str,
    notification_type: str = "general",
    related_entity_type: str | None = None,
    related_entity_id: str | None = None,
    idempotency_key: str | None = None,
) -> None:
    stamp = now()
    msg = NotificationMessage(
        message_code=f"MSG-{int(stamp.timestamp() * 1000000)}",
        title=title,
        content=content,
        notification_type=notification_type,
        source_type="system",
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        lifecycle_status="completed",
        created_by_type="system",
        created_by_code="system",
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
        idempotency_key=idempotency_key or f"auto:{msg.message_code}:reader:{reader_id}",
        sent_at=stamp,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(delivery)


def _json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _reader_active(reader: ReaderAccount) -> bool:
    return not reader_borrow_suspended(reader) and reader.status == "active"


def _aware(value: datetime) -> datetime:
    from bookflow_core.core.time import CST
    return value if value.tzinfo is not None else value.replace(tzinfo=CST)


def _is_expired(value: datetime | None) -> bool:
    return bool(value and _aware(value) < now())


def _book_for_copy(db: Session, copy: BookCopy) -> Book:
    book = db.get(Book, copy.book_id)
    if not book:
        raise NotFoundError("Book not found.", code="BOOK_NOT_FOUND", details={"copy_id": copy.id})
    return book


def _get_reader(db: Session, reader_code: str) -> ReaderAccount:
    reader = db.scalar(select(ReaderAccount).where(ReaderAccount.reader_code == reader_code))
    if not reader:
        raise NotFoundError("ReaderAccount not found.", code="READER_NOT_FOUND", details={"reader_code": reader_code})
    return reader


def _create_request_task(db: Session, row: CirculationServiceRequest, *, priority: str = "normal") -> WorkTask:
    group = "reservation" if row.request_type == "reservation" else "borrow"
    type_label = {"borrow": "借书", "return": "还书", "reservation": "预约", "renew": "续借"}.get(row.request_type, row.request_type)
    title = f"读者{type_label}服务请求"
    parts = [f"读者 {row.reader_code}", f"请求 {row.request_code}"]
    if row.voucher_code:
        parts.append(f"凭证 {row.voucher_code}")
    if row.book_code:
        parts.append(f"图书 {row.book_code}")
    if row.copy_code:
        parts.append(f"副本 {row.copy_code}")
    task = create_task(
        db,
        title=title,
        description="，".join(parts),
        priority=priority,
        source_type="reader_event" if row.source_actor_type == "reader" else "ai_admin",
        task_group=group,
        related_entity_type="circulation_service_request",
        related_entity_id=str(row.id),
        source_payload={
            "kernel_intent": "business_event",
            "action": f"circulation_request_{row.request_type}",
            "request_code": row.request_code,
            "voucher_code": row.voucher_code,
            "reader_code": row.reader_code,
            "book_id": row.book_id,
            "copy_id": row.copy_id,
            "loan_id": row.loan_id,
            "reservation_id": row.reservation_id,
            "status": row.status,
        },
        execution_context={"entrypoint": "circulation_service_request", "request_type": row.request_type},
        actor_type=row.source_actor_type or "system",
        actor_id=row.source_actor_id or "system",
        commit=False,
    )
    row.task_id = task.id
    row.task_code = task.task_code
    return task


def _resolve_request_task(db: Session, row: CirculationServiceRequest, *, actor_id: str, resolution: str) -> None:
    if not row.task_code:
        return
    task = db.scalar(select(WorkTask).where(WorkTask.task_code == row.task_code))
    if not task or task.status not in ACTIVE_TASK_STATUSES:
        return
    resolve_task(db, row.task_code, resolution=resolution, actor_id=actor_id, commit=False)


def _set_result(row: CirculationServiceRequest, result: dict[str, Any]) -> None:
    row.result_json = as_json(result)
    row.updated_at = now()


def service_request_to_dict(row: CirculationServiceRequest) -> dict[str, Any]:
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
        "ai_plan": _json(row.ai_plan_json),
        "ai_trace": _json(row.ai_trace_json),
        "payload": _json(row.request_payload_json),
        "result": _json(row.result_json),
        "failure_reason": row.failure_reason,
        "expires_at": str(row.expires_at) if row.expires_at else None,
        "completed_at": str(row.completed_at) if row.completed_at else None,
        "cancelled_at": str(row.cancelled_at) if row.cancelled_at else None,
        "handled_by_code": row.handled_by_code,
        "created_at": str(row.created_at) if row.created_at else None,
        "updated_at": str(row.updated_at) if row.updated_at else None,
    }


def get_service_request(db: Session, request_code: str) -> CirculationServiceRequest:
    row = db.scalar(select(CirculationServiceRequest).where(CirculationServiceRequest.request_code == request_code))
    if not row:
        row = db.scalar(select(CirculationServiceRequest).where(CirculationServiceRequest.voucher_code == request_code))
    if not row:
        raise NotFoundError("Circulation service request not found.", code="RESOURCE_NOT_FOUND", details={"request_code": request_code})
    return row


def create_borrow_request(
    db: Session,
    reader: ReaderAccount,
    *,
    book_id: int | None = None,
    copy_id: int | None = None,
    source_type: str = "reader_ai",
    source_actor_type: str = "reader",
    source_actor_id: str | None = None,
    ai_plan: dict | None = None,
    ai_trace: dict | None = None,
    payload: dict | None = None,
    hold_hours: int = 24,
    commit: bool = True,
) -> CirculationServiceRequest:
    try:
        if book_id is None and copy_id is None:
            raise BookFlowError("book_id or copy_id is required.", code="VALIDATION_ERROR")
        if not _reader_active(reader):
            raise BusinessRuleError("ReaderAccount borrowing is suspended.")
        copy = db.get(BookCopy, copy_id) if copy_id is not None else None
        if copy_id is not None and not copy:
            raise NotFoundError("Copy not found.", code="COPY_NOT_FOUND", details={"copy_id": copy_id})
        book = _book_for_copy(db, copy) if copy else db.get(Book, book_id)
        if not book or book.status != "active":
            raise BusinessRuleError("Book is not active.", details={"book_id": book_id})
        if copy is None:
            copy = db.scalar(select(BookCopy).where(BookCopy.book_id == book.id, BookCopy.copy_status == "available").order_by(BookCopy.id))
        status = "pending"
        voucher = _voucher_code("BR")
        expires_at = now() + timedelta(hours=max(1, int(hold_hours or 24)))
        if copy is not None:
            if copy.copy_status != "available":
                raise BusinessRuleError("Copy is not available for borrowing request.", details={"copy_id": copy.id, "copy_status": copy.copy_status})
            rule = _rule_for(db, reader.reader_type_code, book.circulation_type)
            if active_borrow_count(db, reader.id) >= rule.max_borrow_count:
                raise BusinessRuleError("ReaderAccount has reached max borrow count.")
            old = copy.copy_status
            copy.copy_status = "reserved"
            write_status_event(db, copy, old, "reserved", "create_borrow_service_request", source_actor_type, source_actor_id or reader.reader_code)
            recalculate_book_inventory(db, book.id)
            status = "ready"
        row = CirculationServiceRequest(
            request_code=_code("CSR"),
            voucher_code=voucher,
            request_type="borrow",
            status=status,
            source_type=source_type,
            source_actor_type=source_actor_type,
            source_actor_id=source_actor_id or reader.reader_code,
            reader_id=reader.id,
            reader_code=reader.reader_code,
            book_id=book.id,
            book_code=book.book_code,
            copy_id=copy.id if copy else None,
            copy_code=copy.copy_code if copy else None,
            ai_plan_json=as_json(ai_plan or {}),
            ai_trace_json=as_json(ai_trace or {}),
            request_payload_json=as_json(payload or {}),
            expires_at=expires_at,
            created_at=now(),
            updated_at=now(),
        )
        db.add(row)
        db.flush()
        _create_request_task(db, row, priority="normal")
        _create_reader_notification(
            db,
            reader_id=reader.id,
            title="借阅取书凭证已生成",
            content=f"你已成功登记借阅《{book.title}》，取书凭证码 {voucher}，请在 {expires_at.strftime('%Y-%m-%d %H:%M')} 前到馆取书。",
            notification_type="borrow",
            related_entity_type="circulation_service_request",
            related_entity_id=row.request_code,
            idempotency_key=f"borrow_request:{row.request_code}:reader:{reader.id}",
        )
        write_audit(db, actor_type=source_actor_type, actor_id=row.source_actor_id, action="create_borrow_service_request", target_table="circulation_service_requests", target_id=row.request_code, detail={"status": row.status, "voucher_code": row.voucher_code})
        if commit:
            db.commit()
            db.refresh(row)
        return row
    except Exception:
        if commit:
            db.rollback()
        raise


def redeem_borrow_request(db: Session, request_code: str, *, admin_code: str, voucher_code: str | None = None, commit: bool = True) -> CirculationServiceRequest:
    try:
        row = get_service_request(db, request_code)
        if row.request_type != "borrow":
            raise BusinessRuleError("Circulation request is not a borrow request.", details={"request_code": request_code})
        if row.status != "ready":
            raise BusinessRuleError("Borrow request is not ready for fulfillment.", details={"status": row.status})
        if voucher_code and row.voucher_code != voucher_code:
            raise BusinessRuleError("Voucher code does not match the borrow request.", details={"request_code": request_code, "provided_voucher": voucher_code})
        if _is_expired(row.expires_at):
            expire_service_requests(db, request_code=row.request_code, commit=False)
            raise BusinessRuleError("Borrow request has expired.", details={"request_code": row.request_code})
        reader = db.get(ReaderAccount, row.reader_id)
        copy = db.get(BookCopy, row.copy_id)
        if not reader or not copy:
            raise BusinessRuleError("Borrow request is missing reader or copy.")
        if not _reader_active(reader):
            raise BusinessRuleError("ReaderAccount borrowing is suspended.")
        if copy.copy_status != "reserved":
            raise BusinessRuleError("Reserved copy is no longer available.", details={"copy_status": copy.copy_status})
        book = _book_for_copy(db, copy)
        rule = _rule_for(db, reader.reader_type_code, book.circulation_type)
        if active_borrow_count(db, reader.id) >= rule.max_borrow_count:
            raise BusinessRuleError("ReaderAccount has reached max borrow count.")
        t = get_business_date(db)
        stamp = utc_text()
        loan = Loan(loan_code=_loan_code(), reader_id=reader.id, book_id=book.id, copy_id=copy.id, borrowed_at=t, due_at=t + timedelta(days=rule.borrow_days), status="active", renewal_count=0, handled_by_code=admin_code, created_at=stamp, updated_at=stamp)
        db.add(loan)
        old = copy.copy_status
        copy.copy_status = "borrowed"
        write_status_event(db, copy, old, "borrowed", "redeem_borrow_service_request", "admin", admin_code)
        db.flush()
        db.add(LoanEvent(loan_id=loan.id, event_type="borrowed_from_service_request", actor_code=admin_code, event_time=utc_text(), detail=f"request_code={row.request_code};copy_code={copy.copy_code}"))
        # 如果该请求关联了预约，同步将预约标记为 fulfilled
        if row.reservation_id:
            reservation = db.get(Reservation, row.reservation_id)
            if reservation and reservation.status in ("ready_for_pickup", "waiting"):
                reservation.status = "fulfilled"
                reservation.updated_at = now()
                db.add(ReservationEvent(reservation_id=reservation.id, event_type="fulfilled", actor_code=admin_code, event_time=utc_text(), detail=f"loan_id={loan.id};copy_code={copy.copy_code};via_service_request={row.request_code}"))
        recalculate_book_inventory(db, book.id)
        row.status = "completed"
        row.loan_id = loan.id
        row.loan_code = loan.loan_code
        row.completed_at = now()
        row.handled_by_code = admin_code
        _set_result(row, {"loan_id": loan.id, "loan_code": loan.loan_code, "due_at": str(loan.due_at), "copy_code": copy.copy_code, "status": loan.status})
        _resolve_request_task(db, row, actor_id=admin_code, resolution="borrow request redeemed")
        _create_reader_notification(
            db,
            reader_id=reader.id,
            title="借阅成功",
            content=f"你已成功借阅《{book.title}》，应还日期 {loan.due_at.strftime('%Y-%m-%d')}。副本编号 {copy.copy_code}。",
            notification_type="borrow",
            related_entity_type="loan",
            related_entity_id=loan.loan_code,
            idempotency_key=f"borrow_completed:{loan.loan_code}:reader:{reader.id}",
        )
        write_audit(db, actor_type="admin", actor_id=admin_code, action="redeem_borrow_service_request", target_table="circulation_service_requests", target_id=row.request_code, detail=_json(row.result_json))
        if commit:
            db.commit()
            db.refresh(row)
        return row
    except Exception:
        if commit:
            db.rollback()
        raise


def create_return_request(
    db: Session,
    reader: ReaderAccount,
    *,
    loan_id: int | None = None,
    copy_code: str | None = None,
    source_type: str = "reader_ai",
    source_actor_type: str = "reader",
    source_actor_id: str | None = None,
    ai_plan: dict | None = None,
    ai_trace: dict | None = None,
    payload: dict | None = None,
    commit: bool = True,
) -> CirculationServiceRequest:
    try:
        record = db.get(Loan, loan_id) if loan_id is not None else None
        if record is None and copy_code:
            copy = get_copy_by_code(db, copy_code)
            record = db.scalar(select(Loan).where(Loan.copy_id == copy.id, Loan.status.in_(["active", "overdue"])).order_by(Loan.id.desc()))
        if not record or record.reader_id != reader.id or record.status not in {"active", "overdue"}:
            raise BusinessRuleError("No active borrow record can be returned by this reader.")
        existing = db.scalar(
            select(CirculationServiceRequest).where(
                CirculationServiceRequest.reader_id == reader.id,
                CirculationServiceRequest.loan_id == record.id,
                CirculationServiceRequest.request_type == "return",
                CirculationServiceRequest.status.in_(["pending", "ready"]),
            ).order_by(CirculationServiceRequest.id.desc())
        )
        if existing and not _is_expired(existing.expires_at):
            return existing
        if existing and _is_expired(existing.expires_at):
            expire_service_requests(db, request_code=existing.request_code, commit=False)
        copy = db.get(BookCopy, record.copy_id)
        book = db.get(Book, record.book_id)
        row = CirculationServiceRequest(
            request_code=_code("CSR"),
            voucher_code=_voucher_code("RT"),
            request_type="return",
            status="ready",
            source_type=source_type,
            source_actor_type=source_actor_type,
            source_actor_id=source_actor_id or reader.reader_code,
            reader_id=reader.id,
            reader_code=reader.reader_code,
            book_id=record.book_id,
            book_code=book.book_code if book else None,
            copy_id=record.copy_id,
            copy_code=copy.copy_code if copy else None,
            loan_id=record.id,
            loan_code=record.loan_code,
            ai_plan_json=as_json(ai_plan or {}),
            ai_trace_json=as_json(ai_trace or {}),
            request_payload_json=as_json(payload or {}),
            expires_at=now() + timedelta(days=7),
            created_at=now(),
            updated_at=now(),
        )
        db.add(row)
        db.flush()
        _create_request_task(db, row, priority="normal")
        write_audit(db, actor_type=source_actor_type, actor_id=row.source_actor_id, action="create_return_service_request", target_table="circulation_service_requests", target_id=row.request_code, detail={"voucher_code": row.voucher_code, "loan_id": row.loan_id})
        if commit:
            db.commit()
            db.refresh(row)
        return row
    except Exception:
        if commit:
            db.rollback()
        raise


def complete_return_request(db: Session, request_code: str, *, admin_code: str, commit: bool = True) -> CirculationServiceRequest:
    try:
        row = get_service_request(db, request_code)
        if row.request_type != "return":
            raise BusinessRuleError("Circulation request is not a return request.", details={"request_code": request_code})
        if row.status != "ready":
            raise BusinessRuleError("Return request is not ready.", details={"status": row.status})
        if not row.copy_code:
            raise BusinessRuleError("Return request has no copy code.")
        record = return_copy(db, copy_code=row.copy_code, actor_type="admin", actor_id=admin_code, commit=False)
        returned_copy = db.get(BookCopy, record.copy_id)
        overdue_case = db.scalar(select(OverdueCase).where(OverdueCase.loan_id == record.id))
        overdue_days = int(overdue_case.overdue_days or 0) if overdue_case else 0
        penalty_score = int(overdue_case.penalty_score or 0) if overdue_case else 0
        row.status = "completed"
        row.completed_at = now()
        row.handled_by_code = admin_code
        _set_result(
            row,
            {
                "loan_id": record.id,
                "status": record.status,
                "returned_at": str(record.returned_at),
                "copy_code": row.copy_code,
                "copy_status": returned_copy.copy_status if returned_copy else None,
                "overdue_days": overdue_days,
                "penalty_score": penalty_score,
            },
        )
        _resolve_request_task(db, row, actor_id=admin_code, resolution="return request completed")
        write_audit(db, actor_type="admin", actor_id=admin_code, action="complete_return_service_request", target_table="circulation_service_requests", target_id=row.request_code, detail=_json(row.result_json))
        if commit:
            db.commit()
            db.refresh(row)
        return row
    except Exception:
        if commit:
            db.rollback()
        raise


def create_reservation_request(
    db: Session,
    reader: ReaderAccount,
    *,
    book_id: int,
    source_type: str = "reader_ai",
    source_actor_type: str = "reader",
    source_actor_id: str | None = None,
    ai_plan: dict | None = None,
    ai_trace: dict | None = None,
    payload: dict | None = None,
    commit: bool = True,
) -> CirculationServiceRequest:
    try:
        book = db.get(Book, book_id)
        if not book:
            raise NotFoundError("Book not found.", code="BOOK_NOT_FOUND", details={"book_id": book_id})
        reservation = create_reservation(db, reader_code=reader.reader_code, book_code=book.book_code, actor_type=source_actor_type, actor_id=source_actor_id or reader.reader_code, commit=False)
        row = CirculationServiceRequest(
            request_code=_code("CSR"),
            voucher_code=reservation.reservation_code,
            request_type="reservation",
            status="completed",
            source_type=source_type,
            source_actor_type=source_actor_type,
            source_actor_id=source_actor_id or reader.reader_code,
            reader_id=reader.id,
            reader_code=reader.reader_code,
            book_id=book.id,
            book_code=book.book_code,
            copy_id=reservation.fulfilled_copy_id,
            reservation_id=reservation.id,
            reservation_code=reservation.reservation_code,
            ai_plan_json=as_json(ai_plan or {}),
            ai_trace_json=as_json(ai_trace or {}),
            request_payload_json=as_json(payload or {}),
            completed_at=now(),
            created_at=now(),
            updated_at=now(),
        )
        db.add(row)
        db.flush()
        _create_request_task(db, row, priority="normal")
        _set_result(row, {"reservation_id": reservation.id, "reservation_code": reservation.reservation_code, "status": reservation.status, "fulfilled_copy_id": reservation.fulfilled_copy_id})
        _resolve_request_task(db, row, actor_id=row.source_actor_id, resolution="reservation created")
        if commit:
            db.commit()
            db.refresh(row)
        return row
    except Exception:
        if commit:
            db.rollback()
        raise


def create_renew_request(
    db: Session,
    reader: ReaderAccount,
    *,
    loan_id: int,
    source_type: str = "reader_ai",
    source_actor_type: str = "reader",
    source_actor_id: str | None = None,
    ai_plan: dict | None = None,
    ai_trace: dict | None = None,
    payload: dict | None = None,
    commit: bool = True,
) -> CirculationServiceRequest:
    try:
        record = db.get(Loan, loan_id)
        if not record or record.reader_id != reader.id:
            raise BusinessRuleError("Cannot renew another reader's borrow record.")
        event = renew_borrow(db, loan_id=loan_id, actor_type=source_actor_type, actor_id=source_actor_id or reader.reader_code, commit=False)
        row = CirculationServiceRequest(
            request_code=_code("CSR"),
            voucher_code=None,
            request_type="renew",
            status="completed",
            source_type=source_type,
            source_actor_type=source_actor_type,
            source_actor_id=source_actor_id or reader.reader_code,
            reader_id=reader.id,
            reader_code=reader.reader_code,
            book_id=record.book_id,
            copy_id=record.copy_id,
            loan_id=record.id,
            loan_code=record.loan_code,
            ai_plan_json=as_json(ai_plan or {}),
            ai_trace_json=as_json(ai_trace or {}),
            request_payload_json=as_json(payload or {}),
            completed_at=now(),
            created_at=now(),
            updated_at=now(),
        )
        db.add(row)
        db.flush()
        _create_request_task(db, row, priority="normal")
        _set_result(row, {"renewal_id": event.id, "loan_id": record.id, "old_due_at": str(event.old_due_at), "new_due_at": str(event.new_due_at)})
        _resolve_request_task(db, row, actor_id=row.source_actor_id, resolution="borrow renewed")
        if commit:
            db.commit()
            db.refresh(row)
        return row
    except Exception:
        if commit:
            db.rollback()
        raise


def cancel_service_request(db: Session, request_code: str, *, actor_type: str, actor_id: str, reason: str = "cancelled", commit: bool = True) -> CirculationServiceRequest:
    try:
        row = get_service_request(db, request_code)
        if row.status in TERMINAL_STATUSES:
            raise BusinessRuleError("Circulation request is already closed.", details={"status": row.status})
        book_id_to_recalc = None
        if row.request_type == "borrow" and row.copy_id:
            copy = db.get(BookCopy, row.copy_id)
            if copy and copy.copy_status == "reserved":
                old = copy.copy_status
                copy.copy_status = "available"
                write_status_event(db, copy, old, "available", "cancel_borrow_service_request", actor_type, actor_id)
                book_id_to_recalc = copy.book_id
        # 如果该请求关联了预约，同步取消预约
        if row.reservation_id:
            reservation = db.get(Reservation, row.reservation_id)
            if reservation and reservation.status in ("ready_for_pickup", "waiting"):
                reservation.status = "cancelled"
                reservation.updated_at = now()
                db.add(ReservationEvent(reservation_id=reservation.id, event_type="cancelled", actor_code=actor_id, event_time=utc_text(), detail=f"reason=cancel_borrow_service_request;via_service_request={row.request_code}"))
                if not book_id_to_recalc:
                    book_id_to_recalc = reservation.book_id
        # 在副本和预约状态都更新后再刷新库存缓存
        if book_id_to_recalc:
            recalculate_book_inventory(db, book_id_to_recalc)
        row.status = "cancelled"
        row.cancelled_at = now()
        row.failure_reason = reason
        row.updated_at = now()
        _resolve_request_task(db, row, actor_id=actor_id, resolution=f"request cancelled: {reason}")
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="cancel_circulation_service_request", target_table="circulation_service_requests", target_id=row.request_code, detail={"reason": reason})
        if commit:
            db.commit()
            db.refresh(row)
        return row
    except Exception:
        if commit:
            db.rollback()
        raise


def expire_service_requests(db: Session, *, request_code: str | None = None, commit: bool = True) -> int:
    try:
        stmt = select(CirculationServiceRequest).where(
            CirculationServiceRequest.status.in_(["pending", "ready"]),
            CirculationServiceRequest.expires_at != None,
            CirculationServiceRequest.expires_at < now(),
        )
        if request_code:
            stmt = stmt.where(CirculationServiceRequest.request_code == request_code)
        rows = db.scalars(stmt).all()
        count = 0
        for row in rows:
            book_id_to_recalc = None
            if row.request_type == "borrow" and row.copy_id:
                copy = db.get(BookCopy, row.copy_id)
                if copy and copy.copy_status == "reserved":
                    old = copy.copy_status
                    copy.copy_status = "available"
                    write_status_event(db, copy, old, "available", "expire_borrow_service_request", "system", "circulation_request_expirer")
                    book_id_to_recalc = copy.book_id
            # 如果该请求关联了预约，同步将预约标记为过期
            if row.reservation_id:
                reservation = db.get(Reservation, row.reservation_id)
                if reservation and reservation.status in ("ready_for_pickup", "waiting"):
                    reservation.status = "expired"
                    reservation.updated_at = now()
                    db.add(ReservationEvent(reservation_id=reservation.id, event_type="expired", actor_code="circulation_request_expirer", event_time=utc_text(), detail=f"via_service_request={row.request_code}"))
                    if not book_id_to_recalc:
                        book_id_to_recalc = reservation.book_id
            # 在副本和预约状态都更新后再刷新库存缓存
            if book_id_to_recalc:
                recalculate_book_inventory(db, book_id_to_recalc)
            row.status = "expired"
            row.failure_reason = "expired"
            row.updated_at = now()
            _resolve_request_task(db, row, actor_id="circulation_request_expirer", resolution="request expired")
            count += 1
        if commit:
            db.commit()
        return count
    except Exception:
        if commit:
            db.rollback()
        raise
