from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from bookflow_core.core.exceptions import NotFoundError, ValidationError, BusinessRuleError
from bookflow_core.models import CirculationRule, SystemSetting, CirculationPolicy
from bookflow_core.services.common import create_snapshot, write_audit

VALID_READER_TYPES = {"child", "teen", "adult", "senior", "institution"}
VALID_CIRCULATION_TYPES = {"hot", "normal", "cold"}
VALID_VALUE_TYPES = {"int", "string", "bool", "float"}


def list_borrow_rules(db: Session) -> list[CirculationRule]:
    return db.scalars(select(CirculationRule).where(CirculationRule.is_active == True).order_by(CirculationRule.reader_type_code, CirculationRule.circulation_type)).all()


def get_borrow_rule(db: Session, reader_type_code: str, circulation_type: str) -> CirculationRule:
    row = db.scalar(select(CirculationRule).where(CirculationRule.reader_type_code == reader_type_code, CirculationRule.circulation_type == circulation_type))
    if not row:
        raise NotFoundError("Borrow rule not found.", details={"reader_type_code": reader_type_code, "circulation_type": circulation_type})
    return row


def update_borrow_rule(db: Session, *, reader_type_code: str, circulation_type: str, max_borrow_count: int | None = None, borrow_days: int | None = None, max_renewals: int | None = None, actor_type: str = "super_admin", actor_id: str = "super_admin", commit: bool = True) -> CirculationRule:
    if reader_type_code not in VALID_READER_TYPES:
        raise ValidationError("Invalid reader_type_code.", details={"reader_type_code": reader_type_code})
    if circulation_type not in VALID_CIRCULATION_TYPES:
        raise ValidationError("Invalid circulation_type.", details={"circulation_type": circulation_type})
    try:
        row = get_borrow_rule(db, reader_type_code, circulation_type)
        before = {"max_borrow_count": row.max_borrow_count, "borrow_days": row.borrow_days, "max_renewals": row.max_renewals}
        if max_borrow_count is not None:
            if max_borrow_count < 1:
                raise BusinessRuleError("max_borrow_count must be positive.")
            row.max_borrow_count = max_borrow_count
        if borrow_days is not None:
            if borrow_days < 1:
                raise BusinessRuleError("borrow_days must be positive.")
            row.borrow_days = borrow_days
        if max_renewals is not None:
            if max_renewals < 0:
                raise BusinessRuleError("max_renewals cannot be negative.")
            row.max_renewals = max_renewals
        after = {"max_borrow_count": row.max_borrow_count, "borrow_days": row.borrow_days, "max_renewals": row.max_renewals}
        create_snapshot(db, action_type="update_borrow_rule", target_table="circulation_rules", target_id=f"{reader_type_code}:{circulation_type}", before=before, after=after, actor_type=actor_type, actor_id=actor_id, can_rollback=True)
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="update_borrow_rule", target_table="circulation_rules", target_id=f"{reader_type_code}:{circulation_type}", detail={"before": before, "after": after})
        if commit:
            db.commit()
            db.refresh(row)
        return row
    except Exception:
        if commit:
            db.rollback()
        raise


def list_system_settings(db: Session) -> list[SystemSetting]:
    return db.scalars(select(SystemSetting).where(SystemSetting.is_active == True).order_by(SystemSetting.setting_key)).all()


def update_system_setting(db: Session, key: str, *, value: str, value_type: str | None = None, description: str | None = None, actor_type: str = "super_admin", actor_id: str = "super_admin", commit: bool = True) -> SystemSetting:
    if value_type is not None and value_type not in VALID_VALUE_TYPES:
        raise ValidationError("Invalid value_type.", details={"value_type": value_type})
    try:
        row = db.scalar(select(SystemSetting).where(SystemSetting.setting_key == key))
        if not row:
            row = SystemSetting(setting_key=key, setting_value=value, value_type=value_type or "string", description=description or "", is_active=True)
            db.add(row)
            before = None
        else:
            before = {"value": row.setting_value, "value_type": row.value_type, "description": row.description}
            row.setting_value = value
            if value_type is not None:
                row.value_type = value_type
            if description is not None:
                row.description = description
            row.is_active = True
        after = {"value": row.setting_value, "value_type": row.value_type, "description": row.description}
        create_snapshot(db, action_type="update_system_setting", target_table="system_settings", target_id=key, before=before or {}, after=after, actor_type=actor_type, actor_id=actor_id, can_rollback=True)
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="update_system_setting", target_table="system_settings", target_id=key, detail={"before": before, "after": after})
        if commit:
            db.commit()
            db.refresh(row)
        return row
    except Exception:
        if commit:
            db.rollback()
        raise


def get_active_policy(db: Session) -> CirculationPolicy:
    row = db.scalar(select(CirculationPolicy).where(CirculationPolicy.is_active == True).order_by(CirculationPolicy.id.desc()))
    if not row:
        raise NotFoundError("No active circulation policy found.")
    return row


def update_circulation_policy(db: Session, *, hot_borrow_90d_threshold: int | None = None, hot_reserve_90d_threshold: int | None = None, cold_borrow_365d_threshold: int | None = None, cold_days_since_last_borrow_threshold: int | None = None, actor_type: str = "super_admin", actor_id: str = "super_admin", commit: bool = True) -> CirculationPolicy:
    try:
        row = get_active_policy(db)
        before = {
            "hot_borrow_90d_threshold": row.hot_borrow_90d_threshold,
            "hot_reserve_90d_threshold": row.hot_reserve_90d_threshold,
            "cold_borrow_365d_threshold": row.cold_borrow_365d_threshold,
            "cold_days_since_last_borrow_threshold": row.cold_days_since_last_borrow_threshold,
        }
        for name, value in {
            "hot_borrow_90d_threshold": hot_borrow_90d_threshold,
            "hot_reserve_90d_threshold": hot_reserve_90d_threshold,
            "cold_borrow_365d_threshold": cold_borrow_365d_threshold,
            "cold_days_since_last_borrow_threshold": cold_days_since_last_borrow_threshold,
        }.items():
            if value is not None:
                if value < 0:
                    raise BusinessRuleError("Policy threshold cannot be negative.", details={"field": name})
                setattr(row, name, value)
        after = {
            "hot_borrow_90d_threshold": row.hot_borrow_90d_threshold,
            "hot_reserve_90d_threshold": row.hot_reserve_90d_threshold,
            "cold_borrow_365d_threshold": row.cold_borrow_365d_threshold,
            "cold_days_since_last_borrow_threshold": row.cold_days_since_last_borrow_threshold,
        }
        create_snapshot(db, action_type="update_circulation_policy", target_table="circulation_policies", target_id=str(row.id), before=before, after=after, actor_type=actor_type, actor_id=actor_id, can_rollback=True)
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="update_circulation_policy", target_table="circulation_policies", target_id=row.id, detail={"before": before, "after": after})
        if commit:
            db.commit()
            db.refresh(row)
        return row
    except Exception:
        if commit:
            db.rollback()
        raise


def rule_to_dict(row: CirculationRule) -> dict:
    return {"reader_type_code": row.reader_type_code, "reader_type_name": row.reader_type_name, "circulation_type": row.circulation_type, "max_borrow_count": row.max_borrow_count, "borrow_days": row.borrow_days, "max_renewals": row.max_renewals}


def system_setting_to_dict(row: SystemSetting) -> dict:
    return {"setting_key": row.setting_key, "setting_value": row.setting_value, "value_type": row.value_type, "description": row.description, "is_active": row.is_active}


def policy_to_dict(row: CirculationPolicy) -> dict:
    return {"hot_borrow_90d_threshold": row.hot_borrow_90d_threshold, "hot_reserve_90d_threshold": row.hot_reserve_90d_threshold, "cold_borrow_365d_threshold": row.cold_borrow_365d_threshold, "cold_days_since_last_borrow_threshold": row.cold_days_since_last_borrow_threshold, "is_active": row.is_active}


