from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from bookflow_core.core.exceptions import BusinessRuleError, NotFoundError
from bookflow_core.core.time import now
from bookflow_core.models import ActionSnapshot, AdminUser, AgentRun, AgentStep, BookCopy, AIApprovalRequest
from bookflow_core.services.catalog_service import update_copy_status
from bookflow_core.services.common import as_json, create_snapshot, write_audit, write_status_event


def _copy_snapshot(db: Session, copy_code: str) -> dict:
    copy = db.scalar(select(BookCopy).where(BookCopy.copy_code == copy_code))
    if not copy:
        raise NotFoundError("Copy not found.")
    return {
        "copy_code": copy.copy_code,
        "copy_status": copy.copy_status,
        "book_id": copy.book_id,
        "current_position_id": copy.current_position_id,
    }


def _admin_id_by_code(db: Session, admin_code: str) -> int | None:
    row = db.scalar(select(AdminUser).where(AdminUser.admin_code == str(admin_code)))
    return row.id if row else None


def rollback_snapshot(db: Session, snapshot_code: str, *, actor_type: str = "super_admin", actor_id: str = "super_admin", commit: bool = True) -> dict:
    try:
        snap = db.scalar(select(ActionSnapshot).where(ActionSnapshot.snapshot_code == snapshot_code))
        if not snap or not snap.can_rollback or snap.rolled_back:
            raise BusinessRuleError("Snapshot cannot be rolled back.")
        before = json.loads(snap.before_json or "{}")
        if snap.target_entity_type == "book_copies":
            copy = db.scalar(select(BookCopy).where(BookCopy.copy_code == before["copy_code"]))
            if not copy:
                raise NotFoundError("Target copy not found.")
            old_status = copy.copy_status
            copy.copy_status = before["copy_status"]
            if old_status != copy.copy_status:
                write_status_event(db, copy, old_status, copy.copy_status, "rollback_snapshot", actor_type, actor_id)
            copy.current_position_id = before.get("current_position_id")
            result = {"copy_code": copy.copy_code, "copy_status": copy.copy_status}
        elif snap.target_entity_type == "reservations":
            from datetime import date
            from bookflow_core.models import Reservation

            reservation = db.get(Reservation, int(snap.target_entity_id))
            if not reservation:
                raise NotFoundError("Target reservation not found.")
            reservation.status = before["status"]
            reservation.fulfilled_copy_id = before.get("fulfilled_copy_id")
            raw_reserved_until = before.get("reserved_until")
            reservation.reserved_until = date.fromisoformat(raw_reserved_until) if isinstance(raw_reserved_until, str) and raw_reserved_until else raw_reserved_until
            result = {"reservation_id": reservation.id, "status": reservation.status}
        elif snap.target_entity_type == "notifications":
            from bookflow_core.models import Notification

            notification = db.get(Notification, int(snap.target_entity_id))
            if not notification:
                raise NotFoundError("Target notification not found.")
            notification.status = before["status"]
            notification.title = before.get("title", notification.title)
            notification.content = before.get("content", notification.content)
            result = {"notification_id": notification.id, "status": notification.status}
        elif snap.target_entity_type in {"circulation_rules", "circulation_rules"}:
            from bookflow_core.models import CirculationRule

            rule = db.get(CirculationRule, int(snap.target_entity_id))
            if not rule:
                raise NotFoundError("Target rule set not found.")
            rule.max_borrow_count = before["max_borrow_count"]
            rule.borrow_days = before["borrow_days"]
            rule.max_renewals = before["max_renewals"]
            result = {"circulation_rule_id": rule.id, "borrow_days": rule.borrow_days}
        elif snap.target_entity_type in {"system_settings", "system_settings"}:
            from bookflow_core.models import SystemSetting

            row = db.get(SystemSetting, int(snap.target_entity_id))
            if not row:
                raise NotFoundError("Target system rule not found.")
            row.setting_value = before["value"]
            row.value_type = before["value_type"]
            row.description = before.get("description", row.description)
            result = {"system_setting_id": row.id, "value": row.setting_value}
        elif snap.target_entity_type == "circulation_policies":
            from bookflow_core.models import CirculationPolicy

            row = db.get(CirculationPolicy, int(snap.target_entity_id))
            if not row:
                raise NotFoundError("Target circulation policy not found.")
            for field in [
                "hot_borrow_90d_threshold",
                "hot_reserve_90d_threshold",
                "cold_borrow_365d_threshold",
                "cold_days_since_last_borrow_threshold",
            ]:
                setattr(row, field, before[field])
            result = {"circulation_policy_id": row.id, "hot_borrow_90d_threshold": row.hot_borrow_90d_threshold}
        else:
            raise BusinessRuleError("Unsupported snapshot target table.", details={"target_table": snap.target_entity_type})
        snap.rolled_back = True
        write_audit(
            db,
            actor_type=actor_type,
            actor_id=actor_id,
            action="rollback_snapshot",
            target_table=snap.target_entity_type,
            target_id=snap.target_entity_id,
            detail={"snapshot_code": snapshot_code, "result": result},
        )
        if commit:
            db.commit()
        out = {"status": "rolled_back", "snapshot_code": snapshot_code, "data": result}
        if snap.target_entity_type == "book_copies":
            out["copy_code"] = result["copy_code"]
            out["copy_status"] = result["copy_status"]
        return out
    except Exception:
        if commit:
            db.rollback()
        raise


def approve_approval(db: Session, approval_code: str, *, reviewer: str = "super_admin", commit: bool = True) -> dict:
    try:
        approval = db.scalar(select(AIApprovalRequest).where(AIApprovalRequest.approval_code == approval_code))
        if not approval:
            raise NotFoundError("AI approval request not found.", details={"approval_code": approval_code})
        if approval.status != "waiting":
            raise BusinessRuleError("AI approval request is not waiting for review.", details={"status": approval.status})
        approval.status = "approved"
        approval.reviewed_by_admin_id = _admin_id_by_code(db, reviewer)
        approval.reviewed_at = now()
        run = db.get(AgentRun, approval.run_id) if approval.run_id else None
        if run:
            run.status = "approved_waiting_execution"
            db.add(AgentStep(run_id=run.id, step_name="approve_approval", status="approved", detail_json=as_json({"approval_code": approval_code, "reviewer": reviewer})))
        write_audit(db, actor_type="super_admin", actor_id=reviewer, action="approve_ai_approval_request", target_table="ai_approval_requests", target_id=approval_code)
        if commit:
            db.commit()
        return {"status": "approved", "approval_code": approval_code}
    except Exception:
        if commit:
            db.rollback()
        raise


def reject_approval(db: Session, approval_code: str, *, reviewer: str = "super_admin", reason: str = "rejected", commit: bool = True) -> dict:
    try:
        approval = db.scalar(select(AIApprovalRequest).where(AIApprovalRequest.approval_code == approval_code))
        if not approval:
            raise NotFoundError("AI approval request not found.", details={"approval_code": approval_code})
        if approval.status != "waiting":
            raise BusinessRuleError("AI approval request is not waiting for review.", details={"status": approval.status})
        approval.status = "rejected"
        approval.reviewed_by_admin_id = _admin_id_by_code(db, reviewer)
        approval.reviewed_at = now()
        approval.decision_reason = reason
        run = db.get(AgentRun, approval.run_id) if approval.run_id else None
        if run:
            run.status = "rejected_by_super_admin"
            db.add(AgentStep(run_id=run.id, step_name="reject_approval", status="rejected", detail_json=as_json({"approval_code": approval_code, "reviewer": reviewer, "reason": reason})))
        write_audit(
            db,
            actor_type="super_admin",
            actor_id=reviewer,
            action="reject_ai_approval_request",
            target_table="ai_approval_requests",
            target_id=approval_code,
            result="rejected",
            detail={"reason": reason},
        )
        if commit:
            db.commit()
        return {"status": "rejected", "approval_code": approval_code}
    except Exception:
        if commit:
            db.rollback()
        raise


def execute_approved_approval(db: Session, approval_code: str, *, reviewer: str = "super_admin", commit: bool = True) -> dict:
    try:
        from bookflow_core.models import CirculationPolicy, CirculationRule, SystemSetting
        from bookflow_core.services.rule_service import update_borrow_rule, update_circulation_policy, update_system_setting

        approval = db.scalar(select(AIApprovalRequest).where(AIApprovalRequest.approval_code == approval_code))
        if not approval:
            raise NotFoundError("AI approval request not found.", details={"approval_code": approval_code})
        if approval.status != "approved":
            raise BusinessRuleError("Approval must be approved before execution.", details={"status": approval.status})
        payload = json.loads(approval.payload_json or "{}")
        if approval.requested_action == "ai_request_copy_status_change":
            before = _copy_snapshot(db, payload["copy_code"])
            copy = update_copy_status(
                db,
                payload["copy_code"],
                payload["new_status"],
                reason=payload.get("reason", "approved_ai_request_copy_status_change"),
                actor_type="super_admin",
                actor_id=reviewer,
                commit=False,
            )
            after = _copy_snapshot(db, copy.copy_code)
            create_snapshot(
                db,
                action_type="ai_request_copy_status_change",
                target_table="book_copies",
                target_id=copy.copy_code,
                before=before,
                after=after,
                actor_type="super_admin",
                actor_id=reviewer,
            )
            result = {"copy_code": copy.copy_code, "copy_status": copy.copy_status}
        elif approval.requested_action == "ai_request_rule_change":
            change_type = payload.get("change_type")
            if change_type == "borrow_rule":
                before_row = db.scalar(
                    select(CirculationRule).where(
                        CirculationRule.reader_type_code == payload["reader_type_code"],
                        CirculationRule.circulation_type == payload["circulation_type"],
                        CirculationRule.is_active == True,
                    )
                )
                before = {
                    "max_borrow_count": before_row.max_borrow_count,
                    "borrow_days": before_row.borrow_days,
                    "max_renewals": before_row.max_renewals,
                } if before_row else {}
                row = update_borrow_rule(
                    db,
                    reader_type_code=payload["reader_type_code"],
                    circulation_type=payload["circulation_type"],
                    max_borrow_count=payload.get("max_borrow_count"),
                    borrow_days=payload.get("borrow_days"),
                    max_renewals=payload.get("max_renewals"),
                    actor_type="super_admin",
                    actor_id=reviewer,
                    commit=False,
                )
                result = {
                    "reader_type_code": row.reader_type_code,
                    "circulation_type": row.circulation_type,
                    "borrow_days": row.borrow_days,
                    "max_borrow_count": row.max_borrow_count,
                    "max_renewals": row.max_renewals,
                }
                create_snapshot(db, action_type="ai_request_rule_change", target_table="circulation_rules", target_id=str(row.id), before=before, after=result, actor_type="super_admin", actor_id=reviewer)
            elif change_type == "system_setting":
                before_row = db.scalar(select(SystemSetting).where(SystemSetting.setting_key == payload["key"]))
                before = {"value": before_row.setting_value, "value_type": before_row.value_type, "description": before_row.description} if before_row else {}
                row = update_system_setting(
                    db,
                    payload["key"],
                    value=str(payload["value"]),
                    value_type=payload.get("value_type"),
                    description=payload.get("description"),
                    actor_type="super_admin",
                    actor_id=reviewer,
                    commit=False,
                )
                result = {"key": row.setting_key, "value": row.setting_value, "value_type": row.value_type}
                create_snapshot(
                    db,
                    action_type="ai_request_rule_change",
                    target_table="system_settings",
                    target_id=str(row.id),
                    before=before or {"value": "", "value_type": row.value_type, "description": ""},
                    after={"value": row.setting_value, "value_type": row.value_type, "description": row.description},
                    actor_type="super_admin",
                    actor_id=reviewer,
                    can_rollback=bool(before),
                )
            elif change_type == "circulation_policy":
                before_row = db.scalar(select(CirculationPolicy).where(CirculationPolicy.is_active == True).order_by(CirculationPolicy.id.desc()))
                before = {
                    "hot_borrow_90d_threshold": before_row.hot_borrow_90d_threshold,
                    "hot_reserve_90d_threshold": before_row.hot_reserve_90d_threshold,
                    "cold_borrow_365d_threshold": before_row.cold_borrow_365d_threshold,
                    "cold_days_since_last_borrow_threshold": before_row.cold_days_since_last_borrow_threshold,
                }
                row = update_circulation_policy(db, actor_type="super_admin", actor_id=reviewer, commit=False, **payload.get("fields", {}))
                result = {
                    "hot_borrow_90d_threshold": row.hot_borrow_90d_threshold,
                    "hot_reserve_90d_threshold": row.hot_reserve_90d_threshold,
                    "cold_borrow_365d_threshold": row.cold_borrow_365d_threshold,
                    "cold_days_since_last_borrow_threshold": row.cold_days_since_last_borrow_threshold,
                }
                create_snapshot(db, action_type="ai_request_rule_change", target_table="circulation_policies", target_id=str(row.id), before=before, after=result, actor_type="super_admin", actor_id=reviewer)
            else:
                raise BusinessRuleError("Unsupported rule change type.", details={"change_type": change_type})
        else:
            raise BusinessRuleError("Unsupported approved action.", details={"requested_action": approval.requested_action})
        approval.status = "executed"
        run = db.get(AgentRun, approval.run_id) if approval.run_id else None
        if run:
            run.status = "success"
            run.output_json = as_json(result)
            db.add(AgentStep(run_id=run.id, step_name="execute_approved_approval", status="success", detail_json=as_json(result)))
        write_audit(db, actor_type="super_admin", actor_id=reviewer, action="execute_approved_approval", target_table="ai_approval_requests", target_id=approval_code, detail=result)
        if commit:
            db.commit()
        return {"status": "executed", "approval_code": approval_code, "data": result}
    except Exception:
        if commit:
            db.rollback()
        raise


def list_approvals(db: Session, *, status: str | None = None, limit: int = 50) -> dict:
    stmt = select(AIApprovalRequest)
    if status:
        stmt = stmt.where(AIApprovalRequest.status == status)
    rows = db.scalars(stmt.order_by(AIApprovalRequest.id.desc()).limit(limit)).all()
    return {
        "items": [
            {
                "approval_code": row.approval_code,
                "requested_action": row.requested_action,
                "status": row.status,
                "requested_by_agent_run_id": row.requested_by_agent_run_id,
                "reviewed_by_admin_id": row.reviewed_by_admin_id,
            }
            for row in rows
        ],
        "total": len(rows),
        "limit": limit,
    }


def list_action_snapshots(db: Session, *, target_table: str | None = None, limit: int = 50) -> dict:
    stmt = select(ActionSnapshot)
    if target_table:
        stmt = stmt.where(ActionSnapshot.target_entity_type == target_table)
    rows = db.scalars(stmt.order_by(ActionSnapshot.id.desc()).limit(limit)).all()
    return {
        "items": [
            {
                "snapshot_code": row.snapshot_code,
                "action_type": row.action_type,
                "target_entity_type": row.target_entity_type,
                "target_entity_id": row.target_entity_id,
                "can_rollback": row.can_rollback,
                "rolled_back": row.rolled_back,
            }
            for row in rows
        ],
        "total": len(rows),
        "limit": limit,
    }


