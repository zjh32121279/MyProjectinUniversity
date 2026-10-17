from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bookflow_core.models import (
    AICapability,
    AIRule,
    AgentRun,
    CirculationPolicy,
    CirculationRule,
    SystemSetting,
)
from bookflow_core.services.rule_service import policy_to_dict, rule_to_dict, system_setting_to_dict
from bookflow_core.services.super_admin_common import (
    _count,
    today_window,
    waiting_approval_count,
)


def _system_rule_type(row: SystemSetting) -> str:
    text = f"{row.setting_key or ''} {row.description or ''}".lower()
    if any(key in text for key in ["notice", "notification", "message", "remind", "sms", "email", "overdue", "通知", "提醒", "消息"]):
        return "notification_rule"
    return "system_builtin"


def _rule_type_label(rule_type: str) -> str:
    return {
        "business_rule": "业务规则",
        "notification_rule": "通知规则",
        "ai_rule": "AI 规则",
        "ai_tool": "AI 工具能力",
        "system_builtin": "系统内置",
    }.get(rule_type, rule_type)


def _reader_type_label(code: str | None, fallback: str | None = None) -> str:
    value = (code or "").lower()
    return {
        "adult": "成人读者",
        "child": "少儿读者",
        "senior": "老年读者",
        "institution": "机构读者",
        "teacher": "教师读者",
        "student": "学生读者",
        "general": "普通读者",
    }.get(value, fallback or code or "读者")


def _circulation_type_label(code: str | None) -> str:
    value = (code or "").lower()
    return {
        "hot": "热门馆藏",
        "cold": "冷门馆藏",
        "normal": "普通馆藏",
        "reference": "参考馆藏",
        "rare": "特藏馆藏",
    }.get(value, code or "馆藏")


def _ai_module_label(code: str | None) -> str:
    value = (code or "").lower()
    return {
        "borrow": "借阅辅助",
        "borrowing": "借阅辅助",
        "circulation": "流通服务",
        "recommendation": "智能推荐",
        "search": "智能检索",
        "catalog": "编目辅助",
        "audit": "审计安全",
        "notification": "通知提醒",
        "reader": "读者服务",
    }.get(value, code or "AI 服务")


def _permission_label(code: str | None) -> str:
    value = (code or "").upper()
    return {
        "L1": "只读查询",
        "L2": "辅助建议",
        "L3": "受控执行",
        "L4": "高风险操作",
        "L5": "超级管理员授权",
    }.get(value, code or "未分级")


def ai_rule_rows(db: Session) -> list[dict]:
    rows: list[dict] = []
    for row in db.scalars(select(CirculationRule).order_by(CirculationRule.reader_type_code, CirculationRule.circulation_type)).all():
        data = rule_to_dict(row)
        rule_type = "business_rule"
        reader_label = _reader_type_label(row.reader_type_code, row.reader_type_name)
        circulation_label = _circulation_type_label(row.circulation_type)
        data.update({"reader_type_label": reader_label, "circulation_type_label": circulation_label})
        rows.append(
            {
                "id": f"borrow-{row.reader_type_code}-{row.circulation_type}",
                "title": f"{reader_label} / {circulation_label} 借阅规则",
                "description": f"可借 {row.max_borrow_count} 本，借期 {row.borrow_days} 天，最多续借 {row.max_renewals} 次",
                "type": _rule_type_label(rule_type),
                "rule_type": rule_type,
                "category": "borrow",
                "active": row.is_active,
                "status": "enabled" if row.is_active else "disabled",
                "editable": True,
                "editable_fields": ["max_borrow_count", "borrow_days", "max_renewals"],
                "priority": "normal",
                "risk_level": "low",
                "updated_at": row.updated_at,
                "data": data,
            }
        )
    for row in db.scalars(select(SystemSetting).order_by(SystemSetting.setting_key)).all():
        rule_type = _system_rule_type(row)
        description = row.description or "系统配置项"
        rows.append(
            {
                "id": f"system-{row.setting_key}",
                "title": description,
                "description": f"当前值：{row.setting_value}",
                "type": _rule_type_label(rule_type),
                "rule_type": rule_type,
                "category": "system",
                "active": row.is_active,
                "status": "enabled" if row.is_active else "disabled",
                "editable": True,
                "editable_fields": ["setting_value", "value_type", "description"],
                "priority": "medium",
                "risk_level": "medium",
                "updated_at": row.updated_at,
                "data": system_setting_to_dict(row),
            }
        )
    for row in db.scalars(select(AIRule).order_by(AIRule.module, AIRule.priority, AIRule.rule_code)).all():
        rule_type = "ai_rule"
        module_label = _ai_module_label(row.module)
        reader_label = _reader_type_label(row.target_reader_type, "全部读者")
        circulation_label = _circulation_type_label(row.target_circulation_type) if row.target_circulation_type else "全部馆藏"
        rows.append(
            {
                "id": f"airule-{row.rule_code}",
                "title": row.rule_name or row.rule_code,
                "description": f"{module_label}，适用 {reader_label}、{circulation_label}",
                "type": _rule_type_label(rule_type),
                "rule_type": rule_type,
                "category": "airule",
                "active": row.is_enabled,
                "status": "enabled" if row.is_enabled else "disabled",
                "editable": False,
                "editable_fields": [],
                "priority": "high" if (row.priority or 0) >= 80 else "normal",
                "risk_level": row.risk_level or "medium",
                "updated_at": row.updated_at,
                "data": {
                    "rule_code": row.rule_code,
                    "rule_name": row.rule_name,
                    "rule_type": row.rule_type,
                    "module": row.module,
                    "module_label": module_label,
                    "target_reader_type": row.target_reader_type,
                    "target_reader_type_label": reader_label,
                    "target_circulation_type": row.target_circulation_type,
                    "target_circulation_type_label": circulation_label,
                    "priority": row.priority,
                    "status": row.status,
                },
            }
        )
    policy = db.scalar(select(CirculationPolicy).where(CirculationPolicy.is_active == True).order_by(CirculationPolicy.id.desc()))
    if policy:
        rule_type = "system_builtin"
        rows.append(
            {
                "id": "policy-active",
                "title": "馆藏流通冷热策略",
                "description": f"热门借阅阈值 {policy.hot_borrow_90d_threshold}，冷门未借阈值 {policy.cold_days_since_last_borrow_threshold} 天",
                "type": _rule_type_label(rule_type),
                "rule_type": rule_type,
                "category": "policy",
                "active": policy.is_active,
                "status": "enabled" if policy.is_active else "disabled",
                "editable": True,
                "editable_fields": [
                    "hot_borrow_90d_threshold",
                    "hot_reserve_90d_threshold",
                    "cold_borrow_365d_threshold",
                    "cold_days_since_last_borrow_threshold",
                ],
                "priority": "medium",
                "risk_level": "medium",
                "updated_at": policy.updated_at,
                "data": policy_to_dict(policy),
            }
        )
    for row in db.scalars(select(AICapability).order_by(AICapability.tool_name)).all():
        priority = "high" if row.requires_super_authorization or row.permission_level in {"L4", "L5"} else "normal"
        rule_type = "ai_tool"
        rows.append(
            {
                "id": f"ai-{row.tool_name}",
                "title": row.display_name or row.tool_name,
                "description": row.description or f"{row.permission_level} / {row.tool_name}",
                "type": _rule_type_label(rule_type),
                "rule_type": rule_type,
                "category": "ai",
                "active": row.is_enabled,
                "status": "enabled" if row.is_enabled else "disabled",
                "editable": False,
                "editable_fields": [],
                "priority": priority,
                "risk_level": row.risk_level,
                "updated_at": row.updated_at,
                "data": {
                    "tool_name": row.tool_name,
                    "display_name": row.display_name or row.tool_name,
                    "permission_level": row.permission_level,
                    "permission_label": _permission_label(row.permission_level),
                    "requires_super_authorization": row.requires_super_authorization,
                    "writes_db": row.writes_db,
                },
            }
        )
    return rows


def ai_rule_management(db: Session, *, limit: int = 100, offset: int = 0) -> dict:
    rows = ai_rule_rows(db)
    total = len(rows)
    enabled = sum(1 for row in rows if row["active"])
    high_priority = sum(1 for row in rows if row["priority"] == "high")
    today_start, today_end = today_window()
    today_runs = _count(db, select(func.count(AgentRun.id)).where(AgentRun.created_at >= today_start, AgentRun.created_at < today_end))
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    return {
        "items": rows[offset : offset + limit],
        "total": total,
        "limit": limit,
        "offset": offset,
        "summary": {
            "enabled": enabled,
            "pendingChanges": waiting_approval_count(db),
            "highPriority": high_priority,
            "todayTriggers": today_runs,
        },
    }
