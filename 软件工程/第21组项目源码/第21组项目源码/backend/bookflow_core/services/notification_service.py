from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from bookflow_core.core.exceptions import BusinessRuleError, NotFoundError
from bookflow_core.core.time import now
from bookflow_core.models import (
    NotificationDelivery,
    NotificationMessage,
    ReaderAccount,
)
from bookflow_core.services.common import write_audit
from bookflow_core.services.notification_utils import (
    active_admin_ids as _active_admin_ids,
    delivery_code as _delivery_code,
    int_rule as _int_rule,
    make_idempotency_key as _make_idempotency_key,
    message_code as _message_code,
)


# ===================================================================
# 新通知中心核心函数 —— 两层模型（message + delivery）
# ===================================================================

LIFECYCLE_TRANSITIONS = {
    "draft": {"queued", "cancelled"},
    "queued": {"sending", "cancelled"},
    "sending": {"completed", "failed"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


def _transition_message(
    message: NotificationMessage,
    target: str,
    *,
    db: Session,
    actor_type: str = "system",
    actor_id: str = "system",
) -> None:
    if target not in LIFECYCLE_TRANSITIONS.get(message.lifecycle_status, set()):
        raise BusinessRuleError(
            f"不能将消息从 {message.lifecycle_status} 转为 {target}。",
            code="NOTIFICATION_TRANSITION_INVALID",
            details={
                "message_code": message.message_code,
                "from": message.lifecycle_status,
                "to": target,
            },
        )
    message.lifecycle_status = target
    message.updated_at = now()
    write_audit(
        db,
        actor_type=actor_type,
        actor_id=actor_id,
        action=f"message_{target}",
        target_table="notification_messages",
        target_id=message.message_code,
        detail={"lifecycle_status": target},
    )


# ---- 创建消息 ----

def create_message(
    db: Session,
    *,
    title: str,
    content: str,
    notification_type: str = "general",
    source_type: str = "manual",
    source_task_code: str | None = None,
    related_entity_type: str | None = None,
    related_entity_id: str | None = None,
    target_scope_json: str | None = None,
    lifecycle_status: str = "draft",
    scheduled_at: datetime | None = None,
    created_by_type: str = "admin",
    created_by_code: str = "system",
    idempotency_key: str | None = None,
    actor_type: str = "admin",
    actor_id: str = "system",
    commit: bool = True,
) -> NotificationMessage:
    try:
        if lifecycle_status not in LIFECYCLE_TRANSITIONS:
            raise BusinessRuleError(
                f"无效的生命周期状态: {lifecycle_status}",
                code="NOTIFICATION_INVALID_STATUS",
            )
        if idempotency_key:
            existing = db.scalar(
                select(NotificationMessage).where(
                    NotificationMessage.idempotency_key == idempotency_key
                )
            )
            if existing:
                return existing

        stamp = now()
        row = NotificationMessage(
            message_code=_message_code(),
            title=title,
            content=content,
            notification_type=notification_type,
            source_type=source_type,
            source_task_code=source_task_code,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            target_scope_json=target_scope_json,
            lifecycle_status=lifecycle_status,
            scheduled_at=scheduled_at,
            created_by_type=created_by_type,
            created_by_code=created_by_code,
            idempotency_key=idempotency_key,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(row)
        db.flush()
        write_audit(
            db,
            actor_type=actor_type,
            actor_id=actor_id,
            action="create_message",
            target_table="notification_messages",
            target_id=row.message_code,
            detail={
                "title": title,
                "notification_type": notification_type,
                "lifecycle_status": lifecycle_status,
            },
        )
        if commit:
            db.commit()
            db.refresh(row)
        return row
    except Exception:
        if commit:
            db.rollback()
        raise


# ---- 创建投递记录 ----

def create_deliveries(
    db: Session,
    *,
    message_id: int,
    recipients: list[dict],
    channel: str = "in_app",
    actor_type: str = "admin",
    actor_id: str = "system",
    commit: bool = True,
) -> dict:
    """为消息创建投递记录。每个 recipient 需要包含 recipient_type 和 recipient_id。

    自动生成 idempotency_key 避免重复投递：
      message:{message_code}:{recipient_type}:{recipient_id}
    """
    try:
        message = db.get(NotificationMessage, message_id)
        if not message:
            raise NotFoundError(
                "NotificationMessage not found.",
                details={"message_id": message_id},
            )

        created = 0
        skipped = 0
        stamp = now()

        for item in recipients:
            rtype = item.get("recipient_type", "reader")
            rid = item.get("recipient_id")
            if rid is None:
                continue

            ikey = (
                f"message:{message.message_code}:{rtype}:{rid}"
            )
            existing = db.scalar(
                select(NotificationDelivery).where(
                    NotificationDelivery.idempotency_key == ikey
                )
            )
            if existing:
                skipped += 1
                continue

            delivery = NotificationDelivery(
                delivery_code=_delivery_code(),
                message_id=message.id,
                recipient_type=rtype,
                recipient_id=rid,
                channel=channel,
                delivery_status="queued",
                read_status="unread",
                idempotency_key=ikey,
                created_at=stamp,
                updated_at=stamp,
            )
            db.add(delivery)
            created += 1

        if created > 0:
            db.flush()

        write_audit(
            db,
            actor_type=actor_type,
            actor_id=actor_id,
            action="create_deliveries",
            target_table="notification_deliveries",
            target_id=message.message_code,
            detail={
                "message_id": message.id,
                "created": created,
                "skipped": skipped,
            },
        )
        if commit:
            db.commit()
        return {
            "message_code": message.message_code,
            "created_count": created,
            "skipped_count": skipped,
        }
    except Exception:
        if commit:
            db.rollback()
        raise


# ---- 发送消息 ----

def send_message(
    db: Session,
    message_id: int,
    *,
    actor_type: str = "admin",
    actor_id: str = "system",
    commit: bool = True,
) -> dict:
    """发送消息：将 lifecycle 转为 sending -> completed，将所有 queued delivery 标记为 sent。

    若当前为 draft，先转为 queued 再转 sending。
    """
    try:
        message = db.get(NotificationMessage, message_id)
        if not message:
            raise NotFoundError(
                "NotificationMessage not found.",
                details={"message_id": message_id},
            )
        if message.lifecycle_status not in ("draft", "queued"):
            raise BusinessRuleError(
                f"只有草稿或待发送状态的消息才能发送，当前状态: {message.lifecycle_status}",
                code="NOTIFICATION_CANNOT_SEND",
            )

        # draft → queued（如需要）
        if message.lifecycle_status == "draft":
            _transition_message(
                message, "queued", db=db, actor_type=actor_type, actor_id=actor_id
            )

        _transition_message(
            message, "sending", db=db, actor_type=actor_type, actor_id=actor_id
        )

        stamp = now()
        sent_count = 0
        failed_count = 0

        deliveries = db.scalars(
            select(NotificationDelivery).where(
                NotificationDelivery.message_id == message.id,
                NotificationDelivery.delivery_status == "queued",
            )
        ).all()

        for d in deliveries:
            d.delivery_status = "sent"
            d.sent_at = stamp
            d.updated_at = stamp
            sent_count += 1

        if sent_count == 0:
            # 没有投递记录也算完成
            _transition_message(
                message,
                "completed",
                db=db,
                actor_type=actor_type,
                actor_id=actor_id,
            )
        else:
            _transition_message(
                message,
                "completed",
                db=db,
                actor_type=actor_type,
                actor_id=actor_id,
            )

        write_audit(
            db,
            actor_type=actor_type,
            actor_id=actor_id,
            action="send_message",
            target_table="notification_messages",
            target_id=message.message_code,
            detail={
                "sent_count": sent_count,
                "failed_count": failed_count,
            },
        )
        if commit:
            db.commit()
        return {
            "message_code": message.message_code,
            "sent_count": sent_count,
            "failed_count": failed_count,
        }
    except Exception:
        if commit:
            db.rollback()
        raise


def cancel_message(
    db: Session,
    message_id: int,
    *,
    actor_type: str = "admin",
    actor_id: str = "system",
    commit: bool = True,
) -> dict:
    """取消草稿或待发送消息，并跳过尚未投递的 delivery。"""
    try:
        message = db.get(NotificationMessage, message_id)
        if not message:
            raise NotFoundError(
                "NotificationMessage not found.",
                details={"message_id": message_id},
            )
        if message.lifecycle_status not in ("draft", "queued"):
            raise BusinessRuleError(
                f"只有草稿或待发送状态的消息才能取消，当前状态: {message.lifecycle_status}",
                code="NOTIFICATION_CANNOT_CANCEL",
            )

        _transition_message(
            message,
            "cancelled",
            db=db,
            actor_type=actor_type,
            actor_id=actor_id,
        )

        stamp = now()
        skipped_count = 0
        deliveries = db.scalars(
            select(NotificationDelivery).where(
                NotificationDelivery.message_id == message.id,
                NotificationDelivery.delivery_status == "queued",
            )
        ).all()
        for delivery in deliveries:
            delivery.delivery_status = "skipped"
            delivery.failed_reason = "message_cancelled"
            delivery.updated_at = stamp
            skipped_count += 1

        write_audit(
            db,
            actor_type=actor_type,
            actor_id=actor_id,
            action="cancel_message",
            target_table="notification_messages",
            target_id=message.message_code,
            detail={"skipped_count": skipped_count},
        )
        if commit:
            db.commit()
        return {
            "message_code": message.message_code,
            "skipped_count": skipped_count,
            "status": "cancelled",
        }
    except Exception:
        if commit:
            db.rollback()
        raise


# ---- 管理员通知中心 ----

def message_to_dict(row: NotificationMessage, db: Session) -> dict:
    """将消息主体转为前端可用的字典，包含投递统计。"""
    total_deliveries = int(
        db.scalar(
            select(func.count(NotificationDelivery.id)).where(
                NotificationDelivery.message_id == row.id
            )
        )
        or 0
    )
    sent_deliveries = int(
        db.scalar(
            select(func.count(NotificationDelivery.id)).where(
                NotificationDelivery.message_id == row.id,
                NotificationDelivery.delivery_status == "sent",
            )
        )
        or 0
    )
    failed_deliveries = int(
        db.scalar(
            select(func.count(NotificationDelivery.id)).where(
                NotificationDelivery.message_id == row.id,
                NotificationDelivery.delivery_status == "failed",
            )
        )
        or 0
    )
    read_deliveries = int(
        db.scalar(
            select(func.count(NotificationDelivery.id)).where(
                NotificationDelivery.message_id == row.id,
                NotificationDelivery.read_status == "read",
            )
        )
        or 0
    )
    return {
        "id": row.id,
        "message_code": row.message_code,
        "title": row.title,
        "content": row.content,
        "notification_type": row.notification_type,
        "source_type": row.source_type,
        "source_task_code": row.source_task_code,
        "related_entity_type": row.related_entity_type,
        "related_entity_id": row.related_entity_id,
        "target_scope_json": row.target_scope_json,
        "lifecycle_status": row.lifecycle_status,
        "scheduled_at": str(row.scheduled_at) if row.scheduled_at else None,
        "created_by_type": row.created_by_type,
        "created_by_code": row.created_by_code,
        "total_deliveries": total_deliveries,
        "sent_deliveries": sent_deliveries,
        "failed_deliveries": failed_deliveries,
        "read_deliveries": read_deliveries,
        "unread_deliveries": total_deliveries - read_deliveries,
        "created_at": str(row.created_at) if row.created_at else None,
        "updated_at": str(row.updated_at) if row.updated_at else None,
    }


def list_messages_for_admin(
    db: Session,
    *,
    notification_type: str | None = None,
    lifecycle_status: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """管理员通知中心 —— 展示 message 列表和投递统计。"""
    stmt = select(NotificationMessage)
    if lifecycle_status:
        stmt = stmt.where(
            NotificationMessage.lifecycle_status == lifecycle_status
        )
    if notification_type:
        if notification_type == "other":
            stmt = stmt.where(
                NotificationMessage.notification_type.notin_([
                    "system", "due", "due_reminder", "overdue",
                    "overdue_reminder", "reservation", "reservation_ready", "task",
                ])
            )
        else:
            stmt = stmt.where(
                NotificationMessage.notification_type == notification_type
            )
    if keyword:
        text = keyword.strip()
        stmt = stmt.where(
            or_(
                NotificationMessage.message_code.contains(text),
                NotificationMessage.title.contains(text),
                NotificationMessage.content.contains(text),
            )
        )

    total = int(
        db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    )
    rows = db.scalars(
        stmt.order_by(NotificationMessage.id.desc()).offset(offset).limit(limit)
    ).all()

    return {
        "items": [message_to_dict(row, db) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def message_stats(db: Session) -> dict:
    """管理员通知中心统计卡片数据。"""
    draft_count = int(
        db.scalar(
            select(func.count(NotificationMessage.id)).where(
                NotificationMessage.lifecycle_status == "draft"
            )
        )
        or 0
    )
    queued_count = int(
        db.scalar(
            select(func.count(NotificationMessage.id)).where(
                NotificationMessage.lifecycle_status == "queued"
            )
        )
        or 0
    )
    completed_count = int(
        db.scalar(
            select(func.count(NotificationMessage.id)).where(
                NotificationMessage.lifecycle_status == "completed"
            )
        )
        or 0
    )
    failed_message_count = int(
        db.scalar(
            select(func.count(NotificationMessage.id)).where(
                NotificationMessage.lifecycle_status == "failed"
            )
        )
        or 0
    )

    today_start = now().replace(hour=0, minute=0, second=0, microsecond=0)
    sent_today = int(
        db.scalar(
            select(func.count(NotificationDelivery.id)).where(
                NotificationDelivery.sent_at >= today_start,
                NotificationDelivery.delivery_status == "sent",
            )
        )
        or 0
    )
    failed_delivery_count = int(
        db.scalar(
            select(func.count(NotificationDelivery.id)).where(
                NotificationDelivery.delivery_status == "failed"
            )
        )
        or 0
    )

    return {
        "draft_queued_count": draft_count + queued_count,
        "completed_count": completed_count,
        "failed_message_count": failed_message_count,
        "failed_delivery_count": failed_delivery_count,
        "sent_today_count": sent_today,
    }


# ---- 读者端投递查询 ----

def delivery_to_dict(row: NotificationDelivery, db: Session) -> dict:
    """将投递记录转为读者端字典。"""
    message = db.get(NotificationMessage, row.message_id) if row.message_id else None
    return {
        "id": row.id,
        "delivery_code": row.delivery_code,
        "message_id": row.message_id,
        "title": message.title if message else "—",
        "content": message.content if message else "—",
        "notification_type": message.notification_type if message else "general",
        "recipient_type": row.recipient_type,
        "recipient_id": row.recipient_id,
        "channel": row.channel,
        "delivery_status": row.delivery_status,
        "read_status": row.read_status,
        "sent_at": str(row.sent_at) if row.sent_at else None,
        "read_at": str(row.read_at) if row.read_at else None,
        "related_entity_type": message.related_entity_type if message else None,
        "related_entity_id": message.related_entity_id if message else None,
        "created_at": str(row.created_at) if row.created_at else None,
        "updated_at": str(row.updated_at) if row.updated_at else None,
    }


def list_deliveries_for_reader(
    db: Session,
    reader_id: int,
    *,
    read_status: str | None = None,
    notification_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """读者端通知列表 —— 只返回已发送且未归档的投递。"""
    stmt = select(NotificationDelivery).where(
        NotificationDelivery.recipient_type == "reader",
        NotificationDelivery.recipient_id == reader_id,
        NotificationDelivery.delivery_status == "sent",
        NotificationDelivery.archived_at == None,
    )
    if read_status:
        stmt = stmt.where(NotificationDelivery.read_status == read_status)
    if notification_type:
        if notification_type == "other":
            known_types = {"due", "reservation", "system", "activity", "borrow", "task", "overdue"}
            msg_ids = select(NotificationMessage.id).where(
                NotificationMessage.notification_type.notin_(known_types)
            )
        else:
            msg_ids = select(NotificationMessage.id).where(
                NotificationMessage.notification_type == notification_type
            )
        stmt = stmt.where(NotificationDelivery.message_id.in_(msg_ids))

    total = int(
        db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    )
    rows = db.scalars(
        stmt.order_by(NotificationDelivery.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    return {
        "items": [delivery_to_dict(row, db) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def list_deliveries_for_admin_inbox(
    db: Session,
    admin_id: int,
    *,
    read_status: str | None = None,
    notification_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """管理员收件箱 —— 返回发给当前管理员的已发送投递。"""
    stmt = select(NotificationDelivery).where(
        NotificationDelivery.recipient_type == "admin",
        NotificationDelivery.recipient_id == admin_id,
        NotificationDelivery.delivery_status == "sent",
        NotificationDelivery.archived_at == None,
    )
    if read_status:
        stmt = stmt.where(NotificationDelivery.read_status == read_status)
    if notification_type:
        msg_ids = select(NotificationMessage.id).where(
            NotificationMessage.notification_type == notification_type
        )
        stmt = stmt.where(NotificationDelivery.message_id.in_(msg_ids))

    total = int(
        db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    )
    rows = db.scalars(
        stmt.order_by(NotificationDelivery.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    return {
        "items": [delivery_to_dict(row, db) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def reader_delivery_summary(db: Session, reader_id: int) -> dict:
    """读者端通知概览统计。"""
    base = select(NotificationDelivery).where(
        NotificationDelivery.recipient_type == "reader",
        NotificationDelivery.recipient_id == reader_id,
        NotificationDelivery.delivery_status == "sent",
        NotificationDelivery.archived_at == None,
    )
    total = int(
        db.scalar(select(func.count()).select_from(base.subquery())) or 0
    )
    unread = int(
        db.scalar(
            select(func.count(NotificationDelivery.id)).where(
                NotificationDelivery.recipient_type == "reader",
                NotificationDelivery.recipient_id == reader_id,
                NotificationDelivery.delivery_status == "sent",
                NotificationDelivery.archived_at == None,
                NotificationDelivery.read_status == "unread",
            )
        )
        or 0
    )

    # 按类型统计
    by_type: dict[str, int] = {}
    rows = db.execute(
        select(
            NotificationMessage.notification_type,
            func.count(NotificationDelivery.id),
        )
        .join(
            NotificationMessage,
            NotificationDelivery.message_id == NotificationMessage.id,
        )
        .where(
            NotificationDelivery.recipient_type == "reader",
            NotificationDelivery.recipient_id == reader_id,
            NotificationDelivery.delivery_status == "sent",
            NotificationDelivery.archived_at == None,
        )
        .group_by(NotificationMessage.notification_type)
    ).all()
    for ntype, count in rows:
        by_type[ntype or "other"] = int(count or 0)

    known_types = {"due", "reservation", "system", "activity", "borrow", "task", "overdue"}
    other_count = sum(count for ntype, count in by_type.items() if ntype not in known_types)
    by_type["other"] = other_count

    return {"total": total, "unread": unread, "byType": by_type}


# ---- 标记已读 ----

def mark_delivery_read(
    db: Session,
    delivery_id: int,
    *,
    recipient_type: str = "reader",
    recipient_id: int,
    actor_type: str = "reader",
    actor_id: str = "reader",
    commit: bool = True,
) -> dict:
    """标记单条投递为已读，校验接收人身份。"""
    try:
        row = db.get(NotificationDelivery, delivery_id)
        if not row:
            raise NotFoundError(
                "投递记录未找到。",
                code="NOTIFICATION_NOT_FOUND",
                details={"delivery_id": delivery_id},
            )
        if (
            row.recipient_type != recipient_type
            or row.recipient_id != recipient_id
        ):
            raise BusinessRuleError(
                "不能操作其他读者的通知。",
                code="NOTIFICATION_NOT_FOUND",
                details={"delivery_id": delivery_id},
            )
        if row.read_status == "read":
            return delivery_to_dict(row, db)

        row.read_status = "read"
        row.read_at = now()
        row.updated_at = now()

        write_audit(
            db,
            actor_type=actor_type,
            actor_id=actor_id,
            action="mark_delivery_read",
            target_table="notification_deliveries",
            target_id=row.delivery_code,
            detail={
                "delivery_id": row.id,
                "recipient_type": recipient_type,
                "recipient_id": recipient_id,
            },
        )
        if commit:
            db.commit()
            db.refresh(row)
        return delivery_to_dict(row, db)
    except Exception:
        if commit:
            db.rollback()
        raise


def mark_all_reader_deliveries_read(
    db: Session,
    reader_id: int,
    *,
    actor_type: str = "reader",
    actor_id: str = "reader",
    commit: bool = True,
) -> dict:
    """读者一键全部标为已读。"""
    try:
        rows = db.scalars(
            select(NotificationDelivery).where(
                NotificationDelivery.recipient_type == "reader",
                NotificationDelivery.recipient_id == reader_id,
                NotificationDelivery.delivery_status == "sent",
                NotificationDelivery.archived_at == None,
                NotificationDelivery.read_status == "unread",
            )
        ).all()
        stamp = now()
        for row in rows:
            row.read_status = "read"
            row.read_at = stamp
            row.updated_at = stamp
        if commit:
            db.commit()
        return {"updated": len(rows)}
    except Exception:
        if commit:
            db.rollback()
        raise


def archive_read_reader_deliveries(
    db: Session,
    reader_id: int,
    *,
    actor_type: str = "reader",
    actor_id: str = "reader",
    commit: bool = True,
) -> dict:
    """读者清空已读 —— 归档已读投递，不物理删除，不影响消息主体。"""
    try:
        rows = db.scalars(
            select(NotificationDelivery).where(
                NotificationDelivery.recipient_type == "reader",
                NotificationDelivery.recipient_id == reader_id,
                NotificationDelivery.delivery_status == "sent",
                NotificationDelivery.read_status == "read",
                NotificationDelivery.archived_at == None,
            )
        ).all()
        stamp = now()
        for row in rows:
            row.archived_at = stamp
            row.updated_at = stamp
        if commit:
            db.commit()
        return {"archived": len(rows)}
    except Exception:
        if commit:
            db.rollback()
        raise


from bookflow_core.services.notification_reminder_service import (
    create_due_reminders,
    create_overdue_reminders,
    create_reservation_ready_reminders,
    create_task_notifications,
)
