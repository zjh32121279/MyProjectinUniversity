from __future__ import annotations

import hashlib
import random
import re
from datetime import timedelta

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from bookflow_core.core.exceptions import BookFlowError
from bookflow_core.core.security import create_access_token, decode_access_token, hash_password, verify_password
from bookflow_core.core.time import now
from bookflow_core.models import ReaderAccount, ReaderCredential, ReaderNotificationSetting, ReaderVerificationCode
from bookflow_core.services.reader_service import reader_to_dict


def _reader_public(reader: ReaderAccount) -> dict:
    return {
        "id": reader.id,
        "reader_code": reader.reader_code,
        "name": reader.name,
        "reader_type_code": reader.reader_type_code,
        "reader_type_name": reader.reader_type_name,
        "status": reader.status,
        "phone_masked": reader.phone_masked,
        "email": reader.email,
        "avatar_url": reader.avatar_url,
        "credit_score": reader.credit_score,
    }


def _credential_row(db: Session, account: str):
    account_hash = hashlib.sha256(account.encode("utf-8")).hexdigest()
    return db.execute(
        text(
            """
            SELECT
                c.id AS credential_id,
                c.password_hash AS password_hash,
                c.status AS credential_status,
                r.id AS reader_id,
                r.reader_code AS reader_code,
                r.name AS name,
                r.reader_type_code AS reader_type_code,
                r.reader_type_name AS reader_type_name,
                r.status AS reader_status,
                r.phone_masked AS phone_masked,
                r.email AS email,
                r.credit_score AS credit_score
            FROM reader_credentials c
            JOIN reader_accounts r ON r.id = c.reader_id
            WHERE c.login_name = :account
               OR c.phone_hash = :account_hash
               OR c.email = :account
               OR r.reader_code = :account
            ORDER BY c.id
            LIMIT 1
            """
        ),
        {"account": account, "account_hash": account_hash},
    ).mappings().first()


def authenticate_reader(db: Session, *, account: str, password: str) -> dict:
    normalized = account.strip()
    if not normalized or not password:
        raise BookFlowError("读者账号或密码错误。", code="READER_AUTH_FAILED")
    row = _credential_row(db, normalized)
    if not row:
        verify_password(password, "pbkdf2_sha256$180000$0000000000000000$0000000000000000000000000000000000000000000000000000000000000000")
        raise BookFlowError("读者账号或密码错误。", code="READER_AUTH_FAILED")
    if row["credential_status"] != "active" or not verify_password(password, row["password_hash"]):
        raise BookFlowError("读者账号或密码错误。", code="READER_AUTH_FAILED")
    if row["reader_status"] != "active":
        raise BookFlowError("读者账号当前不可用。", code="READER_FORBIDDEN")
    token = create_access_token(
        int(row["reader_id"]),
        role="reader",
        subject_type="reader",
        reader_code=str(row["reader_code"]),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "reader": {
            "id": row["reader_id"],
            "reader_code": row["reader_code"],
            "name": row["name"],
            "reader_type_code": row["reader_type_code"],
            "reader_type_name": row["reader_type_name"],
            "status": row["reader_status"],
            "phone_masked": row["phone_masked"],
            "email": row["email"],
            "credit_score": row["credit_score"],
        },
    }


def get_reader_from_token(db: Session, token: str) -> ReaderAccount:
    payload = decode_access_token(token)
    if payload.get("subject_type") != "reader":
        raise BookFlowError("Administrator tokens cannot access reader APIs.", code="READER_FORBIDDEN")
    reader_id = payload.get("reader_id") or payload.get("sub")
    reader = db.get(ReaderAccount, int(reader_id)) if reader_id else None
    if not reader:
        raise BookFlowError("Reader authentication is invalid.", code="READER_AUTH_REQUIRED")
    if reader.status != "active":
        raise BookFlowError("Reader account is not active.", code="READER_FORBIDDEN")
    return reader


def logout_reader(db: Session, reader: ReaderAccount | None) -> dict:
    return {"logged_out": True, "reader_id": reader.id if reader else None}


def _normalize_account(account: str | None) -> str:
    return str(account or "").strip().lower()


def _account_hash(account: str | None) -> str:
    return hashlib.sha256(_normalize_account(account).encode("utf-8")).hexdigest()


def _code_hash(code: str | None) -> str:
    return hashlib.sha256(f"bookflow-reader-code:{str(code or '').strip()}".encode("utf-8")).hexdigest()


def _mask_phone(phone: str | None) -> str | None:
    raw = re.sub(r"\D", "", str(phone or ""))
    if not raw:
        return None
    if len(raw) <= 7:
        return raw[:2] + "****"
    return raw[:3] + "****" + raw[-4:]


def _next_reader_code(db: Session) -> str:
    rows = db.scalars(select(ReaderAccount.reader_code).where(ReaderAccount.reader_code.like("RD-%"))).all()
    max_seq = 0
    for code in rows:
        match = re.search(r"(\d+)$", str(code or ""))
        if match:
            max_seq = max(max_seq, int(match.group(1)))
    return f"RD-{max_seq + 1:05d}"


def _validate_password(password: str | None, confirm_password: str | None) -> str:
    if not password or len(password) < 6:
        raise BookFlowError("密码至少需要 6 位。", code="VALIDATION_ERROR")
    if password != confirm_password:
        raise BookFlowError("两次输入的密码不一致。", code="VALIDATION_ERROR")
    return password


def _verify_reader_code(db: Session, *, account: str, code: str | None, purpose: str, extra_accounts: list[str] | None = None) -> ReaderVerificationCode:
    normalized = _normalize_account(account)
    if not normalized or not code:
        raise BookFlowError("验证码不能为空。", code="VALIDATION_ERROR")
    # 构建候选账号列表：主账号 + 额外账号（如同时填了邮箱和手机号）
    candidates = [normalized]
    if extra_accounts:
        for a in extra_accounts:
            n = _normalize_account(a)
            if n and n not in candidates:
                candidates.append(n)
    row = db.scalar(
        select(ReaderVerificationCode)
        .where(
            ReaderVerificationCode.account.in_(candidates),
            ReaderVerificationCode.purpose.in_([purpose, "general"]),
            ReaderVerificationCode.consumed_at.is_(None),
            ReaderVerificationCode.expire_at > now(),
        )
        .order_by(ReaderVerificationCode.id.desc())
    )
    if not row or row.code_hash != _code_hash(code):
        raise BookFlowError("验证码错误或已过期。", code="VALIDATION_ERROR")
    row.consumed_at = now()
    return row


def request_reader_verification_code(db: Session, *, account: str, purpose: str = "general", request_ip: str | None = None, commit: bool = True) -> dict:
    normalized = _normalize_account(account)
    if not normalized:
        raise BookFlowError("账号不能为空。", code="VALIDATION_ERROR")
    purpose = purpose if purpose in {"register", "reset_password", "login", "general"} else "general"
    code = f"{random.randint(0, 999999):06d}"
    row = ReaderVerificationCode(account=normalized, purpose=purpose, code_hash=_code_hash(code), expire_at=now() + timedelta(minutes=10), request_ip=request_ip, created_at=now())
    db.add(row)
    if commit:
        db.commit()

    is_email = "@" in normalized

    # 每次请求直接从 .env 文件读取，彻底绕过 uvicorn/os.environ 缓存
    from bookflow_core.core.config import project_root
    _debug_mode = False
    _env_path = project_root() / ".env"
    if _env_path.exists():
        for _line in _env_path.read_text(encoding="utf-8").splitlines():
            _stripped = _line.strip()
            if _stripped.startswith("BOOKFLOW_DEBUG_VERIFICATION_CODE="):
                _val = _stripped.split("=", 1)[1].strip().strip('"').strip("'")
                _debug_mode = _val.lower() in {"1", "true", "yes", "on"}
                break

    if _debug_mode:
        # 调试模式：不发送邮件，直接返回验证码供网页显示
        delivery = "local_debug"
    elif is_email:
        from bookflow_core.services.mailer import send_verification_email
        sent = send_verification_email(normalized, code, purpose)
        delivery = "email" if sent else "failed"
    else:
        raise BookFlowError("请使用邮箱地址接收验证码，短信通道暂未开放。", code="VALIDATION_ERROR")

    result: dict = {
        "account": normalized,
        "purpose": purpose,
        "expires_in_seconds": 600,
        "delivery": delivery,
    }
    if _debug_mode:
        result["debug_code"] = code
    return result


def register_reader(db: Session, *, name: str | None = None, email: str | None = None, phone: str | None = None, code: str | None = None, password: str | None = None, confirmPassword: str | None = None, accepted: bool | None = None, commit: bool = True) -> dict:
    if not accepted:
        raise BookFlowError("请先同意读者服务条款。", code="VALIDATION_ERROR")
    reader_name = str(name or "").strip()
    if not reader_name:
        raise BookFlowError("姓名不能为空。", code="VALIDATION_ERROR")
    email_value = _normalize_account(email) or None
    phone_value = re.sub(r"\s+", "", str(phone or "").strip()) or None
    # 直接从 .env 文件读取调试模式，与验证码发送逻辑保持一致
    from bookflow_core.core.config import project_root
    _reg_debug = False
    _env_path = project_root() / ".env"
    if _env_path.exists():
        for _line in _env_path.read_text(encoding="utf-8").splitlines():
            _stripped = _line.strip()
            if _stripped.startswith("BOOKFLOW_DEBUG_VERIFICATION_CODE="):
                _val = _stripped.split("=", 1)[1].strip().strip('"').strip("'")
                _reg_debug = _val.lower() in {"1", "true", "yes", "on"}
                break
    if not _reg_debug and not email_value:
        raise BookFlowError("请填写邮箱地址以接收验证码。", code="VALIDATION_ERROR")
    account = phone_value or email_value
    if not account:
        raise BookFlowError("手机号或邮箱至少填写一项。", code="VALIDATION_ERROR")
    password_value = _validate_password(password, confirmPassword)
    # 传入手机号和邮箱作为候选，避免验证码存邮箱名下却用手机号查（或反过来）
    _extra = []
    if phone_value and email_value:
        _extra = [email_value] if account == phone_value else [phone_value]
    _verify_reader_code(db, account=account, code=code, purpose="register", extra_accounts=_extra)
    phone_hash = _account_hash(phone_value) if phone_value else None
    unique_clauses = [ReaderCredential.login_name == account]
    if email_value:
        unique_clauses.append(ReaderCredential.email == email_value)
    if phone_hash:
        unique_clauses.append(ReaderCredential.phone_hash == phone_hash)
    if db.scalar(select(ReaderCredential).where(or_(*unique_clauses))):
        raise BookFlowError("该手机号或邮箱已注册。", code="VALIDATION_ERROR")
    reader = ReaderAccount(
        reader_code=_next_reader_code(db),
        reader_type_code="adult",
        reader_type_name="普通读者",
        name=reader_name,
        phone_masked=_mask_phone(phone_value),
        phone_hash=phone_hash,
        email=email_value,
        status="active",
        credit_score="100",
        registered_at=now(),
        active_90d="是",
        current_borrow_count=0,
        created_at=now(),
        updated_at=now(),
    )
    db.add(reader)
    db.flush()
    credential = ReaderCredential(reader_id=reader.id, login_name=account, phone_hash=phone_hash, email=email_value, password_hash=hash_password(password_value), status="active", created_at=now(), updated_at=now())
    db.add(credential)
    db.add(ReaderNotificationSetting(reader_id=reader.id, borrow_due_enabled=True, reservation_arrival_enabled=True, system_notice_enabled=True, email_enabled=bool(email_value), sms_enabled=bool(phone_value), created_at=now(), updated_at=now()))
    if commit:
        db.commit()
        db.refresh(reader)
    token = create_access_token(reader.id, role="reader", subject_type="reader", reader_code=reader.reader_code)
    return {"access_token": token, "token_type": "bearer", "reader": _reader_public(reader)}


def reset_reader_password(db: Session, *, account: str, code: str | None = None, password: str | None = None, confirmPassword: str | None = None, commit: bool = True) -> dict:
    normalized = _normalize_account(account)
    password_value = _validate_password(password, confirmPassword)
    _verify_reader_code(db, account=normalized, code=code, purpose="reset_password")
    account_hash = _account_hash(normalized)
    credential = db.scalar(select(ReaderCredential).where(or_(ReaderCredential.login_name == normalized, ReaderCredential.email == normalized, ReaderCredential.phone_hash == account_hash)).order_by(ReaderCredential.id))
    if not credential:
        raise BookFlowError("未找到对应读者账号。", code="READER_NOT_FOUND")
    credential.password_hash = hash_password(password_value)
    credential.updated_at = now()
    if commit:
        db.commit()
    return {"reset": True, "account": normalized}


def current_reader_to_dict(reader: ReaderAccount, db: Session | None = None) -> dict:
    if db is None:
        return _reader_public(reader)
    data = reader_to_dict(reader, db)
    data["status"] = reader.status
    return data


def upsert_reader_notification_settings(db: Session, reader: ReaderAccount, updates: dict[str, bool], *, commit: bool = True) -> dict:
    allowed = {
        "borrow_due_enabled",
        "reservation_arrival_enabled",
        "system_notice_enabled",
        "email_enabled",
    }
    values = {key: bool(value) for key, value in updates.items() if key in allowed}
    if not values:
        row = get_reader_notification_settings(db, reader)
        return row or {}
    existing = db.execute(
        text("SELECT id FROM reader_notification_settings WHERE reader_id = :reader_id"),
        {"reader_id": reader.id},
    ).first()
    stamp = now()
    if existing:
        assignments = ", ".join(f"{key} = :{key}" for key in values)
        db.execute(
            text(f"UPDATE reader_notification_settings SET {assignments}, updated_at = :updated_at WHERE reader_id = :reader_id"),
            {**{key: int(value) for key, value in values.items()}, "reader_id": reader.id, "updated_at": stamp},
        )
    else:
        db.execute(
            text(
                """
                INSERT INTO reader_notification_settings (
                    reader_id,
                    borrow_due_enabled,
                    reservation_arrival_enabled,
                    system_notice_enabled,
                    email_enabled,
                    created_at,
                    updated_at
                ) VALUES (
                    :reader_id,
                    :borrow_due_enabled,
                    :reservation_arrival_enabled,
                    :system_notice_enabled,
                    :email_enabled,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "reader_id": reader.id,
                "borrow_due_enabled": int(values.get("borrow_due_enabled", True)),
                "reservation_arrival_enabled": int(values.get("reservation_arrival_enabled", True)),
                "system_notice_enabled": int(values.get("system_notice_enabled", True)),
                "email_enabled": int(values.get("email_enabled", False)),
                "created_at": stamp,
                "updated_at": stamp,
            },
        )
    db.flush()
    if commit:
        db.commit()
    return get_reader_notification_settings(db, reader) or {}


def get_reader_notification_settings(db: Session, reader: ReaderAccount) -> dict | None:
    row = db.execute(
        text(
            """
            SELECT
                borrow_due_enabled,
                reservation_arrival_enabled,
                system_notice_enabled,
                email_enabled,
                updated_at
            FROM reader_notification_settings
            WHERE reader_id = :reader_id
            """
        ),
        {"reader_id": reader.id},
    ).mappings().first()
    if not row:
        return None
    return {
        "enabled": True,
        "borrow_due_enabled": bool(row["borrow_due_enabled"]),
        "reservation_arrival_enabled": bool(row["reservation_arrival_enabled"]),
        "system_notice_enabled": bool(row["system_notice_enabled"]),
        "email_enabled": bool(row["email_enabled"]),
        "updated_at": str(row["updated_at"]) if row["updated_at"] else None,
        "items": [
            {"key": "borrow_due_enabled", "label": "借阅到期提醒", "enabled": bool(row["borrow_due_enabled"]), "mutable": True},
            {"key": "reservation_arrival_enabled", "label": "预约到书提醒", "enabled": bool(row["reservation_arrival_enabled"]), "mutable": True},
            {"key": "system_notice_enabled", "label": "系统通知", "enabled": bool(row["system_notice_enabled"]), "mutable": True},
            {"key": "email_enabled", "label": "邮件通知", "enabled": bool(row["email_enabled"]), "mutable": True},
        ],
    }
