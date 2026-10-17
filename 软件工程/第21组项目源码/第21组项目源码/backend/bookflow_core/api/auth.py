from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from bookflow_core.api.deps import get_current_admin, get_db, get_optional_admin
from bookflow_core.core.security import create_access_token, decode_access_token
from bookflow_core.core.exceptions import BookFlowError
from bookflow_core.schemas.auth import LoginRequest
from bookflow_core.services.auth_service import admin_role, authenticate_admin, logout_admin
from bookflow_core.services.permission_service import admin_to_public
from bookflow_core.models import AdminUser

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    data = authenticate_admin(
        db,
        account=req.account,
        password=req.password,
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return {"success": True, "data": data, "message": None}


@router.get("/me")
def me(current_admin: AdminUser = Depends(get_current_admin)):
    return {"success": True, "data": admin_to_public(current_admin), "message": None}


@router.post("/refresh")
def refresh_token(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Issue a fresh token using the current (possibly expired) token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise BookFlowError("Missing authentication token.", code="AUTH_INVALID_TOKEN")
    token = authorization.removeprefix("Bearer ").strip()
    # Decode but allow expired tokens within a grace window
    try:
        payload = decode_access_token(token)
    except BookFlowError as exc:
        if exc.code != "AUTH_TOKEN_EXPIRED":
            raise
        # Allow refresh up to 24h after expiry
        payload = decode_access_token(token, allow_expired=True) if hasattr(decode_access_token, "allow_expired") else _decode_expired(token)

    admin_id = int(payload.get("sub", 0))
    admin_code = payload.get("admin_code")
    role = payload.get("role", "admin")
    if not admin_id:
        raise BookFlowError("Invalid token payload.", code="AUTH_INVALID_TOKEN")

    new_token = create_access_token(
        admin_id,
        role=role,
        subject_type="admin",
        admin_code=admin_code,
        expires_delta=timedelta(minutes=1440),
    )
    # Return admin info from DB so frontend can update
    admin: AdminUser | None = db.get(AdminUser, admin_id) if admin_id else None
    admin_data = admin_to_public(admin) if admin else None
    return {"success": True, "data": {"access_token": new_token, "token_type": "bearer", "admin": admin_data}, "message": None}


def _decode_expired(token: str) -> dict:
    """Decode token payload without checking expiry."""
    import json as _json
    from bookflow_core.core.security import _b64url_decode
    body, _sig = token.split(".", 1)
    return _json.loads(_b64url_decode(body).decode("utf-8"))


@router.post("/logout")
def logout(current_admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    return {"success": True, "data": logout_admin(db, current_admin), "message": None}
