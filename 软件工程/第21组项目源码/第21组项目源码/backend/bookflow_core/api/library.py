from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from bookflow_core.api.deps import require_permission
from bookflow_core.core.database import get_db
from bookflow_core.schemas import (
    BatchUpdateSettingsRequest,
    UpdateLibraryProfileRequest,
    UpdateLibrarySpaceConfigRequest,
)
from bookflow_core.services.dashboard_service import library_profile
from bookflow_core.services.library_settings_service import (
    batch_update_system_settings,
    update_library_profile,
    update_library_space_config,
)
router = APIRouter(prefix="/library", tags=["library"])

@router.get("/profile")
def get_profile(db: Session = Depends(get_db), current_admin=Depends(require_permission("dashboard:read"))):
    return {"success": True, "data": library_profile(db), "message": None}


@router.put("/profile")
def put_profile(
    req: UpdateLibraryProfileRequest,
    db: Session = Depends(get_db),
    current_admin=Depends(require_permission("library:write")),
):
    profile = update_library_profile(
        db,
        library_name=req.library_name,
        library_type=req.library_type,
        service_population=req.service_population,
        building_area_sqm=req.building_area_sqm,
        open_floors=req.open_floors,
        actor_id=current_admin.admin_code,
    )
    return {"success": True, "data": library_profile(db), "message": "图书馆基础信息已更新"}


@router.put("/space-config")
def put_space_config(
    req: UpdateLibrarySpaceConfigRequest,
    db: Session = Depends(get_db),
    current_admin=Depends(require_permission("library:write")),
):
    profile = update_library_space_config(
        db,
        zone_count=req.zone_count,
        shelf_count=req.shelf_count,
        reservation_shelf_count=req.reservation_shelf_count,
        turnover_shelf_count=req.turnover_shelf_count,
        actor_id=current_admin.admin_code,
    )
    return {"success": True, "data": library_profile(db), "message": "馆内空间配置已更新"}


@router.put("/settings")
def put_settings(
    req: BatchUpdateSettingsRequest,
    db: Session = Depends(get_db),
    current_admin=Depends(require_permission("settings:write")),
):
    results = batch_update_system_settings(
        db,
        settings=req.settings,
        actor_id=current_admin.admin_code,
    )
    return {"success": True, "data": {"updated": results}, "message": "系统运行设置已更新"}
