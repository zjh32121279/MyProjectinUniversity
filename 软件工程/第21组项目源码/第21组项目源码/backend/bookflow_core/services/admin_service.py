from __future__ import annotations

import re

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from bookflow_core.core.security import hash_password
from bookflow_core.core.exceptions import BusinessRuleError, NotFoundError, ValidationError
from bookflow_core.core.time import now
from bookflow_core.models import AdminLoginEvent, AdminRole, AdminUser, AdminUserRole, AuditEvent
from bookflow_core.services.common import write_audit, utc_text
from bookflow_core.services.permission_service import admin_is_active, admin_role, permissions_for_role

VALID_ADMIN_ROLES = {"super_admin", "admin"}
VALID_ADMIN_EVENTS = {"login_success", "login_failed", "password_changed", "disabled", "enabled", "permission_check", "logout"}
ADMIN_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,31}$")


def admin_to_dict(admin: AdminUser) -> dict:
    role = admin_role(admin)
    return {
        "id": admin.id,
        "admin_code": admin.admin_code,
        "name": admin.name,
        "email": admin.email,
        "is_super_admin": bool(admin.is_super_admin),
        "status": admin.status,
        "created_at": admin.created_at,
        "updated_at": admin.updated_at,
        "permissions": permissions_for_role(role),
        "permission_template": "超级管理员模板" if role == "super_admin" else "普通管理员模板",
        "managed_scope": "全馆" if role == "super_admin" else "馆内运营",
    }


def login_event_to_dict(event: AdminLoginEvent) -> dict:
    admin_code = ""
    admin_name = ""
    admin = getattr(event, "_bookflow_admin", None)
    if admin:
        admin_code = admin.admin_code
        admin_name = admin.name
    return {
        "id": event.id,
        "admin_code": admin_code,
        "admin_name": admin_name,
        "event_type": event.event_type,
        "ip_address": event.ip_address,
        "user_agent": event.user_agent,
        "created_at": event.created_at,
    }


def get_admin(db: Session, admin_code: str) -> AdminUser:
    admin = db.scalar(select(AdminUser).where(AdminUser.admin_code == admin_code))
    if not admin:
        raise NotFoundError("AdminUser not found.", details={"admin_code": admin_code})
    return admin


def list_admins(
    db: Session,
    *,
    is_super_admin: bool | None = None,
    status: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    if status and status not in {"active", "disabled"}:
        raise ValidationError("Invalid admin status.", details={"status": status})
    stmt = select(AdminUser)
    if is_super_admin is not None:
        stmt = stmt.where(AdminUser.is_super_admin == is_super_admin)
    if status:
        stmt = stmt.where(AdminUser.status == status)
    if keyword:
        stmt = stmt.where(AdminUser.name.contains(keyword) | AdminUser.admin_code.contains(keyword) | AdminUser.email.contains(keyword))
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    items = db.scalars(stmt.order_by(AdminUser.is_super_admin.desc(), AdminUser.id).offset(offset).limit(limit)).all()

    admin_ids = [row.id for row in items]
    last_login_by_admin: dict[int, AdminLoginEvent] = {}
    failed_count_by_admin: dict[int, int] = {}
    if admin_ids:
        login_rows = db.scalars(
            select(AdminLoginEvent)
            .where(AdminLoginEvent.admin_id.in_(admin_ids), AdminLoginEvent.event_type == "login_success")
            .order_by(AdminLoginEvent.id.desc())
        ).all()
        for event in login_rows:
            if event.admin_id is not None and event.admin_id not in last_login_by_admin:
                last_login_by_admin[event.admin_id] = event
        for admin_id, count in db.execute(
            select(AdminLoginEvent.admin_id, func.count(AdminLoginEvent.id))
            .where(AdminLoginEvent.admin_id.in_(admin_ids), AdminLoginEvent.event_type == "login_failed")
            .group_by(AdminLoginEvent.admin_id)
        ).all():
            if admin_id is not None:
                failed_count_by_admin[int(admin_id)] = int(count)

    enriched = []
    for row in items:
        item = admin_to_dict(row)
        last_login = last_login_by_admin.get(row.id)
        item.update(
            {
                "last_login_at": last_login.created_at if last_login else "",
                "last_login_ip": last_login.ip_address if last_login else "",
                "failed_login_count": failed_count_by_admin.get(row.id, 0),
                "risk_level": "medium" if failed_count_by_admin.get(row.id, 0) else "low",
            }
        )
        enriched.append(item)
    return {"items": enriched, "total": total, "limit": limit, "offset": offset}


def _validate_admin_password(password: str) -> None:
    if len(password) < 12:
        raise ValidationError("Admin password must contain at least 12 characters.")
    checks = [
        any(ch.islower() for ch in password),
        any(ch.isupper() for ch in password),
        any(ch.isdigit() for ch in password),
        any(not ch.isalnum() for ch in password),
    ]
    if not all(checks):
        raise ValidationError("Admin password must include uppercase, lowercase, number, and symbol.")


def _ensure_role_metadata(db: Session, *, role_code: str) -> AdminRole:
    role = db.scalar(select(AdminRole).where(AdminRole.role_code == role_code))
    if role is None:
        stamp = now()
        role = AdminRole(
            role_code=role_code,
            name="Super Administrator" if role_code == "super_admin" else "Administrator",
            description="System role",
            is_system=True,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(role)
        db.flush()
    return role


def create_admin(
    db: Session,
    *,
    admin_code: str,
    name: str,
    email: str = "",
    password: str,
    is_super_admin: bool = False,
    status: str = "active",
    actor_id: str = "super_admin",
    actor_admin_id: int | None = None,
    commit: bool = True,
) -> AdminUser:
    admin_code = (admin_code or "").strip()
    name = (name or "").strip()
    email = (email or "").strip()
    status = (status or "active").strip()
    role_code = "super_admin" if is_super_admin else "admin"
    if not ADMIN_CODE_PATTERN.match(admin_code):
        raise ValidationError("Admin code must be 3-32 letters, numbers, dots, underscores, or hyphens.", details={"admin_code": admin_code})
    if not name:
        raise ValidationError("Admin name is required.")
    if email and ("@" not in email or email.startswith("@") or email.endswith("@")):
        raise ValidationError("Invalid admin email.", details={"email": email})
    if status not in {"active", "disabled"}:
        raise ValidationError("Invalid admin status.", details={"status": status})
    _validate_admin_password(password)
    duplicate_stmt = select(AdminUser).where(AdminUser.admin_code == admin_code)
    if email:
        duplicate_stmt = select(AdminUser).where(or_(AdminUser.admin_code == admin_code, AdminUser.email == email))
    duplicate = db.scalar(duplicate_stmt)
    if duplicate is not None:
        field = "email" if email and duplicate.email == email else "admin_code"
        raise ValidationError("Admin account already exists.", details={field: email if field == "email" else admin_code})
    try:
        stamp = now()
        role = _ensure_role_metadata(db, role_code=role_code)
        admin = AdminUser(
            admin_code=admin_code,
            name=name,
            email=email or None,
            password_hash=hash_password(password),
            status=status,
            is_super_admin=is_super_admin,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(admin)
        db.flush()
        db.add(AdminUserRole(admin_id=admin.id, role_id=role.id, assigned_by_admin_id=actor_admin_id, created_at=stamp))
        db.add(AdminLoginEvent(admin_id=admin.id, admin_code=admin.admin_code, event_type="enabled" if status == "active" else "disabled", ip_address="", user_agent="system", result="success", created_at=stamp))
        write_audit(
            db,
            actor_type="super_admin",
            actor_id=actor_id,
            action="create_admin",
            target_table="admin_users",
            target_id=admin.admin_code,
            detail={"is_super_admin": is_super_admin, "status": status},
        )
        if commit:
            db.commit()
            db.refresh(admin)
        return admin
    except Exception:
        if commit:
            db.rollback()
        raise


def record_admin_event(
    db: Session,
    *,
    admin_code: str,
    event_type: str,
    ip_address: str = "",
    user_agent: str = "",
    actor_id: str = "system",
    commit: bool = True,
) -> AdminLoginEvent:
    if event_type not in VALID_ADMIN_EVENTS:
        raise ValidationError("Invalid admin event type.", details={"event_type": event_type})
    try:
        admin = get_admin(db, admin_code)
        event = AdminLoginEvent(admin_id=admin.id, event_type=event_type, ip_address=ip_address, user_agent=user_agent, created_at=utc_text())
        db.add(event)
        write_audit(db, actor_type="system", actor_id=actor_id, action=f"admin_{event_type}", target_table="admin_login_events", target_id=admin.admin_code, detail={"ip_address": ip_address})
        if commit:
            db.commit()
            db.refresh(event)
        return event
    except Exception:
        if commit:
            db.rollback()
        raise


def update_admin(
    db: Session,
    *,
    admin_code: str,
    name: str | None = None,
    email: str | None = None,
    is_super_admin: bool | None = None,
    status: str | None = None,
    actor_id: str = "super_admin",
    commit: bool = True,
) -> AdminUser:
    try:
        admin = get_admin(db, admin_code)
        changes = {}
        if name is not None:
            name = (name or "").strip()
            if not name:
                raise ValidationError("Admin name is required.")
            if name != admin.name:
                changes["name"] = {"old": admin.name, "new": name}
                admin.name = name
        if email is not None:
            email = (email or "").strip()
            if email and ("@" not in email or email.startswith("@") or email.endswith("@")):
                raise ValidationError("Invalid admin email.", details={"email": email})
            new_email = email or None
            if new_email != admin.email:
                changes["email"] = {"old": admin.email, "new": new_email}
                admin.email = new_email
        if is_super_admin is not None:
            if bool(is_super_admin) != bool(admin.is_super_admin):
                changes["is_super_admin"] = {"old": admin.is_super_admin, "new": is_super_admin}
                admin.is_super_admin = is_super_admin
        if status is not None:
            status = (status or "active").strip()
            if status not in {"active", "disabled"}:
                raise ValidationError("Invalid admin status.", details={"status": status})
            if admin.is_super_admin and status != "active":
                active_supers = int(db.scalar(select(func.count(AdminUser.id)).where(AdminUser.is_super_admin == True, AdminUser.status == "active")) or 0)
                if active_supers <= 1:
                    raise BusinessRuleError("Cannot disable the last active super admin.")
            if status != admin.status:
                changes["status"] = {"old": admin.status, "new": status}
                admin.status = status
        if not changes:
            return admin
        admin.updated_at = utc_text()
        write_audit(db, actor_type="super_admin", actor_id=actor_id, action="update_admin", target_table="admin_users", target_id=admin.admin_code, detail=changes)
        if commit:
            db.commit()
            db.refresh(admin)
        return admin
    except Exception:
        if commit:
            db.rollback()
        raise


def reset_admin_password(db: Session, *, admin_code: str, password: str, actor_id: str = "super_admin", commit: bool = True) -> AdminUser:
    try:
        admin = get_admin(db, admin_code)
        _validate_admin_password(password)
        admin.password_hash = hash_password(password)
        admin.updated_at = utc_text()
        write_audit(db, actor_type="super_admin", actor_id=actor_id, action="reset_admin_password", target_table="admin_users", target_id=admin.admin_code, detail={})
        if commit:
            db.commit()
            db.refresh(admin)
        return admin
    except Exception:
        if commit:
            db.rollback()
        raise


def set_admin_status(db: Session, *, admin_code: str, status: str, actor_id: str = "super_admin", commit: bool = True) -> AdminUser:
    if status not in {"active", "disabled"}:
        raise ValidationError("Invalid admin status.", details={"status": status})
    try:
        admin = get_admin(db, admin_code)
        if admin.is_super_admin and status != "active":
            active_supers = int(db.scalar(select(func.count(AdminUser.id)).where(AdminUser.is_super_admin == True, AdminUser.status == "active")) or 0)
            if active_supers <= 1:
                raise BusinessRuleError("Cannot disable the last active super admin.")
        old = admin.status
        admin.status = status
        db.add(AdminLoginEvent(admin_id=admin.id, event_type="enabled" if status == "active" else "disabled", ip_address="", user_agent="system", created_at=utc_text()))
        write_audit(db, actor_type="super_admin", actor_id=actor_id, action="set_admin_status", target_table="admin_users", target_id=admin.admin_code, detail={"old": old, "new": status})
        if commit:
            db.commit()
            db.refresh(admin)
        return admin
    except Exception:
        if commit:
            db.rollback()
        raise


def list_admin_events(db: Session, *, admin_code: str | None = None, event_type: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    if event_type and event_type not in VALID_ADMIN_EVENTS:
        raise ValidationError("Invalid admin event type.", details={"event_type": event_type})
    stmt = select(AdminLoginEvent)
    admin_lookup: dict[int, AdminUser] = {}
    if admin_code:
        admin = get_admin(db, admin_code)
        stmt = stmt.where(AdminLoginEvent.admin_id == admin.id)
        admin_lookup[admin.id] = admin
    if event_type:
        stmt = stmt.where(AdminLoginEvent.event_type == event_type)
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = db.scalars(stmt.order_by(AdminLoginEvent.id.desc()).offset(offset).limit(limit)).all()
    admin_ids = {row.admin_id for row in rows if row.admin_id not in admin_lookup}
    if admin_ids:
        for admin in db.scalars(select(AdminUser).where(AdminUser.id.in_(admin_ids))).all():
            admin_lookup[admin.id] = admin
    items = []
    for row in rows:
        row._bookflow_admin = admin_lookup.get(row.admin_id)
        items.append(login_event_to_dict(row))
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def admin_security_summary(db: Session) -> dict:
    by_event = {
        event_type: int(db.scalar(select(func.count(AdminLoginEvent.id)).where(AdminLoginEvent.event_type == event_type)) or 0)
        for event_type in sorted(VALID_ADMIN_EVENTS)
    }
    active_admins = int(db.scalar(select(func.count(AdminUser.id)).where(AdminUser.status == "active")) or 0)
    inactive_admins = int(db.scalar(select(func.count(AdminUser.id)).where(AdminUser.status != "active")) or 0)
    super_admins = int(db.scalar(select(func.count(AdminUser.id)).where(AdminUser.is_super_admin == True, AdminUser.status == "active")) or 0)
    recent_failed = db.scalars(select(AdminLoginEvent).where(AdminLoginEvent.event_type == "login_failed").order_by(AdminLoginEvent.id.desc()).limit(5)).all()
    audit_admin_actions = int(db.scalar(select(func.count(AuditEvent.id)).where(AuditEvent.action.like("admin_%"))) or 0)
    return {
        "active_admin_count": active_admins,
        "inactive_admin_count": inactive_admins,
        "active_super_admin_count": super_admins,
        "login_failed_count": by_event["login_failed"],
        "by_event": by_event,
        "recent_failed_logins": [{"id": row.id, "ip_address": row.ip_address, "created_at": row.created_at} for row in recent_failed],
        "admin_audit_action_count": audit_admin_actions,
        "risk_level": "high" if by_event["login_failed"] >= 5 or super_admins == 0 else "normal",
    }
