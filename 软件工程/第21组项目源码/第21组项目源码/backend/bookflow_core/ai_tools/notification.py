from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from bookflow_core.core.exceptions import BusinessRuleError, NotFoundError
from bookflow_core.models import AdminUser, NotificationDelivery, NotificationMessage, ReaderAccount
from bookflow_core.services.common import create_snapshot
from bookflow_core.services.notification_service import (
    create_deliveries,
    create_message,
    create_task_notifications,
    message_to_dict,
    send_message,
)


def _is_int(value: object) -> bool:
    try:
        int(str(value))
        return True
    except (TypeError, ValueError):
        return False


def _reader_by_identifier(db: Session, value: object | None) -> ReaderAccount:
    text = str(value or "").strip()
    reader = db.get(ReaderAccount, int(text)) if _is_int(text) else None
    if reader is None and text:
        reader = db.scalar(select(ReaderAccount).where(ReaderAccount.reader_code == text))
    if not reader:
        raise NotFoundError("ReaderAccount not found.", code="READER_NOT_FOUND", details={"recipient_id": value})
    return reader


def _admin_by_identifier(db: Session, value: object | None) -> AdminUser:
    text = str(value or "").strip()
    admin = db.get(AdminUser, int(text)) if _is_int(text) else None
    if admin is None and text:
        admin = db.scalar(select(AdminUser).where(AdminUser.admin_code == text))
    if not admin:
        raise NotFoundError("AdminUser not found.", details={"recipient_id": value})
    return admin


def _active_reader_recipients(db: Session) -> list[dict]:
    return [
        {"recipient_type": "reader", "recipient_id": reader_id}
        for reader_id in db.scalars(
            select(ReaderAccount.id)
            .where(ReaderAccount.status == "active")
            .order_by(ReaderAccount.id)
        ).all()
        if reader_id
    ]


def _active_admin_recipients(db: Session) -> list[dict]:
    return [
        {"recipient_type": "admin", "recipient_id": admin_id}
        for admin_id in db.scalars(
            select(AdminUser.id)
            .where(AdminUser.status == "active")
            .order_by(AdminUser.id)
        ).all()
        if admin_id
    ]


def _recipient_targets(db: Session, recipient_type: str, recipient_id: object | None = None) -> list[dict]:
    rtype = str(recipient_type or "").strip().lower()
    if rtype in {"all", "all_readers", "readers"}:
        return _active_reader_recipients(db)
    if rtype in {"all_admins", "admins"}:
        return _active_admin_recipients(db)
    if rtype == "reader":
        return [{"recipient_type": "reader", "recipient_id": _reader_by_identifier(db, recipient_id).id}]
    if rtype == "admin":
        return [{"recipient_type": "admin", "recipient_id": _admin_by_identifier(db, recipient_id).id}]
    raise NotFoundError("Notification recipient type not found.", details={"recipient_type": recipient_type})


def _targets_from_batch_item(db: Session, item: dict) -> list[dict]:
    if item.get("all_admins"):
        return _active_admin_recipients(db)
    if item.get("all_readers"):
        return _active_reader_recipients(db)
    if item.get("recipient_reader_id"):
        reader = db.get(ReaderAccount, int(item["recipient_reader_id"]))
        if not reader:
            raise NotFoundError("ReaderAccount not found.", details={"recipient_reader_id": item["recipient_reader_id"]})
        return [{"recipient_type": "reader", "recipient_id": reader.id}]
    if item.get("recipient_admin_id"):
        admin = db.get(AdminUser, int(item["recipient_admin_id"]))
        if not admin:
            raise NotFoundError("AdminUser not found.", details={"recipient_admin_id": item["recipient_admin_id"]})
        return [{"recipient_type": "admin", "recipient_id": admin.id}]
    return _recipient_targets(db, str(item.get("recipient_type") or ""), item.get("recipient_id"))


def _dedupe_recipients(recipients: list[dict]) -> list[dict]:
    seen: set[tuple[str, int]] = set()
    unique: list[dict] = []
    for item in recipients:
        key = (str(item["recipient_type"]), int(item["recipient_id"]))
        if key in seen:
            continue
        seen.add(key)
        unique.append({"recipient_type": key[0], "recipient_id": key[1]})
    return unique


def _target_scope(recipients: list[dict]) -> str:
    reader_count = sum(1 for item in recipients if item["recipient_type"] == "reader")
    admin_count = sum(1 for item in recipients if item["recipient_type"] == "admin")
    return json.dumps(
        {
            "reader_count": reader_count,
            "admin_count": admin_count,
            "recipient_count": len(recipients),
            "source": "ai",
        },
        ensure_ascii=False,
    )


def _tool_status(message: NotificationMessage) -> str:
    if message.lifecycle_status == "completed":
        return "sent"
    if message.lifecycle_status in {"draft", "queued", "sending"}:
        return "pending"
    return message.lifecycle_status or "unknown"


def _message_tool_dict(db: Session, message: NotificationMessage) -> dict:
    data = message_to_dict(message, db)
    delivery_ids = db.scalars(
        select(NotificationDelivery.id)
        .where(NotificationDelivery.message_id == message.id)
        .order_by(NotificationDelivery.id)
    ).all()
    data.update(
        {
            "notification_id": message.id,
            "status": _tool_status(message),
            "delivery_ids": [int(item) for item in delivery_ids],
            "delivery_count": len(delivery_ids),
        }
    )
    return data


def _create_ai_message(
    db: Session,
    payload: dict,
    *,
    recipients: list[dict],
    actor_id: str,
) -> dict:
    normalized = _dedupe_recipients(recipients)
    if not normalized:
        raise BusinessRuleError("Notification has no deliverable recipients.", code="NOTIFICATION_NO_RECIPIENTS")

    send_immediately = payload.get("send_immediately", True)
    lifecycle_status = str(payload.get("lifecycle_status") or ("queued" if send_immediately else "draft"))
    message = create_message(
        db,
        title=payload["title"],
        content=payload.get("content", ""),
        notification_type=payload.get("notification_type", "ai"),
        source_type="ai",
        source_task_code=payload.get("source_task_code"),
        related_entity_type=payload.get("related_entity_type"),
        related_entity_id=str(payload["related_entity_id"]) if payload.get("related_entity_id") is not None else None,
        target_scope_json=_target_scope(normalized),
        lifecycle_status=lifecycle_status,
        created_by_type="ai_admin",
        created_by_code=actor_id,
        idempotency_key=payload.get("idempotency_key"),
        actor_type="ai_admin",
        actor_id=actor_id,
        commit=False,
    )
    delivery_result = create_deliveries(
        db,
        message_id=message.id,
        recipients=normalized,
        actor_type="ai_admin",
        actor_id=actor_id,
        commit=False,
    )

    send_result = {"sent_count": 0, "failed_count": 0}
    if send_immediately and message.lifecycle_status in {"draft", "queued"}:
        send_result = send_message(
            db,
            message.id,
            actor_type="ai_admin",
            actor_id=actor_id,
            commit=False,
        )

    after = _message_tool_dict(db, message)
    after.update(
        {
            "created_count": delivery_result["created_count"],
            "skipped_count": delivery_result["skipped_count"],
            "sent_count": send_result["sent_count"],
            "failed_count": send_result["failed_count"],
        }
    )
    create_snapshot(
        db,
        action_type="ai_create_notification_message",
        target_table="notification_messages",
        target_id=str(message.id),
        before={},
        after=after,
        actor_type="ai_admin",
        actor_id=actor_id,
        can_rollback=False,
    )
    return after


def ai_create_notification(db: Session, payload: dict, *, actor_id: str) -> dict:
    recipients = _recipient_targets(db, payload["recipient_type"], payload.get("recipient_id"))
    return _create_ai_message(db, payload, recipients=recipients, actor_id=actor_id)


def ai_batch_create_notifications(db: Session, payload: dict, *, actor_id: str) -> dict:
    recipients: list[dict] = []
    for item in payload.get("recipients", []):
        recipients.extend(_targets_from_batch_item(db, item))
    return _create_ai_message(db, payload, recipients=recipients, actor_id=actor_id)


def ai_send_notification(db: Session, payload: dict, *, actor_id: str) -> dict:
    message = db.get(NotificationMessage, int(payload["notification_id"]))
    if not message:
        raise NotFoundError("NotificationMessage not found.", details={"notification_id": payload["notification_id"]})
    if message.lifecycle_status in {"draft", "queued"}:
        send_message(db, message.id, actor_type="ai_admin", actor_id=actor_id, commit=False)
    elif message.lifecycle_status not in {"completed"}:
        raise BusinessRuleError(
            "Current notification message cannot be sent.",
            code="NOTIFICATION_CANNOT_SEND",
            details={"message_id": message.id, "lifecycle_status": message.lifecycle_status},
        )
    return _message_tool_dict(db, message)


def ai_create_task_notifications(db: Session, payload: dict, *, actor_id: str) -> dict:
    return create_task_notifications(db, actor_type="ai_admin", actor_id=actor_id, commit=False)
