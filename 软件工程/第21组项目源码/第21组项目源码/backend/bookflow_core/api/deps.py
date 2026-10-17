from __future__ import annotations

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from bookflow_core.core.database import get_db
from bookflow_core.core.exceptions import BookFlowError
from bookflow_core.models import AdminUser, ReaderAccount
from bookflow_core.services.auth_service import get_admin_from_token
from bookflow_core.services.permission_service import ensure_permission, ensure_super_admin
from bookflow_core.services.reader_auth_service import get_reader_from_token


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise BookFlowError("Invalid authentication token.", code="AUTH_INVALID_TOKEN")
    return token


def get_current_admin(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> AdminUser:
    token = _extract_bearer(authorization)
    if not token:
        raise BookFlowError("Invalid authentication token.", code="AUTH_INVALID_TOKEN")
    return get_admin_from_token(db, token)


def get_optional_admin(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> AdminUser | None:
    token = _extract_bearer(authorization)
    if not token:
        return None
    return get_admin_from_token(db, token)


def get_current_reader(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> ReaderAccount:
    token = _extract_bearer(authorization)
    if not token:
        raise BookFlowError("Reader authentication is required.", code="READER_AUTH_REQUIRED")
    return get_reader_from_token(db, token)


def get_optional_reader(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> ReaderAccount | None:
    token = _extract_bearer(authorization)
    if not token:
        return None
    return get_reader_from_token(db, token)


def require_reader(current: ReaderAccount = Depends(get_current_reader)) -> ReaderAccount:
    return current


def require_reader_self(reader_id: int, current: ReaderAccount = Depends(get_current_reader)) -> ReaderAccount:
    if current.id != reader_id:
        raise BookFlowError("Readers can only access their own data.", code="READER_FORBIDDEN")
    return current


def require_super_admin(current: AdminUser = Depends(get_current_admin)) -> AdminUser:
    ensure_super_admin(current)
    return current


def require_permission(permission: str):
    def dependency(current: AdminUser = Depends(get_current_admin)) -> AdminUser:
        ensure_permission(current, permission)
        return current

    return dependency
