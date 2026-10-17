from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from bookflow_core.api.deps import require_super_admin
from bookflow_core.core.database import get_db
from bookflow_core.core.exceptions import NotFoundError
from bookflow_core.schemas import CreateAdminRequest, ResetAdminPasswordRequest, SetAdminStatusRequest, UpdateAdminRequest
from bookflow_core.services.admin_service import (
    admin_to_dict,
    create_admin,
    get_admin,
    list_admin_events,
    list_admins,
    reset_admin_password,
    set_admin_status,
    update_admin,
)
from bookflow_core.services.governance_action_service import (
    create_audit_export_job,
    create_super_admin_rule,
    get_export_job,
    toggle_rule,
    update_governance_rule_config,
)
from bookflow_core.services.super_admin_service import (
    ai_rule_management,
    audit_events,
    governance_overview,
)

router = APIRouter(prefix="/super-admin", tags=["super-admin"])


def _actor_code(current_admin) -> str:
    return getattr(current_admin, "admin_code", None) or "super_admin"


@router.get("/overview")
def governance(db: Session = Depends(get_db), current_admin=Depends(require_super_admin)):
    return {"success": True, "data": governance_overview(db), "message": None}


@router.get("/admins")
def super_admins(is_super_admin: bool | None = None, status: str | None = None, keyword: str | None = None, limit: int = 50, offset: int = 0, db: Session = Depends(get_db), current_admin=Depends(require_super_admin)):
    return {"success": True, "data": list_admins(db, is_super_admin=is_super_admin, status=status, keyword=keyword, limit=limit, offset=offset), "message": None}


@router.post("/admins")
def create_super_admin_account(req: CreateAdminRequest, db: Session = Depends(get_db), current_admin=Depends(require_super_admin)):
    admin = create_admin(db, **req.model_dump(), actor_id=current_admin.admin_code, actor_admin_id=current_admin.id)
    return {"success": True, "data": admin_to_dict(admin), "message": "管理员已创建"}


@router.get("/admins/login-events")
def super_admin_login_events(admin_code: str | None = None, event_type: str | None = None, limit: int = 50, offset: int = 0, db: Session = Depends(get_db), current_admin=Depends(require_super_admin)):
    return {"success": True, "data": list_admin_events(db, admin_code=admin_code, event_type=event_type, limit=limit, offset=offset), "message": None}


@router.get("/admins/{admin_code}")
def super_admin_detail(admin_code: str, db: Session = Depends(get_db), current_admin=Depends(require_super_admin)):
    return {"success": True, "data": admin_to_dict(get_admin(db, admin_code)), "message": None}


@router.put("/admins/{admin_code}")
def update_super_admin_account(admin_code: str, req: UpdateAdminRequest, db: Session = Depends(get_db), current_admin=Depends(require_super_admin)):
    admin = update_admin(db, admin_code=admin_code, **req.model_dump(exclude_none=True), actor_id=current_admin.admin_code)
    return {"success": True, "data": admin_to_dict(admin), "message": "管理员已更新"}


@router.post("/admins/{admin_code}/status")
def set_super_admin_status(admin_code: str, req: SetAdminStatusRequest, db: Session = Depends(get_db), current_admin=Depends(require_super_admin)):
    admin = set_admin_status(db, admin_code=admin_code, status=req.status, actor_id=current_admin.admin_code)
    return {"success": True, "data": admin_to_dict(admin), "message": "管理员状态已更新"}


@router.post("/admins/{admin_code}/reset-password")
def reset_super_admin_password(admin_code: str, req: ResetAdminPasswordRequest, db: Session = Depends(get_db), current_admin=Depends(require_super_admin)):
    admin = reset_admin_password(db, admin_code=admin_code, password=req.password, actor_id=current_admin.admin_code)
    return {"success": True, "data": admin_to_dict(admin), "message": "密码已重置"}


@router.get("/ai-rules")
def rule_list(limit: int = 100, offset: int = 0, rule_type: str | None = None, status: str | None = None, keyword: str | None = None, db: Session = Depends(get_db), current_admin=Depends(require_super_admin)):
    data = ai_rule_management(db, limit=200, offset=0)
    items = data["items"]
    if rule_type:
        items = [row for row in items if row.get("rule_type") == rule_type]
    if status:
        items = [row for row in items if row.get("status") == status]
    if keyword:
        text = keyword.strip().lower()
        items = [
            row for row in items
            if text in " ".join(str(row.get(key) or "").lower() for key in ("id", "title", "description", "type", "category"))
        ]
    total = len(items)
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    return {"success": True, "data": {**data, "items": items[offset: offset + limit], "total": total, "limit": limit, "offset": offset}, "message": None}


@router.post("/ai-rules")
def create_rule(body: dict | None = None, db: Session = Depends(get_db), current_admin=Depends(require_super_admin)):
    result = create_super_admin_rule(db, payload=body or {}, reviewer=_actor_code(current_admin))
    return {"success": True, "data": result, "message": "规则已创建"}


@router.post("/ai-rules/{rule_id}/toggle")
def toggle_ai_rule(rule_id: str, body: dict | None = None, db: Session = Depends(get_db), current_admin=Depends(require_super_admin)):
    body = body or {}
    enabled = body.get("enabled")
    result = toggle_rule(db, rule_id, enabled=None if enabled is None else bool(enabled), reviewer=_actor_code(current_admin))
    return {"success": True, "data": result, "message": "规则状态已更新"}


@router.put("/ai-rules/{rule_id}")
def update_rule(rule_id: str, body: dict | None = None, db: Session = Depends(get_db), current_admin=Depends(require_super_admin)):
    result = update_governance_rule_config(db, rule_id, payload=body or {}, reviewer=_actor_code(current_admin))
    return {"success": True, "data": result, "message": "规则已更新"}


@router.get("/audit-security/events")
def events(limit: int = 50, offset: int = 0, actor_id: str | None = None, result: str | None = None, risk_level: str | None = None, date_from: str | None = None, date_to: str | None = None, keyword: str | None = None, module: str | None = None, db: Session = Depends(get_db), current_admin=Depends(require_super_admin)):
    return {"success": True, "data": audit_events(db, limit=limit, offset=offset, actor_id=actor_id, result=result, risk_level=risk_level, date_from=date_from, date_to=date_to, keyword=keyword, module=module), "message": None}


@router.post("/audit-security/export")
def create_export(body: dict | None = None, db: Session = Depends(get_db), current_admin=Depends(require_super_admin)):
    body = body or {}
    result = create_audit_export_job(
        db,
        export_type=str(body.get("export_type") or body.get("type") or "admin_audit"),
        template_name=str(body.get("template_name") or body.get("template") or "管理员审计记录"),
        export_format=str(body.get("format") or "csv"),
        filters=body.get("filters") if isinstance(body.get("filters"), dict) else {"limit": int(body.get("limit") or 1000)},
        reviewer=_actor_code(current_admin),
    )
    return {"success": True, "data": result, "message": "审计记录已导出"}


@router.get("/audit-security/export-jobs/{export_code}")
def export_job(export_code: str, db: Session = Depends(get_db), current_admin=Depends(require_super_admin)):
    from bookflow_core.services.governance_action_service import export_job_to_dict

    job = get_export_job(db, export_code)
    return {"success": True, "data": export_job_to_dict(job), "message": None}


@router.get("/audit-security/export-jobs/{export_code}/download")
def download_export(export_code: str, db: Session = Depends(get_db), current_admin=Depends(require_super_admin)):
    job = get_export_job(db, export_code)
    if not job.file_path:
        raise NotFoundError("Export file path is empty.", details={"export_code": export_code})
    root = Path(__file__).resolve().parents[3]
    path = (root / job.file_path).resolve()
    if not path.exists() or root not in path.parents:
        raise NotFoundError("Export file not found.", details={"export_code": export_code})
    return FileResponse(path, filename=path.name, media_type="text/csv" if path.suffix == ".csv" else "application/json")
