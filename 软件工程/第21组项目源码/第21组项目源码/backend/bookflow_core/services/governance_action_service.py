from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from bookflow_core.core.exceptions import BusinessRuleError, NotFoundError, ValidationError
from bookflow_core.core.time import now
from bookflow_core.models import (
    AICapability,
    AIRule,
    AdminUser,
    AuditEvent,
    CirculationRule,
    ExportJob,
    SystemSetting,
)
from bookflow_core.services.common import as_json, create_snapshot, write_audit
from bookflow_core.services.super_admin_audit import audit_event_to_dict
from bookflow_core.services.rule_service import update_borrow_rule, update_circulation_policy, update_system_setting

RULE_PREFIXES = {"ai", "airule", "system", "borrow", "policy"}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _json(raw: str | None, fallback: Any = None) -> Any:
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return fallback if fallback is not None else {"raw": raw}


def _utc_code(prefix: str) -> str:
    return f"{prefix}-{int(datetime.now(timezone.utc).timestamp() * 1000000)}"


def _date_bound(value: str | None, *, end: bool = False) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text[:10])
    except ValueError:
        return None
    return datetime.combine(parsed.date(), time.max if end else time.min)


def _admin_id_by_code(db: Session, admin_code: str | None) -> int | None:
    if not admin_code:
        return None
    return db.scalar(select(AdminUser.id).where(AdminUser.admin_code == str(admin_code)))


def toggle_rule(db: Session, rule_id: str, *, enabled: bool | None = None, reviewer: str = "super_admin", commit: bool = True) -> dict:
    """Enable/disable a governance rule row returned by ai_rule_management."""
    if not rule_id or "-" not in rule_id:
        raise ValidationError("Invalid rule id.", details={"rule_id": rule_id})
    prefix, raw_key = rule_id.split("-", 1)
    if prefix not in RULE_PREFIXES:
        raise ValidationError("Unsupported rule id prefix.", details={"rule_id": rule_id})
    try:
        if prefix == "ai":
            row = db.scalar(select(AICapability).where(AICapability.tool_name == raw_key))
            if not row:
                raise NotFoundError("AI capability rule not found.", details={"rule_id": rule_id})
            before = {"is_enabled": bool(row.is_enabled), "tool_name": row.tool_name}
            row.is_enabled = (not bool(row.is_enabled)) if enabled is None else bool(enabled)
            after = {"is_enabled": bool(row.is_enabled), "tool_name": row.tool_name}
            target_table, target_id = "ai_capabilities", str(row.id)
        elif prefix == "airule":
            row = db.scalar(select(AIRule).where(AIRule.rule_code == raw_key))
            if not row:
                raise NotFoundError("AI rule not found.", details={"rule_id": rule_id})
            before = {"is_enabled": bool(row.is_enabled), "status": row.status, "rule_code": row.rule_code}
            row.is_enabled = (not bool(row.is_enabled)) if enabled is None else bool(enabled)
            row.status = "enabled" if row.is_enabled else "disabled"
            after = {"is_enabled": bool(row.is_enabled), "status": row.status, "rule_code": row.rule_code}
            target_table, target_id = "ai_rules", str(row.id)
        elif prefix == "system":
            row = db.scalar(select(SystemSetting).where(SystemSetting.setting_key == raw_key))
            if not row:
                raise NotFoundError("System rule not found.", details={"rule_id": rule_id})
            before = {"is_active": bool(row.is_active), "setting_key": row.setting_key, "setting_value": row.setting_value}
            row.is_active = (not bool(row.is_active)) if enabled is None else bool(enabled)
            after = {"is_active": bool(row.is_active), "setting_key": row.setting_key, "setting_value": row.setting_value}
            target_table, target_id = "system_settings", str(row.id)
        else:  # borrow-<reader_type>-<circulation_type>
            parts = raw_key.rsplit("-", 1)
            if len(parts) != 2:
                raise ValidationError("Invalid borrow rule id.", details={"rule_id": rule_id})
            reader_type_code, circulation_type = parts
            row = db.scalar(
                select(CirculationRule).where(
                    CirculationRule.reader_type_code == reader_type_code,
                    CirculationRule.circulation_type == circulation_type,
                )
            )
            if not row:
                raise NotFoundError("Borrow rule not found.", details={"rule_id": rule_id})
            before = {
                "is_active": bool(row.is_active),
                "reader_type_code": row.reader_type_code,
                "circulation_type": row.circulation_type,
                "max_borrow_count": row.max_borrow_count,
                "borrow_days": row.borrow_days,
                "max_renewals": row.max_renewals,
            }
            row.is_active = (not bool(row.is_active)) if enabled is None else bool(enabled)
            after = {**before, "is_active": bool(row.is_active)}
            target_table, target_id = "circulation_rules", str(row.id)
        row.updated_at = now() if hasattr(row, "updated_at") else getattr(row, "updated_at", None)
        create_snapshot(
            db,
            action_type="toggle_rule",
            target_table=target_table,
            target_id=target_id,
            before=before,
            after=after,
            actor_type="super_admin",
            actor_id=reviewer,
            can_rollback=True,
        )
        write_audit(
            db,
            actor_type="super_admin",
            actor_id=reviewer,
            action="toggle_governance_rule",
            target_table=target_table,
            target_id=target_id,
            detail={"rule_id": rule_id, "before": before, "after": after},
        )
        if commit:
            db.commit()
        return {"rule_id": rule_id, "enabled": after.get("is_enabled", after.get("is_active")), "before": before, "after": after}
    except Exception:
        if commit:
            db.rollback()
        raise


def _updated_rule_row(db: Session, rule_id: str) -> dict:
    from bookflow_core.services.super_admin_ai_rules import ai_rule_rows

    for item in ai_rule_rows(db):
        if item.get("id") == rule_id:
            return item
    return {"id": rule_id}


def update_governance_rule_config(
    db: Session,
    rule_id: str,
    *,
    payload: dict,
    reviewer: str = "super_admin",
    commit: bool = True,
) -> dict:
    if not rule_id or "-" not in rule_id:
        raise ValidationError("Invalid rule id.", details={"rule_id": rule_id})
    prefix, raw_key = rule_id.split("-", 1)
    payload = payload or {}
    try:
        if prefix == "borrow":
            parts = raw_key.rsplit("-", 1)
            if len(parts) != 2:
                raise ValidationError("Invalid borrow rule id.", details={"rule_id": rule_id})
            row = update_borrow_rule(
                db,
                reader_type_code=parts[0],
                circulation_type=parts[1],
                max_borrow_count=payload.get("max_borrow_count"),
                borrow_days=payload.get("borrow_days"),
                max_renewals=payload.get("max_renewals"),
                actor_id=reviewer,
                commit=False,
            )
            row.is_active = bool(payload.get("is_active", row.is_active))
        elif prefix == "system":
            update_system_setting(
                db,
                raw_key,
                value=str(payload.get("setting_value") if payload.get("setting_value") is not None else payload.get("value", "")),
                value_type=str(payload.get("value_type") or "string"),
                description=str(payload.get("description") or ""),
                actor_id=reviewer,
                commit=False,
            )
        elif prefix == "policy" and raw_key == "active":
            update_circulation_policy(
                db,
                hot_borrow_90d_threshold=payload.get("hot_borrow_90d_threshold"),
                hot_reserve_90d_threshold=payload.get("hot_reserve_90d_threshold"),
                cold_borrow_365d_threshold=payload.get("cold_borrow_365d_threshold"),
                cold_days_since_last_borrow_threshold=payload.get("cold_days_since_last_borrow_threshold"),
                actor_id=reviewer,
                commit=False,
            )
        else:
            raise BusinessRuleError("This rule can only be enabled or disabled, not edited.", details={"rule_id": rule_id})
        if commit:
            db.commit()
        return _updated_rule_row(db, rule_id)
    except Exception:
        if commit:
            db.rollback()
        raise


def create_super_admin_rule(
    db: Session,
    *,
    payload: dict,
    reviewer: str = "super_admin",
    commit: bool = True,
) -> dict:
    rule_type = str(payload.get("rule_type") or payload.get("type") or "system_builtin")
    if rule_type not in {"system_builtin", "notification_rule"}:
        raise BusinessRuleError("Only system or notification rules can be created here.", details={"rule_type": rule_type})
    key = str(payload.get("setting_key") or payload.get("key") or "").strip()
    if not key:
        raise ValidationError("Rule key is required.")
    value = str(payload.get("setting_value") if payload.get("setting_value") is not None else payload.get("value", ""))
    description = str(payload.get("description") or payload.get("title") or key)
    value_type = str(payload.get("value_type") or "string")
    try:
        row = update_system_setting(
            db,
            key,
            value=value,
            value_type=value_type,
            description=description,
            actor_id=reviewer,
            commit=False,
        )
        if commit:
            db.commit()
            db.refresh(row)
        return _updated_rule_row(db, f"system-{key}")
    except Exception:
        if commit:
            db.rollback()
        raise


def _export_rows(db: Session, export_type: str, filters: dict | None = None) -> list[dict]:
    filters = filters or {}
    limit = int(filters.get("limit") or 1000)
    limit = max(1, min(limit, 5000))
    stmt = select(AuditEvent)
    actor_id = str(filters.get("actor_id") or "").strip()
    result = str(filters.get("result") or "").strip()
    start = _date_bound(str(filters.get("date_from") or ""))
    end = _date_bound(str(filters.get("date_to") or ""), end=True)
    if actor_id:
        stmt = stmt.where(AuditEvent.actor_code == actor_id)
    if result:
        stmt = stmt.where(AuditEvent.result == result)
    if start:
        stmt = stmt.where(AuditEvent.created_at >= start)
    if end:
        stmt = stmt.where(AuditEvent.created_at <= end)
    stmt = stmt.order_by(AuditEvent.id.desc()).limit(limit)
    rows = db.scalars(stmt).all()
    if export_type in {"risk", "high_risk"}:
        data = [audit_event_to_dict(row) for row in rows]
        data = [row for row in data if row.get("riskLevel") in {"medium", "high", "critical", "forbidden"}]
    else:
        data = [audit_event_to_dict(row) for row in rows]
    risk_level = str(filters.get("risk_level") or "").strip()
    event_type = str(filters.get("event_type") or "").strip().lower()
    keyword = str(filters.get("keyword") or "").strip().lower()
    if risk_level:
        data = [row for row in data if row.get("riskLevel") == risk_level]
    if event_type:
        data = [row for row in data if event_type in str(row.get("action") or row.get("eventType") or "").lower()]
    if keyword:
        data = [
            row for row in data
            if keyword in " ".join(str(row.get(key) or "").lower() for key in ("actor_id", "action", "eventTypeLabel", "target_table", "target_id", "result", "resultLabel"))
        ]
    return data


def _write_export_file(export_code: str, rows: list[dict], export_format: str = "csv") -> tuple[Path, str]:
    export_dir = _project_root() / "artifacts" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    suffix = "json" if export_format == "json" else "csv"
    path = export_dir / f"{export_code}.{suffix}"
    if suffix == "json":
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    else:
        fieldnames = [
            "id",
            "created_at",
            "actor_id",
            "actor_type",
            "action",
            "eventTypeLabel",
            "target_table",
            "target_id",
            "result",
            "riskLevel",
            "riskLabel",
        ]
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, digest


def export_job_to_dict(row: ExportJob) -> dict:
    return {
        "export_code": row.export_code,
        "export_type": row.export_type,
        "template_name": row.template_name,
        "requester_admin_id": row.requester_admin_id,
        "status": row.status,
        "filter": _json(row.filter_json),
        "file_path": row.file_path,
        "file_hash": row.file_hash,
        "started_at": row.started_at,
        "finished_at": row.finished_at,
        "created_at": row.created_at,
    }


def create_audit_export_job(
    db: Session,
    *,
    export_type: str = "monthly",
    template_name: str = "审计摘要导出",
    export_format: str = "csv",
    filters: dict | None = None,
    reviewer: str = "super_admin",
    commit: bool = True,
) -> dict:
    if export_format not in {"csv", "json"}:
        raise ValidationError("Unsupported export format.", details={"export_format": export_format})
    try:
        export_code = _utc_code("EXP")
        started = now()
        rows = _export_rows(db, export_type, filters)
        file_path, file_hash = _write_export_file(export_code, rows, export_format)
        job = ExportJob(
            export_code=export_code,
            export_type=export_type,
            template_name=template_name,
            requester_admin_id=_admin_id_by_code(db, reviewer),
            status="success",
            filter_json=as_json(filters or {"limit": 1000}),
            file_path=str(file_path.relative_to(_project_root())),
            file_hash=file_hash,
            started_at=started,
            finished_at=now(),
            created_at=started,
        )
        db.add(job)
        write_audit(
            db,
            actor_type="super_admin",
            actor_id=reviewer,
            action="audit_export",
            target_table="export_jobs",
            target_id=export_code,
            detail={"export_type": export_type, "format": export_format, "row_count": len(rows), "file_hash": file_hash},
        )
        if commit:
            db.commit()
            db.refresh(job)
        return {"job": export_job_to_dict(job), "row_count": len(rows)}
    except Exception:
        if commit:
            db.rollback()
        raise


def get_export_job(db: Session, export_code: str) -> ExportJob:
    row = db.scalar(select(ExportJob).where(ExportJob.export_code == export_code))
    if not row:
        raise NotFoundError("Export job not found.", details={"export_code": export_code})
    return row
