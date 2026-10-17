from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from bookflow_core.core.exceptions import BookFlowError
from bookflow_core.models import (
    AgentRun,
    AgentStep,
    WorkTask,
)
from bookflow_core.services.statistics_service import get_business_date


def _snapshot_payload(db: Session, snapshot_key: str) -> dict:
    return {}


def _dashboard_ai_insights(db: Session, operations: dict) -> list[dict]:
    payload = _snapshot_payload(db, "dashboard_ai_insights")
    items = payload.get("items", [])
    if not isinstance(items, list):
        return []
    insights: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        count_key = item.get("count_key")
        count = operations.get(count_key, item.get("count", 0)) if isinstance(count_key, str) else item.get("count", 0)
        insights.append({"type": item.get("type", ""), "message": item.get("message", ""), "count": count})
    return insights


def _home_ai_summary_lines(payload: dict) -> list[str]:
    raw_lines = payload.get("lines")
    if not isinstance(raw_lines, list):
        raw_lines = payload.get("items")
    if not isinstance(raw_lines, list) and payload.get("summary"):
        raw_lines = [payload.get("summary")]
    if not isinstance(raw_lines, list):
        return []
    lines = [str(line).strip() for line in raw_lines if str(line).strip()]
    return lines[:3]


def _home_ai_summary_prompt(operations: dict) -> list[dict]:
    metrics = {
        "business_date": operations.get("business_date"),
        "today_borrow_count": operations.get("today_borrow_count", 0),
        "today_return_count": operations.get("today_return_count", 0),
        "overdue_count": operations.get("overdue_count", 0),
        "reservation_count": operations.get("reservation_count", 0),
        "pending_shelving_count": operations.get("pending_shelving_count", 0),
        "risk_warning_count": operations.get("risk_warning_count", 0),
        "due_today_count": operations.get("due_today_count", 0),
        "current_visit_reader_count": operations.get("current_visit_reader_count", 0),
    }
    return [
        {
            "role": "system",
            "content": (
                "你是 BookFlow 图书馆运营 AI。基于给定结构化指标生成首页 AI 摘要。"
                "只返回 JSON 对象，字段为 badge 和 lines。"
                "lines 必须是 2 到 3 条中文短句，每条不超过 34 个汉字；"
                "不得编造未提供的日期、数值或已执行动作。"
            ),
        },
        {"role": "user", "content": json.dumps({"metrics": metrics}, ensure_ascii=False)},
    ]


def _cached_home_ai_summary(db: Session, operations: dict) -> dict | None:
    payload = _snapshot_payload(db, "home_ai_summary")
    if payload.get("source") != "ai_engine":
        return None
    if str(payload.get("business_date") or "") != str(operations.get("business_date") or ""):
        return None
    status = str(payload.get("status") or "")
    if status != "generated":
        retry_after = payload.get("retry_after")
        if not isinstance(retry_after, str):
            return None
        try:
            retry_at = datetime.fromisoformat(retry_after)
        except ValueError:
            return None
        if retry_at <= datetime.now(timezone.utc):
            return None
    lines = _home_ai_summary_lines(payload)
    if not lines:
        return None
    return {
        **payload,
        "status": status or "cached",
        "badge": payload.get("badge") or "今日概览",
        "lines": lines,
    }


def _home_ai_summary(db: Session, operations: dict, *, generate: bool = False) -> dict:
    from bookflow_core.ai.engine.openai_compatible_client import OpenAICompatibleClient

    client = OpenAICompatibleClient(timeout_seconds=4)
    status = client.status()
    if not status.enabled:
        return {
            "status": "not_configured",
            "code": "AI_ENGINE_NOT_CONFIGURED",
            "badge": "未接入",
            "lines": ["AI 暂未接入，暂无自动摘要。"],
            "required_env": status.required_env,
            "missing_env": status.missing_env,
        }

    cached = _cached_home_ai_summary(db, operations)
    if cached:
        return cached
    if not generate:
        return {
            "status": "not_generated",
            "badge": "待生成",
            "lines": ["AI 摘要尚未生成，等待引擎生成今日概览。"],
        }

    try:
        generated = client.complete_json(messages=_home_ai_summary_prompt(operations), temperature=0.2)
        lines = _home_ai_summary_lines(generated)
        if not lines:
            raise BookFlowError(
                "BookFlow AI engine returned an invalid home summary.",
                code="AI_ENGINE_UNAVAILABLE",
                details={"reason": "invalid_home_summary"},
            )
        payload = {
            "status": "generated",
            "source": "ai_engine",
            "business_date": str(operations.get("business_date") or ""),
            "badge": str(generated.get("badge") or "今日概览")[:12],
            "lines": lines,
            "model": status.model,
        }
        return payload
    except BookFlowError as exc:
        if exc.code == "AI_ENGINE_NOT_CONFIGURED":
            return {
                "status": "not_configured",
                "code": exc.code,
                "badge": "未接入",
                "lines": ["AI 暂未接入，暂无自动摘要。"],
                "details": exc.details,
            }
        payload = {
            "status": "unavailable",
            "code": exc.code,
            "source": "ai_engine",
            "business_date": str(operations.get("business_date") or ""),
            "badge": "未接入",
            "lines": ["AI 暂未接入，暂无自动摘要。"],
            "retry_after": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            "details": exc.details,
        }
        return payload


def ai_efficiency(db: Session, *, business_date: date | str | None = None) -> dict:
    from bookflow_core.models import AIApprovalRequest

    as_of = get_business_date(db, business_date)

    def elapsed_seconds(started_at, finished_at, created_at=None, updated_at=None) -> float:
        start = started_at or created_at
        finish = finished_at or updated_at
        if not start or not finish:
            return 0.0
        seconds = (finish - start).total_seconds()
        return seconds if seconds > 0 else 0.0

    def average_seconds(values: list[float]) -> float:
        valid = [value for value in values if value >= 0]
        return round(sum(valid) / len(valid), 2) if valid else 0.0

    def status_label(status: str) -> str:
        labels = {
            "success": "成功", "completed": "成功", "resolved": "成功",
            "running": "处理中", "pending": "待复核", "ai_processing": "AI处理中", "waiting_human": "待人工介入", "admin_processing": "人工处理中", "waiting": "待授权",
            "failed": "失败", "rejected": "已拒绝", "rejected_by_super_admin": "超管拒绝", "cancelled": "已取消",
        }
        return labels.get(status or "", status or "未知状态")

    def task_title_group(title: str) -> str:
        text = (title or "AI 复核任务").strip()
        for sep in ["-", "－", "—", " "]:
            if sep in text:
                text = text.split(sep, 1)[0]
                break
        return text[:18] or "AI 复核任务"

    total_runs = int(db.scalar(select(func.count(AgentRun.id))) or 0)
    success_run_statuses = {"success", "completed", "succeeded"}
    failed_run_statuses = {"failed", "rejected", "rejected_by_super_admin", "error"}
    success_runs = int(db.scalar(select(func.count(AgentRun.id)).where(AgentRun.status.in_(success_run_statuses))) or 0)
    failed_count = int(db.scalar(select(func.count(AgentRun.id)).where(AgentRun.status.in_(failed_run_statuses))) or 0)
    waiting_approvals = int(db.scalar(select(func.count(AIApprovalRequest.id)).where(AIApprovalRequest.status == "waiting")) or 0)
    rejected_runs = int(db.scalar(select(func.count(AgentRun.id)).where(AgentRun.status.like("%reject%"))) or 0)
    steps = int(db.scalar(select(func.count(AgentStep.id))) or 0)

    if total_runs:
        tool_rows = db.execute(select(AgentRun.tool_name, func.count(AgentRun.id)).group_by(AgentRun.tool_name).order_by(func.count(AgentRun.id).desc()).limit(10)).all()
        status_rows = db.execute(select(AgentRun.status, func.count(AgentRun.id)).group_by(AgentRun.status).order_by(func.count(AgentRun.id).desc())).all()
        recent_runs = db.scalars(select(AgentRun).order_by(AgentRun.id.desc()).limit(10)).all()
        run_timing_rows = db.scalars(select(AgentRun)).all()
        avg_seconds = average_seconds([
            elapsed_seconds(row.started_at, row.finished_at, row.created_at, row.updated_at)
            for row in run_timing_rows
        ])
        avg_minutes = avg_seconds / 60
        trend_rows = db.execute(
            select(func.date(AgentRun.created_at), AgentRun.status, func.count(AgentRun.id))
            .group_by(func.date(AgentRun.created_at), AgentRun.status)
            .order_by(func.date(AgentRun.created_at))
        ).all()
        labels = sorted({str(day) for day, _status, _count in trend_rows if day})[-7:]
        success_by_day = {label: 0 for label in labels}
        transfer_by_day = {label: 0 for label in labels}
        total_by_day = {label: 0 for label in labels}
        for day, status, count in trend_rows:
            key = str(day)
            if key not in total_by_day:
                continue
            value = int(count or 0)
            total_by_day[key] += value
            if status in success_run_statuses:
                success_by_day[key] += value
            elif status in failed_run_statuses:
                transfer_by_day[key] += value
        daily_trend = {
            "labels": labels,
            "series": [
                {"name": "AI 成功率（%）", "data": [round((success_by_day[label] / total_by_day[label]) * 100, 1) if total_by_day[label] else 0 for label in labels]},
                {"name": "转人工率（%）", "data": [round((transfer_by_day[label] / total_by_day[label]) * 100, 1) if total_by_day[label] else 0 for label in labels]},
            ],
        }
        transfer_items = [{"name": status_label(status), "count": int(count or 0)} for status, count in status_rows if status not in success_run_statuses]
        tool_items = [{"tool_name": name or "未命名工具", "count": int(count)} for name, count in tool_rows]
        recent_actions = [{"run_code": row.run_code, "tool_name": row.tool_name, "status": row.status, "created_at": str(row.created_at)} for row in recent_runs]
        business_items = [{"name": item["tool_name"], "count": item["count"]} for item in tool_items]
    else:
        ai_tasks = db.scalars(
            select(WorkTask)
            .where(
                or_(
                    WorkTask.source_type.like("%ai%"),
                    WorkTask.handler_type.in_(["ai", "mixed"]),
                    WorkTask.claim_status.in_(["ai_claimed", "ai_completed", "waiting_human"]),
                )
            )
            .order_by(WorkTask.id.desc())
        ).all()
        total_runs = len(ai_tasks)
        success_statuses = {"success", "completed", "resolved", "fulfilled", "closed"}
        failed_statuses = {"failed", "cancelled", "rejected", "expired", "waiting_human"}
        success_runs = sum(1 for task in ai_tasks if task.status in success_statuses)
        failed_count = sum(1 for task in ai_tasks if task.status in failed_statuses)
        waiting_approvals = sum(1 for task in ai_tasks if task.status not in success_statuses and task.status not in failed_statuses)
        rejected_runs = sum(1 for task in ai_tasks if "reject" in (task.status or ""))
        steps = 0
        avg_seconds = average_seconds([
            elapsed_seconds(task.ai_started_at, task.ai_finished_at, task.created_at, task.updated_at)
            for task in ai_tasks
        ])
        avg_minutes = avg_seconds / 60

        tool_counter: dict[str, int] = {}
        status_counter: dict[str, int] = {}
        day_counter: dict[str, dict[str, int]] = {}
        for task in ai_tasks:
            group = task_title_group(task.title)
            tool_counter[group] = tool_counter.get(group, 0) + 1
            status_counter[task.status] = status_counter.get(task.status, 0) + 1
            day = str(task.created_at.date()) if task.created_at else str(as_of)
            day_counter.setdefault(day, {"total": 0, "success": 0, "transfer": 0})
            day_counter[day]["total"] += 1
            if task.status in success_statuses:
                day_counter[day]["success"] += 1
            elif task.status not in success_statuses:
                day_counter[day]["transfer"] += 1
        labels = sorted(day_counter.keys())[-7:]
        daily_trend = {
            "labels": labels,
            "series": [
                {"name": "AI 成功率（%）", "data": [round((day_counter[label]["success"] / day_counter[label]["total"]) * 100, 1) if day_counter[label]["total"] else 0 for label in labels]},
                {"name": "转人工率（%）", "data": [round((day_counter[label]["transfer"] / day_counter[label]["total"]) * 100, 1) if day_counter[label]["total"] else 0 for label in labels]},
            ],
        }
        tool_items = [{"tool_name": name, "count": count} for name, count in sorted(tool_counter.items(), key=lambda item: item[1], reverse=True)]
        transfer_items = [{"name": status_label(status), "count": count} for status, count in sorted(status_counter.items(), key=lambda item: item[1], reverse=True) if status not in success_statuses]
        business_items = [{"name": item["tool_name"], "count": item["count"]} for item in tool_items]
        recent_actions = [{"run_code": task.task_code, "tool_name": task_title_group(task.title), "status": task.status, "created_at": str(task.created_at)} for task in ai_tasks[:10]]

    status_items = []
    if total_runs:
        if success_runs:
            status_items.append({"name": "成功", "count": success_runs})
        if failed_count:
            status_items.append({"name": "失败/拒绝", "count": failed_count})
        if waiting_approvals:
            status_items.append({"name": "待授权/待复核", "count": waiting_approvals})

    return {
        "business_date": str(as_of),
        "total_runs": total_runs,
        "total_ai_runs": total_runs,
        "success_runs": success_runs,
        "success_count": success_runs,
        "failed_count": failed_count,
        "waiting_authorization_count": waiting_approvals,
        "rejected_runs": rejected_runs,
        "waiting_approvals": waiting_approvals,
        "agent_steps": steps,
        "average_steps": round(steps / total_runs, 2) if total_runs else 0,
        "average_processing_seconds": round(avg_seconds, 2) if total_runs else 0,
        "average_processing_minutes": round(avg_minutes, 2) if total_runs else 0,
        "success_rate": round(success_runs / total_runs, 4) if total_runs else 0,
        "transfer_rate": round((failed_count + waiting_approvals) / total_runs, 4) if total_runs else 0,
        "tool_usage_rank": {"items": tool_items},
        "business_type_distribution": {"items": business_items},
        "transfer_reason_distribution": {"items": transfer_items},
        "status_distribution": {"items": status_items},
        "daily_efficiency_trend": daily_trend,
        "recent_ai_actions": recent_actions,
    }
