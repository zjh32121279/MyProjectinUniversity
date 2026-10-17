from __future__ import annotations

import json
from datetime import datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bookflow_core.core.time import today
from bookflow_core.models import (
    AICapability,
    AIApprovalRequest,
    AgentRun,
    CirculationRule,
    SystemSetting,
    WorkTask,
)

WAITING_GRANT_STATUSES = {"waiting", "pending", "requested"}
OPEN_TASK_STATUSES = {"pending", "ai_processing", "waiting_human", "admin_processing"}
HIGH_RISK_PRIORITIES = {"high", "urgent", "critical"}
RISK_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4, "forbidden": 5}
RISK_LABELS = {"low": "低风险", "normal": "普通风险", "medium": "中风险", "high": "高风险", "critical": "严重风险", "forbidden": "禁止"}
TOKEN_KEYS = {"total_tokens", "token_usage", "tokens_used", "token_count", "input_tokens", "output_tokens"}


def _count(db: Session, stmt) -> int:
    return int(db.scalar(stmt) or 0)


def _json(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {"raw": raw}
    return data if isinstance(data, dict) else {"value": data}


def _as_text(value, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def risk_label(level: str | None) -> str:
    return RISK_LABELS.get((level or "").lower(), "待确认")


def risk_from_text(*values: object) -> str:
    raw = " ".join(_as_text(value).lower() for value in values)
    if any(key in raw for key in ["critical", "forbidden", "high", "export", "delete", "denied", "停用", "导出", "删除", "越权"]):
        return "high"
    if any(key in raw for key in ["failed", "error", "warning", "medium", "异常", "失败", "警告"]):
        return "medium"
    return "low"


def token_count_from_payload(value) -> int:
    if isinstance(value, dict):
        total = 0
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized in TOKEN_KEYS:
                try:
                    total += int(float(item or 0))
                except (TypeError, ValueError):
                    continue
            elif isinstance(item, (dict, list)):
                total += token_count_from_payload(item)
        return total
    if isinstance(value, list):
        return sum(token_count_from_payload(item) for item in value)
    return 0


def source_label(source: str | None) -> str:
    source = source or ""
    return {
        "ai_admin": "BookFlow AI",
        "system": "系统",
        "admin": "普通管理员",
        "super_admin": "超级管理员",
    }.get(source, source or "未知来源")


def result_label(result: str | None) -> str:
    value = (result or "").lower()
    if value in {"success", "ok", "done"}:
        return "成功"
    if value in {"failed", "error", "denied"}:
        return "失败"
    return result or "-"


def today_window() -> tuple[datetime, datetime]:
    start = datetime.combine(today(), time.min)
    return start, start + timedelta(days=1)


def waiting_approval_count(db: Session) -> int:
    return _count(db, select(func.count(AIApprovalRequest.id)).where(AIApprovalRequest.status.in_(WAITING_GRANT_STATUSES)))


def review_task_count(db: Session) -> int:
    return _count(
        db,
        select(func.count(WorkTask.id)).where(
            WorkTask.status.in_(OPEN_TASK_STATUSES),
            (WorkTask.requires_human_confirmation == True) | (WorkTask.priority.in_(HIGH_RISK_PRIORITIES)),
        ),
    )


def ai_rule_enabled_rate(db: Session) -> int:
    capability_total = _count(db, select(func.count(AICapability.id)))
    capability_enabled = _count(db, select(func.count(AICapability.id)).where(AICapability.is_enabled == True))
    if capability_total == 0:
        return 0
    system_total = _count(db, select(func.count(SystemSetting.id)))
    system_enabled = _count(db, select(func.count(SystemSetting.id)).where(SystemSetting.is_active == True))
    rule_total = _count(db, select(func.count(CirculationRule.id)))
    rule_enabled = _count(db, select(func.count(CirculationRule.id)).where(CirculationRule.is_active == True))
    total = capability_total + system_total + rule_total
    if total == 0:
        return 0
    enabled = capability_enabled + system_enabled + rule_enabled
    return round(enabled * 100 / total)
