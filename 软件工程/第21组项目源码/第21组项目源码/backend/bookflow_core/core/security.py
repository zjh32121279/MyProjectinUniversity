from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone

from bookflow_core.core.config import settings
from bookflow_core.core.exceptions import BookFlowError

TOKEN_TTL_MINUTES = 1440  # 24 hours — admin sessions last a full workday
PASSWORD_ITERATIONS = 180_000


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def _secret_key() -> bytes:
    if settings.secret_key:
        return settings.secret_key.encode("utf-8")
    import warnings
    warnings.warn("BOOKFLOW_SECRET_KEY is not set. Using app_name as fallback — insecure for production.", RuntimeWarning)
    return settings.app_name.encode("utf-8")


def hash_password(password: str, *, salt: str | None = None) -> str:
    if not password:
        raise BookFlowError("Password cannot be empty.", code="VALIDATION_ERROR")
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash:
        return False
    try:
        algorithm, iterations, salt, expected = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), int(iterations)).hex()
        return hmac.compare_digest(digest, expected)
    except ValueError:
        return False


def create_access_token(
    subject_id: int,
    *,
    role: str,
    subject_type: str = "admin",
    admin_code: str | None = None,
    reader_code: str | None = None,
    permissions: list[str] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    exp = now + (expires_delta or timedelta(minutes=TOKEN_TTL_MINUTES))
    payload = {
        "sub": str(subject_id),
        "subject_type": subject_type,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    if subject_type == "admin":
        payload["admin_id"] = subject_id
        if admin_code:
            payload["admin_code"] = admin_code
    elif subject_type == "reader":
        payload["reader_id"] = subject_id
        if reader_code:
            payload["reader_code"] = reader_code
    if permissions is not None:
        payload["permissions"] = permissions
    body = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _b64url(hmac.new(_secret_key(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def decode_access_token(token: str) -> dict:
    if not token or "." not in token:
        raise BookFlowError("Invalid authentication token.", code="AUTH_INVALID_TOKEN")
    try:
        body, signature = token.split(".", 1)
        expected = _b64url(hmac.new(_secret_key(), body.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise BookFlowError("Invalid authentication token.", code="AUTH_INVALID_TOKEN")
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
    except BookFlowError:
        raise
    except Exception as exc:
        raise BookFlowError("Invalid authentication token.", code="AUTH_INVALID_TOKEN") from exc
    exp = int(payload.get("exp", 0))
    if exp < int(datetime.now(timezone.utc).timestamp()):
        raise BookFlowError("Authentication token expired.", code="AUTH_TOKEN_EXPIRED")
    return payload
