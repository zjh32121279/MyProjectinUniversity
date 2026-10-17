from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from bookflow_core.core.time import now
from bookflow_core.models import (
    Loan,
    NotificationDelivery,
    ReaderAccount,
    Reservation,
    WorkTask,
)
from bookflow_core.services.common import write_audit
from bookflow_core.services.notification_utils import (
    active_admin_ids as _active_admin_ids,
    delivery_code as _delivery_code,
    int_rule as _int_rule,
    make_idempotency_key as _make_idempotency_key,
)
from bookflow_core.services.statistics_service import (
    ACTIVE_RESERVATION_STATUSES,
    ACTIVE_TASK_STATUSES,
    get_business_date,
)


def create_message(*args, **kwargs):
    from bookflow_core.services.notification_service import create_message as create_notification_message

    return create_notification_message(*args, **kwargs)


def _transition_message(*args, **kwargs) -> None:
    from bookflow_core.services.notification_service import _transition_message as transition_message

    transition_message(*args, **kwargs)


# ===================================================================
# 提醒类通知 —— 带幂等去重
# ===================================================================
def create_due_reminders(
    db: Session,
    *,
    actor_type: str = "system",
    actor_id: str = "system",
    commit: bool = True,
) -> dict:
    """到期提醒 —— 为即将到期的借阅创建投递。幂等键: due:{reader_id}:{loan_id}:{due_at}"""
    try:
        days_before = _int_rule(db, "due_reminder_days_before", 3)
        business_date = get_business_date(db)
        due = business_date + timedelta(days=days_before)
        records = db.scalars(
            select(Loan).where(
                Loan.due_at == due,
                Loan.status.in_(["active", "overdue"]),
            )
        ).all()

        if not records:
            return {"message_code": "", "created_count": 0, "skipped_count": 0}

        message = create_message(
            db,
            title="图书即将到期提醒",
            content=f"你有图书将在 {days_before} 天后到期，请及时归还或续借。",
            notification_type="due",
            source_type="system",
            lifecycle_status="queued",
            created_by_type="system",
            created_by_code="system",
            actor_type=actor_type,
            actor_id=actor_id,
            commit=False,
        )

        created = 0
        skipped = 0
        stamp = now()
        for record in records:
            reader = db.get(ReaderAccount, record.reader_id)
            if not reader:
                continue
            ikey = _make_idempotency_key(
                "due",
                str(reader.id),
                str(record.id),
                str(record.due_at.date()) if record.due_at else "",
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
                recipient_type="reader",
                recipient_id=reader.id,
                channel="in_app",
                delivery_status="queued",
                read_status="unread",
                idempotency_key=ikey,
                created_at=stamp,
                updated_at=stamp,
            )
            db.add(delivery)
            created += 1

        # 发送消息
        _transition_message(
            message,
            "sending",
            db=db,
            actor_type=actor_type,
            actor_id=actor_id,
        )
        # 将所有 queued delivery 标记为 sent
        for d in db.scalars(
            select(NotificationDelivery).where(
                NotificationDelivery.message_id == message.id,
                NotificationDelivery.delivery_status == "queued",
            )
        ).all():
            d.delivery_status = "sent"
            d.sent_at = stamp
            d.updated_at = stamp
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
            action="create_due_reminders",
            target_table="notification_messages",
            target_id=message.message_code,
            detail={"created": created, "skipped": skipped},
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


def create_overdue_reminders(
    db: Session,
    *,
    actor_type: str = "system",
    actor_id: str = "system",
    commit: bool = True,
) -> dict:
    """逾期提醒 —— 幂等键: overdue:{reader_id}:{loan_id}:{business_date}"""
    try:
        records = db.scalars(
            select(Loan).where(Loan.status == "overdue")
        ).all()

        if not records:
            return {"message_code": "", "created_count": 0, "skipped_count": 0}

        business_date = str(get_business_date(db))
        message = create_message(
            db,
            title="图书逾期提醒",
            content="你有图书已经逾期，请尽快归还。",
            notification_type="overdue",
            source_type="system",
            lifecycle_status="queued",
            created_by_type="system",
            created_by_code="system",
            actor_type=actor_type,
            actor_id=actor_id,
            commit=False,
        )

        created = 0
        skipped = 0
        stamp = now()
        seen = set()

        for record in records:
            reader = db.get(ReaderAccount, record.reader_id)
            if not reader:
                continue
            # 同一读者同一天只提醒一次
            reader_key = f"{reader.id}:{business_date}"
            if reader_key in seen:
                continue
            seen.add(reader_key)

            ikey = _make_idempotency_key(
                "overdue",
                str(reader.id),
                str(record.id),
                business_date,
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
                recipient_type="reader",
                recipient_id=reader.id,
                channel="in_app",
                delivery_status="queued",
                read_status="unread",
                idempotency_key=ikey,
                created_at=stamp,
                updated_at=stamp,
            )
            db.add(delivery)
            created += 1

        _transition_message(
            message,
            "sending",
            db=db,
            actor_type=actor_type,
            actor_id=actor_id,
        )
        for d in db.scalars(
            select(NotificationDelivery).where(
                NotificationDelivery.message_id == message.id,
                NotificationDelivery.delivery_status == "queued",
            )
        ).all():
            d.delivery_status = "sent"
            d.sent_at = stamp
            d.updated_at = stamp
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
            action="create_overdue_reminders",
            target_table="notification_messages",
            target_id=message.message_code,
            detail={"created": created, "skipped": skipped},
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


def create_reservation_ready_reminders(
    db: Session,
    *,
    actor_type: str = "system",
    actor_id: str = "system",
    commit: bool = True,
) -> dict:
    """预约到书提醒 —— 幂等键: reservation_ready:{reader_id}:{reservation_id}"""
    try:
        rows = db.scalars(
            select(Reservation).where(
                Reservation.status.in_(ACTIVE_RESERVATION_STATUSES),
                Reservation.fulfilled_copy_id != None,
            )
        ).all()

        if not rows:
            return {"message_code": "", "created_count": 0, "skipped_count": 0}

        message = create_message(
            db,
            title="预约到书通知",
            content="你预约的图书已到馆，请在保留期内办理借阅。",
            notification_type="reservation",
            source_type="system",
            lifecycle_status="queued",
            created_by_type="system",
            created_by_code="system",
            actor_type=actor_type,
            actor_id=actor_id,
            commit=False,
        )

        created = 0
        skipped = 0
        stamp = now()
        for row in rows:
            reader = db.get(ReaderAccount, row.reader_id)
            if not reader:
                continue
            ikey = _make_idempotency_key(
                "reservation_ready",
                str(reader.id),
                str(row.id),
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
                recipient_type="reader",
                recipient_id=reader.id,
                channel="in_app",
                delivery_status="queued",
                read_status="unread",
                idempotency_key=ikey,
                created_at=stamp,
                updated_at=stamp,
            )
            db.add(delivery)
            created += 1

        _transition_message(
            message,
            "sending",
            db=db,
            actor_type=actor_type,
            actor_id=actor_id,
        )
        for d in db.scalars(
            select(NotificationDelivery).where(
                NotificationDelivery.message_id == message.id,
                NotificationDelivery.delivery_status == "queued",
            )
        ).all():
            d.delivery_status = "sent"
            d.sent_at = stamp
            d.updated_at = stamp
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
            action="create_reservation_ready_reminders",
            target_table="notification_messages",
            target_id=message.message_code,
            detail={"created": created, "skipped": skipped},
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


def create_task_notifications(
    db: Session,
    *,
    actor_type: str = "system",
    actor_id: str = "system",
    commit: bool = True,
) -> dict:
    """任务提醒 —— 幂等键: task:{admin_id}:{task_code}:{task_status}"""
    try:
        rows = db.scalars(
            select(WorkTask)
            .where(WorkTask.status.in_(ACTIVE_TASK_STATUSES))
            .order_by(WorkTask.priority.desc(), WorkTask.id.desc())
            .limit(200)
        ).all()

        if not rows:
            return {"message_code": "", "created_count": 0, "skipped_count": 0}

        message = create_message(
            db,
            title="待处理任务提醒",
            content="当前有待处理任务，请进入任务中心核查。",
            notification_type="task",
            source_type="system",
            lifecycle_status="queued",
            created_by_type="system",
            created_by_code="system",
            actor_type=actor_type,
            actor_id=actor_id,
            commit=False,
        )

        created = 0
        skipped = 0
        stamp = now()
        active_admin_ids = _active_admin_ids(db)

        for task in rows:
            target_admins = []
            if task.claimed_by_admin_id:
                target_admins = [task.claimed_by_admin_id]
            else:
                target_admins = active_admin_ids

            for admin_id in target_admins:
                ikey = _make_idempotency_key(
                    "task",
                    str(admin_id),
                    str(task.task_code),
                    str(task.status),
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
                    recipient_type="admin",
                    recipient_id=admin_id,
                    channel="in_app",
                    delivery_status="queued",
                    read_status="unread",
                    idempotency_key=ikey,
                    created_at=stamp,
                    updated_at=stamp,
                )
                db.add(delivery)
                created += 1

        _transition_message(
            message,
            "sending",
            db=db,
            actor_type=actor_type,
            actor_id=actor_id,
        )
        for d in db.scalars(
            select(NotificationDelivery).where(
                NotificationDelivery.message_id == message.id,
                NotificationDelivery.delivery_status == "queued",
            )
        ).all():
            d.delivery_status = "sent"
            d.sent_at = stamp
            d.updated_at = stamp
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
            action="create_task_notifications",
            target_table="notification_messages",
            target_id=message.message_code,
            detail={"created": created, "skipped": skipped},
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
