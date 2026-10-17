from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from bookflow_core.core.database import create_db, get_engine
from bookflow_core.core.security import hash_password
from bookflow_core.core.time import now
from bookflow_core.db.init_metadata import seed_metadata
from bookflow_core.models import AdminRole, AdminUser, AdminUserRole

DEFAULT_DB = BACKEND_ROOT / "data" / "bookflow.db"


def _url_for(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _value(arg_value: str | None, env_key: str) -> str:
    return (arg_value or os.getenv(env_key) or "").strip()


def create_superadmin(
    db_path: Path,
    *,
    admin_code: str,
    password: str,
    name: str,
    email: str,
) -> dict:
    if not admin_code:
        raise ValueError("admin_code is required. Use --admin-code or BOOKFLOW_SUPERADMIN_CODE.")
    if not password:
        raise ValueError("password is required. Use --password or BOOKFLOW_SUPERADMIN_PASSWORD.")
    if len(password) < 8:
        raise ValueError("password must contain at least 8 characters.")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    create_db(_url_for(db_path))
    engine = get_engine(_url_for(db_path))
    stamp = now()
    with Session(engine) as session:
        seed_metadata(session)
        row = session.scalar(select(AdminUser).where(AdminUser.admin_code == admin_code))
        created = row is None
        if row is None:
            row = AdminUser(admin_code=admin_code, created_at=stamp)
            session.add(row)
        row.name = name or admin_code
        row.email = email or None
        row.password_hash = hash_password(password)
        row.status = "active"
        row.is_super_admin = True
        row.updated_at = stamp
        session.flush()

        role = session.scalar(select(AdminRole).where(AdminRole.role_code == "super_admin"))
        if role is None:
            raise RuntimeError("super_admin role was not initialized.")
        assignment = session.scalar(
            select(AdminUserRole).where(AdminUserRole.admin_id == row.id, AdminUserRole.role_id == role.id)
        )
        if assignment is None:
            session.add(AdminUserRole(admin_id=row.id, role_id=role.id, created_at=stamp))
        session.commit()
        return {
            "ok": True,
            "database": str(db_path),
            "created": created,
            "admin_code": row.admin_code,
            "admin_id": row.id,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or reset the initial BookFlow super administrator.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--admin-code")
    parser.add_argument("--name")
    parser.add_argument("--email")
    parser.add_argument("--password")
    args = parser.parse_args()

    password = _value(args.password, "BOOKFLOW_SUPERADMIN_PASSWORD")
    if not password and sys.stdin.isatty():
        password = getpass.getpass("Superadmin password: ")

    result = create_superadmin(
        args.db,
        admin_code=_value(args.admin_code, "BOOKFLOW_SUPERADMIN_CODE"),
        name=_value(args.name, "BOOKFLOW_SUPERADMIN_NAME"),
        email=_value(args.email, "BOOKFLOW_SUPERADMIN_EMAIL"),
        password=password,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

