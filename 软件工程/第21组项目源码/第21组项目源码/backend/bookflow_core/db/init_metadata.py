from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from bookflow_core.ai.tools.capability_defaults import infer_tool_defaults
from bookflow_core.ai.tools.registry import registered_tool_names
from bookflow_core.core.database import create_db, get_engine
from bookflow_core.core.time import now
from bookflow_core.models import (
    AICapability,
    AdminPermission,
    AdminRole,
    AdminRolePermission,
    CirculationPolicy,
    CirculationRule,
    SystemSetting,
)

DEFAULT_DB = BACKEND_ROOT / "data" / "bookflow.db"


ROLES = [
    {"role_code": "super_admin", "name": "超级管理员", "description": "系统治理、管理员管理、AI 与审计控制", "is_system": True},
    {"role_code": "admin", "name": "普通管理员", "description": "日常馆务运营统一权限，不再细分岗位角色", "is_system": True},
]

PERMISSIONS = [
    ("catalog.read", "查看馆藏", "catalog", "查看书目、副本和架位", "low"),
    ("catalog.write", "维护馆藏", "catalog", "新增、编辑、下架书目和副本", "medium"),
    ("circulation.read", "查看流通", "circulation", "查看借阅、预约和逾期", "low"),
    ("circulation.write", "办理流通", "circulation", "办理借书、还书、续借和预约", "medium"),
    ("reader.read", "查看读者", "reader", "查看读者账户和信用记录", "low"),
    ("reader.write", "维护读者", "reader", "维护读者状态和信用分", "medium"),
    ("notifications:read", "查看通知", "notification", "查看通知主体、投递记录和通知统计", "low"),
    ("notifications:write", "发送通知", "notification", "创建和发送读者/管理员通知", "medium"),
    ("workflow.write", "处理任务", "workflow", "认领、处理和关闭工作任务", "medium"),
    ("risk.write", "处理风险", "risk", "确认、忽略和解决风险预警", "high"),
    ("ai.use", "使用 AI", "ai", "使用 AI 工作台和助手", "medium"),
    ("ai.govern", "治理 AI", "ai", "审批高风险 AI 动作和规则", "high"),
    ("audit.read", "查看审计", "audit", "查看系统审计事件", "medium"),
    ("admin.manage", "管理管理员", "admin", "启停账号和调整角色权限", "high"),
    ("settings.manage", "管理系统配置", "settings", "维护系统设置和规则", "high"),
]

ROLE_PERMISSION_CODES = {
    "super_admin": [code for code, *_ in PERMISSIONS],
    "admin": [
        "catalog.read",
        "catalog.write",
        "circulation.read",
        "circulation.write",
        "reader.read",
        "reader.write",
        "notifications:read",
        "notifications:write",
        "workflow.write",
        "risk.write",
        "ai.use",
        "audit.read",
    ],
}

SETTINGS = [
    ("reservation_hold_hours", "48", "int", "circulation", "预约到书后默认保留 48 小时"),
    ("default_page_size", "20", "int", "system", "后台默认分页条数"),
    ("audit_log_retention_days", "180", "int", "audit", "操作日志保留天数"),
    ("auto_backup_time", "02:00", "string", "system", "每日自动备份时间"),
    ("ai_task_timeout_seconds", "180", "int", "ai", "AI 单个任务默认超时时间"),
    ("ai_low_confidence_threshold", "0.65", "float", "ai", "低置信度任务转人工阈值"),
]

READER_TYPES = [
    ("child", "儿童读者", 5),
    ("teen", "青少年读者", 6),
    ("adult", "成人读者", 8),
    ("senior", "老年读者", 8),
    ("institution", "机构账号", 30),
]

CIRCULATION_DAYS = {
    "hot": (14, 0),
    "normal": (30, 1),
    "cold": (45, 2),
}

def _url_for(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _upsert(session: Session, model, key_name: str, key_value, values: dict) -> object:
    row = session.scalar(select(model).where(getattr(model, key_name) == key_value))
    if row is None:
        row = model(**{key_name: key_value})
        session.add(row)
    for field, value in values.items():
        setattr(row, field, value)
    return row


def seed_metadata(session: Session) -> dict[str, int]:
    stamp = now()

    for role in ROLES:
        _upsert(
            session,
            AdminRole,
            "role_code",
            role["role_code"],
            {**role, "updated_at": stamp, "created_at": stamp},
        )

    for code, name, module, description, risk_level in PERMISSIONS:
        _upsert(
            session,
            AdminPermission,
            "permission_code",
            code,
            {
                "permission_code": code,
                "name": name,
                "module": module,
                "description": description,
                "risk_level": risk_level,
                "created_at": stamp,
                "updated_at": stamp,
            },
        )
    session.flush()

    role_by_code = {row.role_code: row for row in session.scalars(select(AdminRole)).all()}
    permission_by_code = {row.permission_code: row for row in session.scalars(select(AdminPermission)).all()}
    for role_code, permission_codes in ROLE_PERMISSION_CODES.items():
        role = role_by_code[role_code]
        for permission_code in permission_codes:
            permission = permission_by_code[permission_code]
            exists = session.scalar(
                select(AdminRolePermission).where(
                    AdminRolePermission.role_id == role.id,
                    AdminRolePermission.permission_id == permission.id,
                )
            )
            if exists is None:
                session.add(AdminRolePermission(role_id=role.id, permission_id=permission.id, created_at=stamp))

    for key, value, value_type, scope, description in SETTINGS:
        _upsert(
            session,
            SystemSetting,
            "setting_key",
            key,
            {
                "setting_key": key,
                "setting_value": value,
                "value_type": value_type,
                "scope": scope,
                "description": description,
                "is_active": True,
                "created_at": stamp,
                "updated_at": stamp,
            },
        )

    for reader_type, reader_type_name, limit in READER_TYPES:
        for circulation_type, (borrow_days, renewals) in CIRCULATION_DAYS.items():
            rule_code = f"{reader_type}:{circulation_type}"
            _upsert(
                session,
                CirculationRule,
                "rule_code",
                rule_code,
                {
                    "rule_code": rule_code,
                    "reader_type_code": reader_type,
                    "reader_type_name": reader_type_name,
                    "circulation_type": circulation_type,
                    "max_borrow_count": limit,
                    "borrow_days": borrow_days if reader_type != "senior" else borrow_days + 7,
                    "max_renewals": renewals,
                    "reservation_limit": min(limit, 5),
                    "is_active": True,
                    "created_at": stamp,
                    "updated_at": stamp,
                },
            )

    if session.scalar(select(CirculationPolicy).where(CirculationPolicy.is_active == True)) is None:
        session.add(
            CirculationPolicy(
                hot_borrow_90d_threshold=12,
                hot_reserve_90d_threshold=3,
                cold_borrow_365d_threshold=1,
                cold_days_since_last_borrow_threshold=180,
                reservation_hold_days=2,
                is_active=True,
                created_at=stamp,
                updated_at=stamp,
            )
        )

    for tool_name in registered_tool_names():
        _upsert(
            session,
            AICapability,
            "tool_name",
            tool_name,
            infer_tool_defaults(tool_name, stamp=stamp),
        )

    session.flush()
    return {
        "admin_roles": int(session.query(AdminRole).count()),
        "admin_permissions": int(session.query(AdminPermission).count()),
        "admin_role_permissions": int(session.query(AdminRolePermission).count()),
        "system_settings": int(session.query(SystemSetting).count()),
        "circulation_rules": int(session.query(CirculationRule).count()),
        "ai_capabilities": int(session.query(AICapability).count()),
    }


def run(db_path: Path = DEFAULT_DB) -> dict:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    create_db(_url_for(db_path))
    engine = get_engine(_url_for(db_path))
    with Session(engine) as session:
        counts = seed_metadata(session)
        session.commit()
    return {"ok": True, "database": str(db_path), "counts": counts}


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize BookFlow system metadata only.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    print(json.dumps(run(args.db), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
