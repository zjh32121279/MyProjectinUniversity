from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from bookflow_core.models import AdminUser, SystemSetting


def time_code(prefix: str) -> str:
    return f"{prefix}-{int(datetime.now(timezone.utc).timestamp() * 1000000)}"


def message_code() -> str:
    return time_code("MSG")


def delivery_code() -> str:
    return time_code("DLV")


def active_admin_ids(db: Session) -> list[int]:
    return [
        admin_id
        for admin_id in db.scalars(
            select(AdminUser.id)
            .where(AdminUser.status == "active")
            .order_by(AdminUser.id)
        ).all()
        if admin_id
    ]


def int_rule(db: Session, key: str, default: int) -> int:
    row = db.scalar(
        select(SystemSetting).where(
            SystemSetting.setting_key == key, SystemSetting.is_active == True
        )
    )
    return int(row.setting_value) if row else default


def make_idempotency_key(*parts: str) -> str:
    return ":".join(parts)
