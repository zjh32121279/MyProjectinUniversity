from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from bookflow_core.api.deps import require_permission
from bookflow_core.core.database import get_db
from bookflow_core.services.location_service import (
    EMPTY_MESSAGE,
    apply_bookflow_default_layout,
    batch_save_layout,
    create_shelf,
    create_zone,
    delete_shelf,
    delete_zone,
    list_positions,
    list_shelves,
    list_zones,
    location_tree,
    update_shelf,
    update_zone,
)

router = APIRouter(prefix="/locations", tags=["locations"])


def _response(data: dict):
    return {"success": True, "data": data, "message": EMPTY_MESSAGE if data.get("empty_state") else None}


@router.get("/zones")
def zones(keyword: str | None = None, limit: int = Query(20, le=200), offset: int = 0, db: Session = Depends(get_db)):
    return _response(list_zones(db, keyword=keyword, limit=limit, offset=offset))


@router.post("/zones")
def add_zone(body: dict, db: Session = Depends(get_db), current_admin=Depends(require_permission("settings:write"))):
    row = create_zone(db, zone_code=body["zone_code"], zone_name=body["zone_name"], floor=body.get("floor", ""), area_sqm=body.get("area_sqm", 0), main_use=body.get("main_use", ""), is_public=body.get("is_public", True), sort_order=body.get("sort_order", 0), pos_x=body.get("pos_x", 0), pos_y=body.get("pos_y", 0), width=body.get("width", 200), height=body.get("height", 150), color=body.get("color", "#e8f4f8"), actor_id=current_admin.admin_code)
    return {"success": True, "data": {"id": row.id, "zone_code": row.zone_code, "zone_name": row.zone_name}, "message": None}


@router.put("/zones/{zone_id}")
def edit_zone(zone_id: int, body: dict, db: Session = Depends(get_db), current_admin=Depends(require_permission("settings:write"))):
    row = update_zone(db, zone_id=zone_id, **{k: v for k, v in body.items() if v is not None}, actor_id=current_admin.admin_code)
    return {"success": True, "data": {"id": row.id, "zone_code": row.zone_code, "zone_name": row.zone_name}, "message": None}


@router.delete("/zones/{zone_id}")
def remove_zone(zone_id: int, db: Session = Depends(get_db), current_admin=Depends(require_permission("settings:write"))):
    delete_zone(db, zone_id=zone_id, actor_id=current_admin.admin_code)
    return {"success": True, "data": None, "message": None}


@router.get("/shelves")
def shelves(
    keyword: str | None = None,
    zone_id: int | None = None,
    zone_code: str | None = None,
    limit: int = Query(20, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    return _response(list_shelves(db, keyword=keyword, zone_id=zone_id, zone_code=zone_code, limit=limit, offset=offset))


@router.post("/shelves")
def add_shelf(body: dict, db: Session = Depends(get_db), current_admin=Depends(require_permission("settings:write"))):
    row = create_shelf(db, shelf_code=body["shelf_code"], zone_id=body["zone_id"], floor=body.get("floor", ""), shelf_index=body.get("shelf_index", 0), layer_count=body.get("layer_count", 4), side_rule=body.get("side_rule", "both"), shelf_type=body.get("shelf_type", "formal"), pos_x=body.get("pos_x", 0), pos_y=body.get("pos_y", 0), width=body.get("width", 60), height=body.get("height", 40), rotation=body.get("rotation", 0), actor_id=current_admin.admin_code)
    return {"success": True, "data": {"id": row.id, "shelf_code": row.shelf_code, "zone_code": row.zone_code}, "message": None}


@router.put("/shelves/{shelf_id}")
def edit_shelf(shelf_id: int, body: dict, db: Session = Depends(get_db), current_admin=Depends(require_permission("settings:write"))):
    row = update_shelf(db, shelf_id=shelf_id, **{k: v for k, v in body.items() if v is not None}, actor_id=current_admin.admin_code)
    return {"success": True, "data": {"id": row.id, "shelf_code": row.shelf_code}, "message": None}


@router.delete("/shelves/{shelf_id}")
def remove_shelf(shelf_id: int, db: Session = Depends(get_db), current_admin=Depends(require_permission("settings:write"))):
    delete_shelf(db, shelf_id=shelf_id, actor_id=current_admin.admin_code)
    return {"success": True, "data": None, "message": None}


@router.get("/positions")
def positions(
    keyword: str | None = None,
    shelf_id: int | None = None,
    shelf_code: str | None = None,
    limit: int = Query(20, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    return _response(list_positions(db, keyword=keyword, shelf_id=shelf_id, shelf_code=shelf_code, limit=limit, offset=offset))


@router.get("/tree")
def tree(db: Session = Depends(get_db)):
    return _response(location_tree(db))


@router.post("/layout")
def save_layout(body: dict, db: Session = Depends(get_db), current_admin=Depends(require_permission("settings:write"))):
    result = batch_save_layout(db, zones=body.get("zones", []), shelves=body.get("shelves", []), actor_id=current_admin.admin_code)
    return {"success": True, "data": result, "message": None}


@router.post("/layout/bookflow-default")
def apply_default_layout(db: Session = Depends(get_db), current_admin=Depends(require_permission("settings:write"))):
    result = apply_bookflow_default_layout(db, actor_id=current_admin.admin_code)
    return {"success": True, "data": result, "message": None}
