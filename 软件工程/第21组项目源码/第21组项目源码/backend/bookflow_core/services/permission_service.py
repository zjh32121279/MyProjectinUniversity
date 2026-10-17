from __future__ import annotations

from bookflow_core.core.exceptions import BookFlowError
from bookflow_core.models import AdminUser

ROLE_PERMISSIONS = {
    "admin": [
        "auth:me",
        "locations:read",
        "catalog:read",
        "catalog:write",
        "readers:read",
        "readers:write",
        "circulation:write",
        "reservations:write",
        "notifications:read",
        "notifications:write",
        "tasks:read",
        "tasks:write",
        "risks:write",
        "rules:read",
        "dashboard:read",
        "analytics:read",
        "analytics:write",
        "library:write",
        "settings:write",
        "ai:chat",
    ],
    "super_admin": [
        "auth:me",
        "locations:read",
        "catalog:read",
        "catalog:write",
        "readers:read",
        "readers:write",
        "circulation:write",
        "reservations:write",
        "notifications:read",
        "notifications:write",
        "tasks:read",
        "tasks:write",
        "risks:write",
        "rules:read",
        "dashboard:read",
        "analytics:read",
        "analytics:write",
        "library:write",
        "settings:write",
        "ai:chat",
        "admins:manage",
        "rules:high_risk_write",
        "approvals:approve_l4",
        "audit:read",
    ],
}


def admin_role(admin: AdminUser) -> str:
    return "super_admin" if bool(admin.is_super_admin) else "admin"


def admin_is_active(admin: AdminUser) -> bool:
    return admin.status == "active"


def permissions_for_role(role: str) -> list[str]:
    return list(ROLE_PERMISSIONS.get(role, []))


def admin_to_public(admin: AdminUser) -> dict:
    role = admin_role(admin)
    return {
        "id": admin.id,
        "admin_code": admin.admin_code,
        "name": admin.name,
        "email": admin.email,
        "is_super_admin": bool(admin.is_super_admin),
        "status": admin.status,
        "permissions": permissions_for_role(role),
    }


def ensure_permission(admin: AdminUser, permission: str) -> None:
    if permission not in permissions_for_role(admin_role(admin)):
        raise BookFlowError("Permission denied.", code="AUTH_FORBIDDEN", details={"permission": permission})


def ensure_super_admin(admin: AdminUser) -> None:
    if not admin.is_super_admin:
        raise BookFlowError("Super administrator permission required.", code="AUTH_FORBIDDEN")
