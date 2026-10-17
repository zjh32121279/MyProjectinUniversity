from __future__ import annotations

from sqlalchemy import or_, select, func
from sqlalchemy.orm import Session

from bookflow_core.models import Shelf, ShelfPosition, LibraryZone

EMPTY_MESSAGE = "数据库暂无可用数据，请先导入或迁移业务数据。"


def _page_response(items: list[dict], total: int, limit: int, offset: int) -> dict:
    data = {"items": items, "total": int(total), "limit": limit, "offset": offset}
    if total == 0:
        data["empty_state"] = True
    return data


def _side_flags(side_rule: str | None) -> tuple[bool, bool]:
    rule = side_rule or ""
    return ("左" in rule or "left" in rule.lower()), ("右" in rule or "right" in rule.lower())


def _shelf_code_from_position(position_code: str | None) -> str | None:
    if not position_code:
        return None
    parts = position_code.rsplit("-", 2)
    return parts[0] if len(parts) == 3 else None


def zone_to_dict(row: LibraryZone) -> dict:
    """Serialize the current real-book-data location schema.

    The API keeps a few legacy aliases (name, floor_label, purpose) so the
    existing frontends do not crash while the database uses the strengthened
    real-data fields (zone_name, floor, main_use).
    """
    return {
        "id": row.id,
        "zone_code": row.zone_code,
        "zone_name": row.zone_name,
        "name": row.zone_name,
        "floor": row.floor,
        "floor_label": row.floor,
        "area_sqm": row.area_sqm,
        "main_use": row.main_use,
        "purpose": row.main_use,
        "is_public": row.is_public,
        "sort_order": row.sort_order,
        "pos_x": row.pos_x,
        "pos_y": row.pos_y,
        "width": row.width,
        "height": row.height,
        "color": row.color,
    }


def shelf_to_dict(row: Shelf, zone: LibraryZone | None = None) -> dict:
    zone = zone or row.zone
    has_left_side, has_right_side = _side_flags(row.side_rule)
    return {
        "id": row.id,
        "shelf_id": row.id,
        "shelf_code": row.shelf_code,
        "zone_id": row.zone_id,
        "zone_code": row.zone_code or (zone.zone_code if zone else None),
        "zone_name": zone.zone_name if zone else None,
        "floor": row.floor,
        "floor_label": row.floor,
        "shelf_index": row.shelf_index,
        "shelf_no": row.shelf_index,
        "layer_count": row.layer_count,
        "side_rule": row.side_rule,
        "has_left_side": has_left_side,
        "has_right_side": has_right_side,
        "shelf_type": row.shelf_type,
        "main_collection": row.shelf_type,
        "shelf_group": row.zone_code or (zone.zone_code if zone else None),
        "counted_in_72_formal_shelves": row.counted_in_72_formal_shelves,
        "pos_x": row.pos_x,
        "pos_y": row.pos_y,
        "width": row.width,
        "height": row.height,
        "rotation": row.rotation,
    }


def position_to_dict(row: ShelfPosition, shelf: Shelf | None = None, zone: LibraryZone | None = None) -> dict:
    shelf = shelf or row.shelf
    zone = zone or (shelf.zone if shelf else None)
    return {
        "id": row.id,
        "position_code": row.position_code,
        "shelf_id": row.shelf_id,
        "shelf_code": shelf.shelf_code if shelf else None,
        "zone_id": shelf.zone_id if shelf else None,
        "zone_code": zone.zone_code if zone else None,
        "zone_name": zone.zone_name if zone else None,
        "floor": shelf.floor if shelf else None,
        "floor_label": shelf.floor if shelf else None,
        "layer_no": row.layer_no,
        "side": row.side,
        "capacity_estimate": row.capacity_estimate,
    }


def list_zones(db: Session, *, keyword: str | None = None, limit: int = 20, offset: int = 0) -> dict:
    stmt = select(LibraryZone)
    if keyword:
        stmt = stmt.where(or_(LibraryZone.zone_code.contains(keyword), LibraryZone.zone_name.contains(keyword), LibraryZone.main_use.contains(keyword)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(LibraryZone.sort_order, LibraryZone.id).offset(offset).limit(limit)).all()
    return _page_response([zone_to_dict(row) for row in rows], total, limit, offset)


def list_shelves(
    db: Session,
    *,
    keyword: str | None = None,
    zone_id: int | None = None,
    zone_code: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    stmt = select(Shelf, LibraryZone).join(LibraryZone, Shelf.zone_id == LibraryZone.id)
    if keyword:
        stmt = stmt.where(or_(Shelf.shelf_code.contains(keyword), Shelf.shelf_type.contains(keyword), LibraryZone.zone_name.contains(keyword)))
    if zone_id is not None:
        stmt = stmt.where(Shelf.zone_id == zone_id)
    if zone_code:
        stmt = stmt.where(LibraryZone.zone_code == zone_code)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.order_by(LibraryZone.sort_order, Shelf.shelf_index, Shelf.id).offset(offset).limit(limit)).all()
    return _page_response([shelf_to_dict(shelf, zone) for shelf, zone in rows], total, limit, offset)


def list_positions(
    db: Session,
    *,
    keyword: str | None = None,
    shelf_id: int | None = None,
    shelf_code: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    shelves = db.scalars(select(Shelf).order_by(Shelf.zone_id, Shelf.shelf_index, Shelf.id)).all()
    shelf_by_id = {row.id: row for row in shelves}
    shelf_by_code = {row.shelf_code: row for row in shelves if row.shelf_code}
    zones = {row.id: row for row in db.scalars(select(LibraryZone)).all()}

    positions = db.scalars(select(ShelfPosition).order_by(ShelfPosition.position_code, ShelfPosition.layer_no, ShelfPosition.side)).all()
    items: list[dict] = []
    for position in positions:
        shelf = shelf_by_id.get(position.shelf_id) if position.shelf_id else None
        if shelf is None:
            shelf = shelf_by_code.get(_shelf_code_from_position(position.position_code))
        zone = zones.get(shelf.zone_id) if shelf else None

        if shelf_id is not None and (not shelf or shelf.id != shelf_id):
            continue
        if shelf_code and (not shelf or shelf.shelf_code != shelf_code):
            continue
        if keyword:
            haystack = " ".join(
                str(value or "")
                for value in [position.position_code, shelf.shelf_code if shelf else None, zone.zone_code if zone else None, zone.zone_name if zone else None]
            )
            if keyword not in haystack:
                continue
        items.append(position_to_dict(position, shelf, zone))

    total = len(items)
    return _page_response(items[offset : offset + limit], total, limit, offset)


def location_tree(db: Session) -> dict:
    zones = db.scalars(select(LibraryZone).order_by(LibraryZone.sort_order, LibraryZone.id)).all()
    if not zones:
        return {"items": [], "total": 0, "empty_state": True}
    shelves = db.scalars(select(Shelf).order_by(Shelf.zone_id, Shelf.shelf_index, Shelf.id)).all()
    shelf_by_code = {row.shelf_code: row for row in shelves if row.shelf_code}
    positions = db.scalars(select(ShelfPosition).order_by(ShelfPosition.position_code, ShelfPosition.layer_no, ShelfPosition.side)).all()
    positions_by_shelf: dict[int, list[ShelfPosition]] = {}
    for position in positions:
        resolved_shelf_id = position.shelf_id
        if resolved_shelf_id is None:
            shelf = shelf_by_code.get(_shelf_code_from_position(position.position_code))
            resolved_shelf_id = shelf.id if shelf else None
        if resolved_shelf_id is not None:
            positions_by_shelf.setdefault(resolved_shelf_id, []).append(position)
    shelves_by_zone: dict[int, list[Shelf]] = {}
    for shelf in shelves:
        shelves_by_zone.setdefault(shelf.zone_id, []).append(shelf)
    items = []
    for zone in zones:
        zone_item = zone_to_dict(zone)
        zone_item["shelves"] = []
        for shelf in shelves_by_zone.get(zone.id, []):
            shelf_item = shelf_to_dict(shelf, zone)
            shelf_item["positions"] = [position_to_dict(position, shelf, zone) for position in positions_by_shelf.get(shelf.id, [])]
            zone_item["shelves"].append(shelf_item)
        items.append(zone_item)
    return {"items": items, "total": len(items)}


def repair_shelf_position_links(db: Session, *, commit: bool = True) -> dict:
    """Backfill shelf_positions.shelf_id from position_code when old imports left it empty."""
    shelves = {row.shelf_code: row for row in db.scalars(select(Shelf)).all() if row.shelf_code}
    updated = 0
    unresolved = 0
    for position in db.scalars(select(ShelfPosition).where(ShelfPosition.shelf_id.is_(None))).all():
        shelf = shelves.get(_shelf_code_from_position(position.position_code))
        if shelf:
            position.shelf_id = shelf.id
            updated += 1
        else:
            unresolved += 1
    if commit:
        db.commit()
    return {"updated": updated, "unresolved": unresolved}


# ── Zone / Shelf CRUD ──

from bookflow_core.core.exceptions import NotFoundError, BusinessRuleError
from bookflow_core.core.time import now
from bookflow_core.services.common import write_audit


def create_zone(db: Session, *, zone_code: str, zone_name: str, floor: str = "", area_sqm: float = 0, main_use: str = "", is_public: bool = True, sort_order: int = 0, pos_x: float = 0, pos_y: float = 0, width: float = 200, height: float = 150, color: str = "#e8f4f8", actor_id: str = "admin") -> LibraryZone:
    existing = db.scalar(select(LibraryZone).where(LibraryZone.zone_code == zone_code))
    if existing:
        raise BusinessRuleError("该分区编号已存在。", code="VALIDATION_ERROR")
    row = LibraryZone(zone_code=zone_code, zone_name=zone_name, floor=floor, area_sqm=area_sqm, main_use=main_use, is_public=is_public, sort_order=sort_order, pos_x=pos_x, pos_y=pos_y, width=width, height=height, color=color, created_at=now(), updated_at=now())
    db.add(row)
    db.flush()
    write_audit(db, actor_type="admin", actor_id=actor_id, action="create_zone", target_table="library_zones", target_id=row.id, detail={"zone_code": zone_code, "zone_name": zone_name})
    db.commit()
    return row


def update_zone(db: Session, *, zone_id: int, zone_name: str | None = None, floor: str | None = None, area_sqm: float | None = None, main_use: str | None = None, is_public: bool | None = None, sort_order: int | None = None, pos_x: float | None = None, pos_y: float | None = None, width: float | None = None, height: float | None = None, color: str | None = None, actor_id: str = "admin") -> LibraryZone:
    row = db.get(LibraryZone, zone_id)
    if not row:
        raise NotFoundError("LibraryZone not found.", code="NOT_FOUND")
    for field in ["zone_name", "floor", "main_use", "color"]:
        val = locals().get(field)
        if val is not None: setattr(row, field, val)
    for field in ["area_sqm", "sort_order", "pos_x", "pos_y", "width", "height"]:
        val = locals().get(field)
        if val is not None: setattr(row, field, val)
    if is_public is not None: row.is_public = is_public
    row.updated_at = now()
    write_audit(db, actor_type="admin", actor_id=actor_id, action="update_zone", target_table="library_zones", target_id=row.id, detail={"zone_name": row.zone_name})
    db.commit()
    return row


def delete_zone(db: Session, *, zone_id: int, actor_id: str = "admin") -> None:
    row = db.get(LibraryZone, zone_id)
    if not row:
        raise NotFoundError("LibraryZone not found.", code="NOT_FOUND")
    shelf_count = db.scalar(select(func.count(Shelf.id)).where(Shelf.zone_id == zone_id)) or 0
    if shelf_count > 0:
        raise BusinessRuleError(f"该分区下还有 {shelf_count} 组书架，请先删除书架。", code="BUSINESS_RULE")
    write_audit(db, actor_type="admin", actor_id=actor_id, action="delete_zone", target_table="library_zones", target_id=row.id, detail={"zone_code": row.zone_code, "zone_name": row.zone_name})
    db.delete(row)
    db.commit()


def create_shelf(db: Session, *, shelf_code: str, zone_id: int, floor: str = "", shelf_index: int = 0, layer_count: int = 4, side_rule: str = "both", shelf_type: str = "formal", pos_x: float = 0, pos_y: float = 0, width: float = 60, height: float = 40, rotation: float = 0, actor_id: str = "admin") -> Shelf:
    zone = db.get(LibraryZone, zone_id)
    if not zone:
        raise NotFoundError("LibraryZone not found.", code="NOT_FOUND")
    existing = db.scalar(select(Shelf).where(Shelf.shelf_code == shelf_code))
    if existing:
        raise BusinessRuleError("该书架编号已存在。", code="VALIDATION_ERROR")
    row = Shelf(shelf_code=shelf_code, zone_id=zone.id, zone_code=zone.zone_code, floor=floor or zone.floor, shelf_index=shelf_index, layer_count=layer_count, side_rule=side_rule, shelf_type=shelf_type, pos_x=pos_x, pos_y=pos_y, width=width, height=height, rotation=rotation, created_at=now(), updated_at=now())
    db.add(row)
    db.flush()
    write_audit(db, actor_type="admin", actor_id=actor_id, action="create_shelf", target_table="shelves", target_id=row.id, detail={"shelf_code": shelf_code, "zone_code": zone.zone_code})
    db.commit()
    return row


def update_shelf(db: Session, *, shelf_id: int, zone_id: int | None = None, shelf_index: int | None = None, layer_count: int | None = None, side_rule: str | None = None, shelf_type: str | None = None, pos_x: float | None = None, pos_y: float | None = None, width: float | None = None, height: float | None = None, rotation: float | None = None, actor_id: str = "admin") -> Shelf:
    row = db.get(Shelf, shelf_id)
    if not row:
        raise NotFoundError("Shelf not found.", code="NOT_FOUND")
    if zone_id is not None:
        zone = db.get(LibraryZone, zone_id)
        if not zone:
            raise NotFoundError("LibraryZone not found.", code="NOT_FOUND")
        row.zone_id = zone.id
        row.zone_code = zone.zone_code
    for field in ["shelf_index", "layer_count", "side_rule", "shelf_type"]:
        val = locals().get(field)
        if val is not None: setattr(row, field, val)
    for field in ["pos_x", "pos_y", "width", "height", "rotation"]:
        val = locals().get(field)
        if val is not None: setattr(row, field, val)
    row.updated_at = now()
    write_audit(db, actor_type="admin", actor_id=actor_id, action="update_shelf", target_table="shelves", target_id=row.id, detail={"shelf_code": row.shelf_code})
    db.commit()
    return row


def delete_shelf(db: Session, *, shelf_id: int, actor_id: str = "admin") -> None:
    row = db.get(Shelf, shelf_id)
    if not row:
        raise NotFoundError("Shelf not found.", code="NOT_FOUND")
    pos_count = db.scalar(select(func.count(ShelfPosition.id)).where(ShelfPosition.shelf_id == shelf_id)) or 0
    if pos_count > 0:
        raise BusinessRuleError(f"该书架下还有 {pos_count} 个架位，请先清理架位。", code="BUSINESS_RULE")
    write_audit(db, actor_type="admin", actor_id=actor_id, action="delete_shelf", target_table="shelves", target_id=row.id, detail={"shelf_code": row.shelf_code})
    db.delete(row)
    db.commit()


BOOKFLOW_DEFAULT_ZONES = [
    {"zone_code": "Z03", "zone_name": "少儿阅览区", "floor": "F1", "area_sqm": 420, "main_use": "儿童区", "sort_order": 3, "pos_x": 48, "pos_y": 48, "width": 300, "height": 250, "color": "#dff0c9"},
    {"zone_code": "Z05", "zone_name": "活动室", "floor": "F1", "area_sqm": 260, "main_use": "活动室", "sort_order": 5, "pos_x": 360, "pos_y": 48, "width": 220, "height": 250, "color": "#ffd9e3"},
    {"zone_code": "Z04", "zone_name": "期刊报纸区", "floor": "F1", "area_sqm": 720, "main_use": "阅览区", "sort_order": 4, "pos_x": 596, "pos_y": 48, "width": 360, "height": 430, "color": "#cfe8ff"},
    {"zone_code": "Z14-F1", "zone_name": "公共休息及通道区", "floor": "F1", "area_sqm": 620, "main_use": "公共休息及通道区", "sort_order": 14, "pos_x": 48, "pos_y": 310, "width": 530, "height": 245, "color": "#f6ead5"},
    {"zone_code": "Z02", "zone_name": "自助借还区", "floor": "F1", "area_sqm": 210, "main_use": "服务区", "sort_order": 2, "pos_x": 170, "pos_y": 585, "width": 190, "height": 155, "color": "#ffefad"},
    {"zone_code": "Z01", "zone_name": "总服务台", "floor": "F1", "area_sqm": 240, "main_use": "服务台", "sort_order": 1, "pos_x": 380, "pos_y": 585, "width": 220, "height": 155, "color": "#ffd19a"},
    {"zone_code": "Z06", "zone_name": "电子查询区", "floor": "F1", "area_sqm": 260, "main_use": "查询区", "sort_order": 6, "pos_x": 620, "pos_y": 585, "width": 250, "height": 155, "color": "#eadbff"},
    {"zone_code": "Z07", "zone_name": "成人文学区", "floor": "F2", "area_sqm": 530, "main_use": "藏书区", "sort_order": 7, "pos_x": 48, "pos_y": 48, "width": 300, "height": 250, "color": "#d7ebff"},
    {"zone_code": "Z08", "zone_name": "社科生活区", "floor": "F2", "area_sqm": 480, "main_use": "藏书区", "sort_order": 8, "pos_x": 360, "pos_y": 48, "width": 270, "height": 250, "color": "#e0f1cd"},
    {"zone_code": "Z09", "zone_name": "科普技术区", "floor": "F2", "area_sqm": 500, "main_use": "藏书区", "sort_order": 9, "pos_x": 642, "pos_y": 48, "width": 314, "height": 250, "color": "#fff0bf"},
    {"zone_code": "Z10", "zone_name": "地方文献与工具书区", "floor": "F2", "area_sqm": 650, "main_use": "藏书区", "sort_order": 10, "pos_x": 48, "pos_y": 328, "width": 330, "height": 405, "color": "#eadbff"},
    {"zone_code": "Z14-F2", "zone_name": "公共休息及通道区", "floor": "F2", "area_sqm": 560, "main_use": "公共休息及通道区", "sort_order": 14, "pos_x": 392, "pos_y": 320, "width": 500, "height": 230, "color": "#f6ead5"},
    {"zone_code": "Z11", "zone_name": "后台编目区", "floor": "F2", "area_sqm": 320, "main_use": "后台作业区", "sort_order": 11, "pos_x": 392, "pos_y": 575, "width": 250, "height": 155, "color": "#ffd9e3"},
    {"zone_code": "Z12", "zone_name": "临时周转区", "floor": "F2", "area_sqm": 170, "main_use": "周转区", "sort_order": 12, "pos_x": 656, "pos_y": 575, "width": 140, "height": 155, "color": "#cfe8ff"},
    {"zone_code": "Z13", "zone_name": "管理办公室", "floor": "F2", "area_sqm": 240, "main_use": "办公室", "sort_order": 13, "pos_x": 810, "pos_y": 575, "width": 146, "height": 155, "color": "#ffd7a8"},
]


BOOKFLOW_DEFAULT_SHELVES = [
    ("Z03", 4, "child"), ("Z05", 2, "activity"), ("Z04", 10, "periodical"),
    ("Z02", 3, "service"), ("Z06", 4, "terminal"),
    ("Z07", 10, "formal"), ("Z08", 9, "formal"), ("Z09", 8, "formal"),
    ("Z10", 12, "formal"), ("Z11", 4, "work"), ("Z12", 4, "turnover"), ("Z13", 2, "office"),
]


def _template_shelf_rect(zone: LibraryZone, index: int, total: int) -> tuple[float, float, float, float, float]:
    width = 54 if zone.width >= zone.height else 46
    height = 18 if zone.width >= zone.height else 58
    cols = max(1, min(4, int((zone.width - 40) // 82)))
    row = index // cols
    col = index % cols
    x = float(zone.pos_x or 0) + 24 + col * 82
    y = float(zone.pos_y or 0) + 36 + row * 58
    if total > 8 and row >= 2:
        y += 28
    if x + width > float(zone.pos_x or 0) + float(zone.width or 0) - 16:
        x = float(zone.pos_x or 0) + float(zone.width or 0) - width - 18
    if y + height > float(zone.pos_y or 0) + float(zone.height or 0) - 16:
        y = float(zone.pos_y or 0) + float(zone.height or 0) - height - 18
    return x, y, width, height, 0


def apply_bookflow_default_layout(db: Session, *, actor_id: str = "admin") -> dict:
    """Upsert the simplified F1/F2 BookFlow layout used by the floor-plan editor."""
    zone_by_code = {row.zone_code: row for row in db.scalars(select(LibraryZone)).all()}
    zones_created = 0
    zones_updated = 0
    for item in BOOKFLOW_DEFAULT_ZONES:
        row = zone_by_code.get(item["zone_code"])
        if row:
            zones_updated += 1
        else:
            row = LibraryZone(zone_code=item["zone_code"], created_at=now())
            db.add(row)
            zones_created += 1
        row.zone_name = item["zone_name"]
        row.floor = item["floor"]
        row.area_sqm = item["area_sqm"]
        row.main_use = item["main_use"]
        row.is_public = True
        row.sort_order = item["sort_order"]
        row.pos_x = item["pos_x"]
        row.pos_y = item["pos_y"]
        row.width = item["width"]
        row.height = item["height"]
        row.color = item["color"]
        row.updated_at = now()
    db.flush()

    zone_by_code = {row.zone_code: row for row in db.scalars(select(LibraryZone)).all()}
    shelf_by_code = {row.shelf_code: row for row in db.scalars(select(Shelf)).all()}
    shelves_created = 0
    shelves_updated = 0
    for zone_code, count, shelf_type in BOOKFLOW_DEFAULT_SHELVES:
        zone = zone_by_code.get(zone_code)
        if not zone:
            continue
        for index in range(count):
            shelf_code = f"{zone_code}-S{index + 1:02d}"
            shelf = shelf_by_code.get(shelf_code)
            if shelf:
                shelves_updated += 1
            else:
                shelf = Shelf(shelf_code=shelf_code, created_at=now())
                db.add(shelf)
                shelves_created += 1
            x, y, width, height, rotation = _template_shelf_rect(zone, index, count)
            shelf.zone_id = zone.id
            shelf.zone_code = zone.zone_code
            shelf.floor = zone.floor
            shelf.shelf_index = index + 1
            shelf.layer_count = 4
            shelf.side_rule = "both"
            shelf.shelf_type = shelf_type
            shelf.counted_in_72_formal_shelves = shelf_type == "formal"
            shelf.pos_x = x
            shelf.pos_y = y
            shelf.width = width
            shelf.height = height
            shelf.rotation = rotation
            shelf.updated_at = now()
    write_audit(
        db,
        actor_type="admin",
        actor_id=actor_id,
        action="apply_default_floor_layout",
        target_table="library_zones,shelves",
        target_id="bookflow_f1_f2",
        detail={"zones_created": zones_created, "zones_updated": zones_updated, "shelves_created": shelves_created, "shelves_updated": shelves_updated},
    )
    db.commit()
    return {"zones_created": zones_created, "zones_updated": zones_updated, "shelves_created": shelves_created, "shelves_updated": shelves_updated}


def batch_save_layout(db: Session, *, zones: list[dict], shelves: list[dict], actor_id: str = "admin") -> dict:
    """Save layout positions for zones and shelves in a single batch."""
    zone_updated = 0
    shelf_updated = 0
    for item in zones:
        zone = db.get(LibraryZone, item["id"])
        if zone:
            zone.pos_x = item.get("pos_x", zone.pos_x)
            zone.pos_y = item.get("pos_y", zone.pos_y)
            zone.width = item.get("width", zone.width)
            zone.height = item.get("height", zone.height)
            zone.updated_at = now()
            zone_updated += 1
    for item in shelves:
        shelf = db.get(Shelf, item["id"])
        if shelf:
            shelf.pos_x = item.get("pos_x", shelf.pos_x)
            shelf.pos_y = item.get("pos_y", shelf.pos_y)
            shelf.width = item.get("width", shelf.width)
            shelf.height = item.get("height", shelf.height)
            shelf.rotation = item.get("rotation", shelf.rotation)
            shelf.updated_at = now()
            shelf_updated += 1
    write_audit(db, actor_type="admin", actor_id=actor_id, action="batch_save_layout", target_table="library_zones,shelves", target_id="batch", detail={"zones_updated": zone_updated, "shelves_updated": shelf_updated})
    db.commit()
    return {"zones_updated": zone_updated, "shelves_updated": shelf_updated}
