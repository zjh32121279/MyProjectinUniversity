from __future__ import annotations

import hashlib
import secrets

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session

from bookflow_core.core.exceptions import BookFlowError, BusinessRuleError, NotFoundError, ValidationError
from bookflow_core.core.security import hash_password
from bookflow_core.core.time import now
from bookflow_core.models import CirculationRule, Loan, ReaderAccount, ReaderCreditEvent, ReaderCredential, ReaderNotificationSetting, ReaderStatusEvent, Reservation
from bookflow_core.services.common import utc_text, write_audit
from bookflow_core.services.statistics_service import ACTIVE_RESERVATION_STATUSES

VALID_READER_TYPES = {"child", "teen", "adult", "senior", "institution"}
VALID_READER_STATUSES = {"active", "inactive", "suspended"}
READER_PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"


def _generate_reader_password(length: int = 10) -> str:
    return "".join(secrets.choice(READER_PASSWORD_ALPHABET) for _ in range(length))


def _account_hash(value: str | None) -> str | None:
    text = str(value or "").strip()
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None


def _credential_for_reader(db: Session, reader_id: int) -> ReaderCredential | None:
    return db.scalar(select(ReaderCredential).where(ReaderCredential.reader_id == reader_id).order_by(ReaderCredential.id))


def _looks_like_raw_phone(value: str | None) -> bool:
    text = str(value or "").strip()
    return text.isdigit() and len(text) >= 6


def _ensure_reader_notification_setting(db: Session, reader: ReaderAccount) -> None:
    existing = db.scalar(select(ReaderNotificationSetting).where(ReaderNotificationSetting.reader_id == reader.id).order_by(ReaderNotificationSetting.id))
    if existing:
        return
    db.add(
        ReaderNotificationSetting(
            reader_id=reader.id,
            borrow_due_enabled=True,
            reservation_arrival_enabled=True,
            system_notice_enabled=True,
            email_enabled=bool(reader.email),
            sms_enabled=_looks_like_raw_phone(reader.phone_masked),
            created_at=now(),
            updated_at=now(),
        )
    )


def _create_reader_credential(db: Session, reader: ReaderAccount, *, password: str) -> ReaderCredential:
    credential = ReaderCredential(
        reader_id=reader.id,
        login_name=reader.reader_code,
        phone_hash=_account_hash(reader.phone_masked) if _looks_like_raw_phone(reader.phone_masked) else None,
        email=reader.email or None,
        password_hash=hash_password(password),
        status="active",
        created_at=now(),
        updated_at=now(),
    )
    db.add(credential)
    return credential


def _credit_score_column():
    return cast(ReaderAccount.credit_score, Integer)


def _reader_credit_score(reader: ReaderAccount) -> int:
    try:
        return int(float(reader.credit_score or 0))
    except (TypeError, ValueError):
        return 0


def reader_borrow_suspended(reader: ReaderAccount) -> bool:
    return reader.status == "suspended" or bool(reader.borrow_suspended_until)


def _write_reader_status_event(db: Session, reader: ReaderAccount, *, old_status: str | None, new_status: str, reason: str, actor_id: str) -> None:
    db.add(ReaderStatusEvent(reader_id=reader.id, old_status=old_status, new_status=new_status, reason=reason, actor_code=actor_id, created_at=utc_text()))


def get_reader(db: Session, reader_code: str) -> ReaderAccount:
    reader = db.scalar(select(ReaderAccount).where(ReaderAccount.reader_code == reader_code))
    if not reader:
        raise NotFoundError("ReaderAccount not found.", details={"reader_code": reader_code})
    return reader


def list_readers(
    db: Session,
    *,
    reader_type_code: str | None = None,
    status: str | None = None,
    credit_status: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    stmt = select(ReaderAccount)
    if reader_type_code:
        stmt = stmt.where(ReaderAccount.reader_type_code == reader_type_code)
    if status:
        stmt = stmt.where(ReaderAccount.status == status)
    credit_score = _credit_score_column()
    if credit_status == "good":
        stmt = stmt.where(credit_score >= 80, ReaderAccount.status != "suspended")
    elif credit_status == "limited":
        stmt = stmt.where(credit_score >= 60, credit_score < 80, ReaderAccount.status != "suspended")
    elif credit_status == "suspended":
        stmt = stmt.where(ReaderAccount.status == "suspended")
    if keyword:
        stmt = stmt.where(ReaderAccount.name.contains(keyword) | ReaderAccount.reader_code.contains(keyword) | ReaderAccount.phone_masked.contains(keyword))
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    items = db.scalars(stmt.order_by(ReaderAccount.id).offset(offset).limit(limit)).all()
    return {"items": [reader_to_dict(row, db) for row in items], "total": total, "limit": limit, "offset": offset}


def create_reader(
    db: Session,
    *,
    reader_code: str,
    name: str,
    reader_type_code: str,
    phone_masked: str = "",
    email: str = "",
    actor_type: str = "admin",
    actor_id: str = "admin",
    commit: bool = True,
) -> ReaderAccount:
    if reader_type_code not in VALID_READER_TYPES:
        raise ValidationError("Invalid reader_type_code.", details={"reader_type_code": reader_type_code})
    try:
        if db.scalar(select(ReaderAccount).where(ReaderAccount.reader_code == reader_code)):
            raise BusinessRuleError("ReaderAccount code already exists.", details={"reader_code": reader_code})
        reader = ReaderAccount(
            reader_code=reader_code,
            name=name,
            reader_type_code=reader_type_code,
            reader_type_name=reader_type_code,
            phone_masked=phone_masked,
            email=email,
            status="active",
            credit_score="100",
            current_borrow_count=0,
        )
        db.add(reader)
        db.flush()
        initial_password = _generate_reader_password()
        _create_reader_credential(db, reader, password=initial_password)
        _ensure_reader_notification_setting(db, reader)
        setattr(reader, "_initial_password", initial_password)
        write_audit(
            db,
            actor_type=actor_type,
            actor_id=actor_id,
            action="create_reader",
            target_table="reader_accounts",
            target_id=reader.reader_code,
            detail={"reader_type_code": reader_type_code, "login_name": reader.reader_code, "initial_password_issued": True},
        )
        if commit:
            db.commit()
            db.refresh(reader)
            setattr(reader, "_initial_password", initial_password)
        return reader
    except Exception:
        if commit:
            db.rollback()
        raise


def update_reader(
    db: Session,
    reader_code: str,
    *,
    name: str | None = None,
    reader_type_code: str | None = None,
    phone_masked: str | None = None,
    email: str | None = None,
    status: str | None = None,
    actor_type: str = "admin",
    actor_id: str = "admin",
    commit: bool = True,
) -> ReaderAccount:
    try:
        reader = get_reader(db, reader_code)
        before = reader_to_dict(reader)
        if reader_type_code is not None:
            if reader_type_code not in VALID_READER_TYPES:
                raise ValidationError("Invalid reader_type_code.", details={"reader_type_code": reader_type_code})
            reader.reader_type_code = reader_type_code
            reader.reader_type_name = reader_type_code
        if status is not None:
            if status not in VALID_READER_STATUSES:
                raise ValidationError("Invalid reader status.", details={"status": status})
            old_status = reader.status
            reader.status = status
            if old_status != status:
                _write_reader_status_event(db, reader, old_status=old_status, new_status=status, reason="update_reader", actor_id=actor_id)
        if name is not None:
            reader.name = name
        if phone_masked is not None:
            reader.phone_masked = phone_masked
        if email is not None:
            reader.email = email
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="update_reader", target_table="reader_accounts", target_id=reader.reader_code, detail={"before": before, "after": reader_to_dict(reader)})
        if commit:
            db.commit()
            db.refresh(reader)
        return reader
    except Exception:
        if commit:
            db.rollback()
        raise


def adjust_credit(db: Session, reader_code: str, *, delta: int, reason: str, actor_type: str = "admin", actor_id: str = "admin", related_loan_id: int | None = None, commit: bool = True) -> ReaderCreditEvent:
    try:
        reader = get_reader(db, reader_code)
        old_score = _reader_credit_score(reader)
        old_status = reader.status
        new_score = max(0, min(100, old_score + int(delta)))
        reader.credit_score = str(new_score)
        if new_score < 60:
            reader.status = "suspended"
        elif new_score >= 60 and reason in {"manual_restore", "credit_restore", "good_behavior"}:
            reader.status = "active"
        if old_status != reader.status:
            _write_reader_status_event(db, reader, old_status=old_status, new_status=reader.status, reason=reason, actor_id=actor_id)
        event = ReaderCreditEvent(reader_id=reader.id, delta=str(new_score - old_score), old_score=str(old_score), new_score=str(new_score), reason=reason, related_loan_id=related_loan_id, actor_code=actor_id, created_at=utc_text())
        db.add(event)
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="adjust_reader_credit", target_table="reader_accounts", target_id=reader.reader_code, detail={"old_score": old_score, "new_score": new_score, "reason": reason})
        if commit:
            db.commit()
            db.refresh(event)
        return event
    except Exception:
        if commit:
            db.rollback()
        raise


def suspend_reader(db: Session, reader_code: str, *, reason: str = "manual_suspend", actor_type: str = "admin", actor_id: str = "admin", commit: bool = True) -> ReaderAccount:
    try:
        reader = get_reader(db, reader_code)
        old_status = reader.status
        reader.status = "suspended"
        if old_status != "suspended":
            _write_reader_status_event(db, reader, old_status=old_status, new_status="suspended", reason=reason, actor_id=actor_id)
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="suspend_reader", target_table="reader_accounts", target_id=reader.reader_code, detail={"reason": reason})
        if commit:
            db.commit()
            db.refresh(reader)
        return reader
    except Exception:
        if commit:
            db.rollback()
        raise


def restore_reader(db: Session, reader_code: str, *, reason: str = "manual_restore", actor_type: str = "admin", actor_id: str = "admin", commit: bool = True) -> ReaderAccount:
    try:
        reader = get_reader(db, reader_code)
        credit_score = _reader_credit_score(reader)
        if credit_score < 60:
            raise BusinessRuleError("ReaderAccount credit is below suspension threshold; restore credit first.", details={"credit_score": credit_score})
        old_status = reader.status
        reader.status = "active"
        if old_status != "active":
            _write_reader_status_event(db, reader, old_status=old_status, new_status="active", reason=reason, actor_id=actor_id)
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="restore_reader", target_table="reader_accounts", target_id=reader.reader_code, detail={"reason": reason})
        if commit:
            db.commit()
            db.refresh(reader)
        return reader
    except Exception:
        if commit:
            db.rollback()
        raise


def reader_activity(db: Session, reader_code: str) -> dict:
    reader = get_reader(db, reader_code)
    loans = db.scalars(
        select(Loan)
        .where(Loan.reader_id == reader.id)
        .order_by(Loan.id.desc())
        .limit(30)
    ).all()
    loan_items: list[dict] = []
    for loan in loans:
        item: dict = {
            "loan_code": loan.loan_code,
            "status": loan.status,
            "borrowed_at": str(loan.borrowed_at) if loan.borrowed_at else None,
            "due_at": str(loan.due_at) if loan.due_at else None,
            "returned_at": str(loan.returned_at) if loan.returned_at else None,
            "renewal_count": loan.renewal_count,
        }
        book = loan.book
        if book:
            item["book_title"] = book.title
            item["book_code"] = book.book_code
        loan_items.append(item)

    status_events = db.scalars(
        select(ReaderStatusEvent)
        .where(ReaderStatusEvent.reader_id == reader.id)
        .order_by(ReaderStatusEvent.id.desc())
        .limit(10)
    ).all()

    credit_events = db.scalars(
        select(ReaderCreditEvent)
        .where(ReaderCreditEvent.reader_id == reader.id)
        .order_by(ReaderCreditEvent.id.desc())
        .limit(10)
    ).all()

    return {
        "reader_code": reader.reader_code,
        "name": reader.name,
        "reader_type_code": reader.reader_type_code,
        "credit_score": _reader_credit_score(reader),
        "status": reader.status,
        "active_borrow_count": int(db.scalar(select(func.count(Loan.id)).where(Loan.reader_id == reader.id, Loan.status.in_(["active", "overdue"]))) or 0),
        "returned_count": int(db.scalar(select(func.count(Loan.id)).where(Loan.reader_id == reader.id, Loan.status == "returned")) or 0),
        "reservation_count": int(db.scalar(select(func.count(Reservation.id)).where(Reservation.reader_id == reader.id, Reservation.status.in_(ACTIVE_RESERVATION_STATUSES))) or 0),
        "loans": loan_items,
        "status_events": [{"old_status": e.old_status, "new_status": e.new_status, "reason": e.reason, "created_at": str(e.created_at)} for e in status_events],
        "credit_events": [{"delta": e.delta, "old_score": e.old_score, "new_score": e.new_score, "reason": e.reason, "created_at": str(e.created_at)} for e in credit_events],
    }


def recent_readers_activity(db: Session, limit: int = 20) -> list[dict]:
    """Recent reader-related events across all readers — for the header '操作记录' button."""
    items: list[dict] = []
    recent_loans = db.scalars(
        select(Loan)
        .where(Loan.status.in_(["active", "returned", "overdue"]))
        .order_by(Loan.id.desc())
        .limit(limit)
    ).all()
    for loan in recent_loans:
        reader = loan.reader
        book = loan.book
        action_label = "归还" if loan.status == "returned" else "续借" if (loan.renewal_count or 0) > 0 else "借阅"
        items.append({
            "type": "loan",
            "action": action_label,
            "reader_name": reader.name if reader else "—",
            "reader_code": reader.reader_code if reader else "—",
            "book_title": book.title if book else "—",
            "loan_code": loan.loan_code,
            "status": loan.status,
            "time": str(loan.borrowed_at) if loan.borrowed_at else str(loan.created_at),
        })

    recent_status = db.scalars(
        select(ReaderStatusEvent)
        .order_by(ReaderStatusEvent.id.desc())
        .limit(limit)
    ).all()
    for event in recent_status:
        reader = db.get(ReaderAccount, event.reader_id) if event.reader_id else None
        items.append({
            "type": "status",
            "action": "状态变更",
            "reader_name": reader.name if reader else "—",
            "reader_code": reader.reader_code if reader else "—",
            "detail": f"{event.old_status} → {event.new_status}",
            "reason": event.reason,
            "time": str(event.created_at),
        })

    items.sort(key=lambda x: str(x.get("time") or ""), reverse=True)
    return items[:limit]


def reader_to_dict(reader: ReaderAccount, db: Session | None = None) -> dict:
    active_borrow_count = None
    max_borrow_count = None
    if db is not None:
        active_borrow_count = int(
            db.scalar(select(func.count(Loan.id)).where(Loan.reader_id == reader.id, Loan.status.in_(["active", "overdue"]))) or 0
        )
        max_borrow_count = db.scalar(
            select(func.max(CirculationRule.max_borrow_count)).where(
                CirculationRule.reader_type_code == reader.reader_type_code,
                CirculationRule.is_active == True,
            )
        )
    credit_score = _reader_credit_score(reader)
    if reader_borrow_suspended(reader):
        credit_label = "暂停"
    elif credit_score >= 80:
        credit_label = "良好"
    elif credit_score < 80:
        credit_label = "受限"
    else:
        credit_label = "一般"
    return {
        "id": reader.id,
        "source_reader_id": reader.source_reader_id,
        "reader_code": reader.reader_code,
        "reader_type_code": reader.reader_type_code,
        "reader_type_name": reader.reader_type_name,
        "name": reader.name,
        "phone_masked": reader.phone_masked,
        "email": reader.email,
        "avatar_url": reader.avatar_url,
        "status": reader.status,
        "credit_score": credit_score,
        "credit_status": credit_label,
        "borrow_suspended_until": reader.borrow_suspended_until,
        "current_borrow_count": active_borrow_count,
        "max_borrow_count": int(max_borrow_count or 0) if max_borrow_count is not None else None,
        "registered_at": str(reader.registered_at or reader.created_at) if (reader.registered_at or reader.created_at) else None,
    }


def admin_reset_reader_password(
    db: Session,
    *,
    reader_code: str,
    new_password: str,
    confirm_password: str,
    actor_type: str = "admin",
    actor_id: str = "admin",
) -> dict:
    from bookflow_core.services.reader_auth_service import _validate_password
    password_value = _validate_password(new_password, confirm_password)
    reader = db.scalar(select(ReaderAccount).where(ReaderAccount.reader_code == reader_code))
    if not reader:
        raise BookFlowError("未找到对应读者账号。", code="READER_NOT_FOUND")
    credential = _credential_for_reader(db, reader.id)
    credential_created = False
    if not credential:
        credential = _create_reader_credential(db, reader, password=password_value)
        credential_created = True
    else:
        credential.password_hash = hash_password(password_value)
        credential.status = "active"
        credential.updated_at = now()
    _ensure_reader_notification_setting(db, reader)
    write_audit(
        db,
        actor_type=actor_type,
        actor_id=actor_id,
        action="reset_reader_password",
        target_table="reader_credentials",
        target_id=reader.reader_code,
        detail={"credential_created": credential_created},
    )
    db.commit()
    return {"reset": True, "reader_code": reader_code, "login_name": credential.login_name or reader.reader_code, "temporary_password": password_value, "credential_created": credential_created}
