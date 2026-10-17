from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from bookflow_core.api.deps import require_permission
from bookflow_core.core.database import get_db
from bookflow_core.core.exceptions import BusinessRuleError, NotFoundError
from bookflow_core.models import AdminUser, ReaderAccount
from bookflow_core.schemas import CreateMessageWithDeliveriesRequest
from bookflow_core.services.notification_service import (
    cancel_message,
    create_deliveries,
    create_message,
    list_messages_for_admin,
    message_stats,
    send_message,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _recipient_option(kind: str, row: ReaderAccount | AdminUser) -> dict:
    if kind == "reader":
        return {
            "id": row.id,
            "type": "reader",
            "code": row.reader_code,
            "name": row.name,
            "description": f"{row.reader_type_code or '读者'} / 信用分 {row.credit_score or '-'}",
            "avatar_url": row.avatar_url,
            "status": row.status,
        }
    return {
        "id": row.id,
        "type": "admin",
        "code": row.admin_code,
        "name": row.name,
        "description": "超级管理员" if row.is_super_admin else "普通管理员",
        "status": row.status,
    }


def _reader_id(db: Session, value) -> int:
    text = str(value or "").strip()
    if not text:
        raise BusinessRuleError("通知接收读者不能为空。", details={"recipient_type": "reader"})
    row = db.get(ReaderAccount, int(text)) if text.isdigit() else None
    if row is None:
        row = db.scalar(select(ReaderAccount).where(ReaderAccount.reader_code == text))
    if row is None:
        raise NotFoundError("通知接收读者不存在。", details={"recipient_type": "reader", "recipient_id": text})
    return int(row.id)


def _admin_id(db: Session, value) -> int:
    text = str(value or "").strip()
    if not text:
        raise BusinessRuleError("通知接收管理员不能为空。", details={"recipient_type": "admin"})
    row = db.get(AdminUser, int(text)) if text.isdigit() else None
    if row is None:
        row = db.scalar(select(AdminUser).where(AdminUser.admin_code == text))
    if row is None:
        raise NotFoundError("通知接收管理员不存在。", details={"recipient_type": "admin", "recipient_id": text})
    return int(row.id)


def _delivery_recipients(db: Session, recipients) -> list[dict]:
    resolved: list[dict] = []
    for item in recipients:
        recipient_type = str(item.recipient_type or "").strip().lower()
        recipient_id = item.recipient_id
        if recipient_type in {"all", "all_readers"}:
            resolved.extend(
                {"recipient_type": "reader", "recipient_id": int(reader_id)}
                for reader_id in db.scalars(select(ReaderAccount.id).where(ReaderAccount.status == "active").order_by(ReaderAccount.id)).all()
                if reader_id
            )
        elif recipient_type in {"all_admins"}:
            resolved.extend(
                {"recipient_type": "admin", "recipient_id": int(admin_id)}
                for admin_id in db.scalars(select(AdminUser.id).where(AdminUser.status == "active").order_by(AdminUser.id)).all()
                if admin_id
            )
        elif recipient_type == "reader":
            resolved.append({"recipient_type": "reader", "recipient_id": _reader_id(db, recipient_id)})
        elif recipient_type == "admin":
            resolved.append({"recipient_type": "admin", "recipient_id": _admin_id(db, recipient_id)})
        else:
            raise BusinessRuleError("通知接收类型无效。", details={"recipient_type": recipient_type})

    unique: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for item in resolved:
        key = (str(item["recipient_type"]), int(item["recipient_id"]))
        if key in seen:
            continue
        seen.add(key)
        unique.append({"recipient_type": key[0], "recipient_id": key[1]})
    if not unique:
        raise BusinessRuleError("通知没有可投递接收人。", details={"recipient_count": 0})
    return unique


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@router.get("")
def list_messages(
    notification_type: str | None = None,
    lifecycle_status: str | None = None,
    keyword: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
    current_admin=Depends(require_permission("notifications:read")),
):
    result = list_messages_for_admin(
        db,
        notification_type=notification_type,
        lifecycle_status=lifecycle_status,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )
    return {"success": True, "data": {**result, "stats": message_stats(db)}, "message": None}


@router.get("/stats")
def get_stats(db: Session = Depends(get_db), current_admin=Depends(require_permission("notifications:read"))):
    return {"success": True, "data": message_stats(db), "message": None}


@router.post("/batch")
def create_msg_with_deliveries(
    req: CreateMessageWithDeliveriesRequest,
    db: Session = Depends(get_db),
    current_admin=Depends(require_permission("notifications:write")),
):
    message = create_message(
        db,
        title=req.title,
        content=req.content,
        notification_type=req.notification_type,
        source_type=req.source_type,
        source_task_code=req.source_task_code,
        related_entity_type=req.related_entity_type,
        related_entity_id=req.related_entity_id,
        target_scope_json=req.target_scope_json,
        lifecycle_status=req.lifecycle_status,
        scheduled_at=_parse_datetime(req.scheduled_at),
        created_by_type="admin",
        created_by_code=current_admin.admin_code,
        idempotency_key=req.idempotency_key,
        actor_type="admin",
        actor_id=current_admin.admin_code,
        commit=False,
    )

    result = create_deliveries(
        db,
        message_id=message.id,
        recipients=_delivery_recipients(db, req.recipients),
        actor_type="admin",
        actor_id=current_admin.admin_code,
        commit=False,
    )

    if req.lifecycle_status == "queued" and result["created_count"] > 0:
        send_result = send_message(
            db,
            message.id,
            actor_type="admin",
            actor_id=current_admin.admin_code,
            commit=False,
        )
        result["sent_count"] = send_result["sent_count"]

    db.commit()
    return {
        "success": True,
        "data": {
            "message_code": result["message_code"],
            "created_count": result["created_count"],
            "skipped_count": result["skipped_count"],
            "sent_count": result.get("sent_count", 0),
        },
        "message": None,
    }


@router.get("/recipient-options")
def recipient_options(
    recipient_type: str = "reader",
    keyword: str | None = None,
    limit: int = Query(30, ge=1, le=100),
    offset: int = 0,
    db: Session = Depends(get_db),
    current_admin=Depends(require_permission("notifications:write")),
):
    kind = str(recipient_type or "").strip().lower()
    if kind not in {"reader", "admin"}:
        raise BusinessRuleError("通知接收类型无效。", details={"recipient_type": recipient_type})

    text = str(keyword or "").strip()
    if kind == "reader":
        stmt = select(ReaderAccount)
        if text:
            stmt = stmt.where(
                or_(
                    ReaderAccount.name.contains(text),
                    ReaderAccount.reader_code.contains(text),
                    ReaderAccount.phone_masked.contains(text),
                    ReaderAccount.email.contains(text),
                )
            )
        total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
        rows = db.scalars(stmt.order_by(ReaderAccount.id).offset(offset).limit(limit)).all()
        items = [_recipient_option("reader", row) for row in rows]
    else:
        stmt = select(AdminUser)
        if text:
            stmt = stmt.where(
                or_(
                    AdminUser.name.contains(text),
                    AdminUser.admin_code.contains(text),
                    AdminUser.email.contains(text),
                )
            )
        total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
        rows = db.scalars(stmt.order_by(AdminUser.is_super_admin.desc(), AdminUser.id).offset(offset).limit(limit)).all()
        items = [_recipient_option("admin", row) for row in rows]

    return {"success": True, "data": {"items": items, "total": total, "limit": limit, "offset": offset}, "message": None}


@router.post("/{message_id}/send")
def send_msg(message_id: int, db: Session = Depends(get_db), current_admin=Depends(require_permission("notifications:write"))):
    result = send_message(db, message_id, actor_type="admin", actor_id=current_admin.admin_code)
    return {"success": True, "data": result, "message": None}


@router.post("/{message_id}/cancel")
def cancel_msg(message_id: int, db: Session = Depends(get_db), current_admin=Depends(require_permission("notifications:write"))):
    result = cancel_message(db, message_id, actor_type="admin", actor_id=current_admin.admin_code)
    return {"success": True, "data": result, "message": None}
