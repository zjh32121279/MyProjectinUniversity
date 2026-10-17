from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from bookflow_core.core.exceptions import BookFlowError
from bookflow_core.core.security import create_access_token, decode_access_token, verify_password
from bookflow_core.models import AdminUser, AdminLoginEvent
from bookflow_core.services.common import write_audit, utc_text
from bookflow_core.services.permission_service import admin_is_active, admin_role, admin_to_public


def _record_login_event(
    db: Session,
    *,
    admin: AdminUser | None,
    event_type: str,
    account: str,
    ip_address: str = "",
    user_agent: str = "",
) -> None:
    if admin is not None:
        db.add(AdminLoginEvent(admin_id=admin.id, event_type=event_type, ip_address=ip_address, user_agent=user_agent, created_at=utc_text()))
    write_audit(
        db,
        actor_type="admin" if admin else "guest",
        actor_id=admin.admin_code if admin else account,
        action=f"admin_{event_type}",
        target_table="admin_users",
        target_id=admin.admin_code if admin else account,
        result="success" if event_type == "login_success" else "failed",
        detail={"account": account, "ip_address": ip_address},
    )


def _recent_failed_count(db: Session, admin_id: int | None, account: str) -> int:
    from datetime import datetime, timedelta, timezone
    window = datetime.now(timezone.utc) - timedelta(minutes=15)
    stmt = select(func.count(AdminLoginEvent.id)).where(AdminLoginEvent.event_type == "login_failed", AdminLoginEvent.created_at >= window)
    if admin_id is not None:
        stmt = stmt.where(AdminLoginEvent.admin_id == admin_id)
    return int(db.scalar(stmt) or 0)


def authenticate_admin(
    db: Session,
    *,
    account: str,
    password: str,
    ip_address: str = "",
    user_agent: str = "",
    commit: bool = True,
) -> dict:
    try:
        normalized = account.strip()
        admin = db.scalar(select(AdminUser).where(or_(AdminUser.email == normalized, AdminUser.admin_code == normalized)))
        failed_count = _recent_failed_count(db, admin.id if admin else None, normalized)
        if failed_count >= 10:
            import time
            time.sleep(min(failed_count * 0.5, 5))
            raise BookFlowError("Account temporarily locked due to too many failed attempts.", code="AUTH_INVALID_CREDENTIALS")
        if failed_count >= 3:
            import time
            time.sleep(min(failed_count * 0.3, 3))
        if not admin:
            verify_password(password, "pbkdf2_sha256$180000$0000000000000000$0000000000000000000000000000000000000000000000000000000000000000")
            _record_login_event(db, admin=None, event_type="login_failed", account=normalized, ip_address=ip_address, user_agent=user_agent)
            if commit:
                db.commit()
            raise BookFlowError("Invalid account or password.", code="AUTH_INVALID_CREDENTIALS")
        if not verify_password(password, admin.password_hash):
            _record_login_event(db, admin=admin, event_type="login_failed", account=normalized, ip_address=ip_address, user_agent=user_agent)
            if commit:
                db.commit()
            raise BookFlowError("Invalid account or password.", code="AUTH_INVALID_CREDENTIALS")
        if not admin_is_active(admin):
            _record_login_event(db, admin=admin, event_type="login_failed", account=normalized, ip_address=ip_address, user_agent=user_agent)
            if commit:
                db.commit()
            raise BookFlowError("Administrator account is inactive.", code="ADMIN_INACTIVE")
        _record_login_event(db, admin=admin, event_type="login_success", account=normalized, ip_address=ip_address, user_agent=user_agent)
        token = create_access_token(admin.id, role=admin_role(admin), subject_type="admin", admin_code=admin.admin_code)
        if commit:
            db.commit()
        return {"access_token": token, "token_type": "bearer", "admin": admin_to_public(admin)}
    except BookFlowError:
        raise
    except Exception:
        if commit:
            db.rollback()
        raise


def get_admin_from_token(db: Session, token: str) -> AdminUser:
    payload = decode_access_token(token)
    if payload.get("subject_type", "admin") != "admin":
        raise BookFlowError("Reader tokens cannot access administrator APIs.", code="AUTH_FORBIDDEN")
    admin_id = payload.get("admin_id") or payload.get("sub")
    admin = db.get(AdminUser, int(admin_id)) if admin_id else None
    if not admin:
        raise BookFlowError("Invalid authentication token.", code="AUTH_INVALID_TOKEN")
    if not admin_is_active(admin):
        raise BookFlowError("Administrator account is inactive.", code="ADMIN_INACTIVE")
    last_logout = db.scalar(
        select(AdminLoginEvent.created_at)
        .where(AdminLoginEvent.admin_id == admin.id, AdminLoginEvent.event_type == "logout")
        .order_by(AdminLoginEvent.id.desc())
    )
    if last_logout and last_logout is not None:
        from datetime import datetime, timezone
        from bookflow_core.core.time import CST
        iat_dt = datetime.fromtimestamp(int(payload["iat"]), tz=timezone.utc)
        logout_dt = last_logout.replace(tzinfo=CST) if last_logout.tzinfo is None else last_logout
        if iat_dt < logout_dt:
            raise BookFlowError("Authentication token has been revoked.", code="AUTH_TOKEN_EXPIRED")
    return admin


def logout_admin(db: Session, admin: AdminUser | None, *, commit: bool = True) -> dict:
    try:
        if admin is not None:
            db.add(AdminLoginEvent(admin_id=admin.id, event_type="logout", created_at=utc_text()))
            write_audit(db, actor_type="admin", actor_id=admin.admin_code, action="admin_logout", target_table="admin_users", target_id=admin.admin_code)
        if commit:
            db.commit()
        return {"logged_out": True}
    except Exception:
        if commit:
            db.rollback()
        raise
