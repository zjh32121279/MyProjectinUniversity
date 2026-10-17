from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from bookflow_core.api.deps import require_permission
from bookflow_core.core.config import project_root
from bookflow_core.core.database import get_db
from bookflow_core.core.exceptions import BookFlowError
from bookflow_core.schemas import CreateBookRequest, CreateCopiesRequest, UpdateBookRequest, UpdateCopyLocationRequest, UpdateCopyStatusRequest
from bookflow_core.services.catalog_service import (
    book_detail,
    book_list_item_to_dict,
    copy_to_dict,
    create_book,
    create_book_copies,
    create_category,
    create_subcategory,
    delete_category,
    delete_subcategory,
    get_book,
    list_book_copies,
    list_books,
    list_categories,
    list_copies,
    list_subcategories,
    recalculate_all_circulation_types,
    update_book,
    update_category,
    update_copy_location,
    update_copy_status,
    update_copy_status_by_id,
    update_subcategory,
)

router = APIRouter(prefix="/catalog", tags=["catalog"])
EMPTY_MESSAGE = "数据库暂无可用数据，请先导入或迁移业务数据。"
BOOK_COVER_DIR = project_root() / "data" / "uploads" / "book-covers"
MAX_COVER_UPLOAD_BYTES = 5 * 1024 * 1024


def _list_response(data: dict):
    return {"success": True, "data": data, "message": EMPTY_MESSAGE if data.get("empty_state") else None}


def _validate_cover_bytes(body: bytes) -> str:
    if not body:
        raise BookFlowError("封面图片为空。", code="VALIDATION_ERROR")
    if len(body) > MAX_COVER_UPLOAD_BYTES:
        raise BookFlowError("封面图片不能超过 5MB。", code="VALIDATION_ERROR", details={"max_bytes": MAX_COVER_UPLOAD_BYTES})
    if body.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if body.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if len(body) >= 12 and body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return ".webp"
    raise BookFlowError("封面图片仅支持 JPG、PNG 或 WebP。", code="VALIDATION_ERROR")


def _local_cover_path(cover_url: str | None):
    if not cover_url or not cover_url.startswith("/uploads/book-covers/"):
        return None
    filename = cover_url.rsplit("/", 1)[-1]
    if not filename or "/" in filename or "\\" in filename:
        return None
    return BOOK_COVER_DIR / filename


@router.get("/books")
def books(
    circulation_type: str | None = None,
    keyword: str | None = None,
    category_id: int | None = None,
    category_code: str | None = None,
    subcategory_id: int | None = None,
    subcategory_code: str | None = None,
    copy_status: str | None = None,
    zone_id: int | None = None,
    zone_code: str | None = None,
    is_active: bool | None = None,
    limit: int = Query(50, le=10000),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    limit = min(limit, 10000)
    result = list_books(
        db,
        circulation_type=circulation_type,
        keyword=keyword,
        category_id=category_id,
        category_code=category_code,
        subcategory_id=subcategory_id,
        subcategory_code=subcategory_code,
        copy_status=copy_status,
        zone_id=zone_id,
        zone_code=zone_code,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    data = {**result, "items": [book_list_item_to_dict(db, b) for b in result["items"]]}
    if data["total"] == 0:
        data["empty_state"] = True
    return _list_response(data)


@router.get("/categories")
def categories(limit: int = Query(200, le=500), offset: int = 0, db: Session = Depends(get_db)):
    return _list_response(list_categories(db, limit=limit, offset=offset))


@router.get("/subcategories")
def subcategories(category_id: int | None = None, category_code: str | None = None, limit: int = Query(500, le=1000), offset: int = 0, db: Session = Depends(get_db)):
    return _list_response(list_subcategories(db, category_id=category_id, category_code=category_code, limit=limit, offset=offset))


@router.post("/books")
def create(req: CreateBookRequest, db: Session = Depends(get_db), current_admin=Depends(require_permission("catalog:write"))):
    book = create_book(db, **req.model_dump(exclude={"initial_copies"}), initial_copies=req.initial_copies, actor_id=current_admin.admin_code)
    return {"success": True, "data": book_detail(db, book.id), "message": None}


@router.get("/books/{book_id}")
def detail(book_id: int, db: Session = Depends(get_db)):
    return {"success": True, "data": book_detail(db, book_id), "message": None}


@router.put("/books/{book_id}")
def update(book_id: int, req: UpdateBookRequest, db: Session = Depends(get_db), current_admin=Depends(require_permission("catalog:write"))):
    book = update_book(db, book_id, **req.model_dump(), actor_id=current_admin.admin_code)
    return {"success": True, "data": book_detail(db, book.id), "message": None}


@router.post("/books/{book_id}/cover")
async def upload_cover(
    book_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_admin=Depends(require_permission("catalog:write")),
):
    book = get_book(db, book_id)
    old_cover_path = _local_cover_path(book.cover_url)

    body = await file.read(MAX_COVER_UPLOAD_BYTES + 1)
    suffix = _validate_cover_bytes(body)
    BOOK_COVER_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"book-{book_id}-{uuid4().hex}{suffix}"
    cover_path = BOOK_COVER_DIR / filename
    cover_path.write_bytes(body)

    cover_url = f"/uploads/book-covers/{filename}"
    try:
        book = update_book(db, book_id, cover_url=cover_url, cover_source="upload", cover_status="ready", actor_id=current_admin.admin_code)
    except Exception:
        cover_path.unlink(missing_ok=True)
        raise

    if old_cover_path and old_cover_path != cover_path:
        old_cover_path.unlink(missing_ok=True)
    return {"success": True, "data": book_detail(db, book.id), "message": None}


@router.get("/books/{book_id}/copies")
def book_copies(book_id: int, limit: int = Query(100, le=200), offset: int = 0, db: Session = Depends(get_db)):
    return _list_response(list_book_copies(db, book_id, limit=limit, offset=offset))


@router.post("/books/{book_id}/copies")
def add_copies(book_id: int, req: CreateCopiesRequest, db: Session = Depends(get_db), current_admin=Depends(require_permission("catalog:write"))):
    rows = create_book_copies(db, book_id, **req.model_dump(), actor_id=current_admin.admin_code)
    return {"success": True, "data": {"items": [copy_to_dict(db, row) for row in rows], "total": len(rows)}, "message": None}


@router.get("/copies")
def copies(
    book_id: int | None = None,
    status: str | None = None,
    zone: str | None = None,
    shelf: str | None = None,
    keyword: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    return _list_response(list_copies(db, book_id=book_id, status=status, zone=zone, shelf=shelf, keyword=keyword, limit=limit, offset=offset))


@router.post("/copies/{copy_code}/status")
def change_copy_status(copy_code: str, body: dict, db: Session = Depends(get_db), current_admin=Depends(require_permission("catalog:write"))):
    copy = update_copy_status(db, copy_code, body["new_status"], reason=body.get("reason", "api_update"), actor_type="admin", actor_id=current_admin.admin_code)
    return {"success": True, "data": {"copy_code": copy.copy_code, "copy_status": copy.copy_status}, "message": None}


@router.put("/copies/{copy_id}/status")
def change_copy_status_by_id(copy_id: int, req: UpdateCopyStatusRequest, db: Session = Depends(get_db), current_admin=Depends(require_permission("catalog:write"))):
    copy = update_copy_status_by_id(db, copy_id, req.new_status, reason=req.reason, actor_type="admin", actor_id=current_admin.admin_code)
    return {"success": True, "data": copy_to_dict(db, copy), "message": None}


@router.put("/copies/{copy_id}/location")
def change_copy_location(copy_id: int, req: UpdateCopyLocationRequest, db: Session = Depends(get_db), current_admin=Depends(require_permission("catalog:write"))):
    copy = update_copy_location(db, copy_id, req.current_position_id, reason=req.reason, actor_type="admin", actor_id=current_admin.admin_code)
    return {"success": True, "data": copy_to_dict(db, copy), "message": None}


@router.post("/recalculate-circulation")
def recalc(db: Session = Depends(get_db), current_admin=Depends(require_permission("catalog:write"))):
    count = recalculate_all_circulation_types(db)
    db.commit()
    return {"success": True, "data": {"updated": count}, "message": None}


# ── Category / Subcategory CRUD ──

@router.post("/categories")
def add_category(body: dict, db: Session = Depends(get_db), current_admin=Depends(require_permission("catalog:write"))):
    row = create_category(
        db,
        category_code=body["category_code"],
        category_name=body["category_name"],
        subcategory_examples=body.get("subcategory_examples"),
        primary_zone_code=body.get("primary_zone_code"),
        clc_hint=body.get("clc_hint"),
        sort_order=body.get("sort_order", 0),
        actor_id=current_admin.admin_code,
    )
    return {"success": True, "data": {"id": row.id, "category_code": row.category_code, "category_name": row.category_name}, "message": None}


@router.put("/categories/{category_id}")
def edit_category(category_id: int, body: dict, db: Session = Depends(get_db), current_admin=Depends(require_permission("catalog:write"))):
    row = update_category(
        db,
        category_id=category_id,
        category_name=body.get("category_name"),
        subcategory_examples=body.get("subcategory_examples"),
        primary_zone_code=body.get("primary_zone_code"),
        clc_hint=body.get("clc_hint"),
        sort_order=body.get("sort_order"),
        actor_id=current_admin.admin_code,
    )
    return {"success": True, "data": {"id": row.id, "category_code": row.category_code, "category_name": row.category_name}, "message": None}


@router.delete("/categories/{category_id}")
def remove_category(category_id: int, db: Session = Depends(get_db), current_admin=Depends(require_permission("catalog:write"))):
    delete_category(db, category_id=category_id, actor_id=current_admin.admin_code)
    return {"success": True, "data": None, "message": None}


@router.post("/subcategories")
def add_subcategory(body: dict, db: Session = Depends(get_db), current_admin=Depends(require_permission("catalog:write"))):
    row = create_subcategory(
        db,
        category_id=body["category_id"],
        subcategory_code=body["subcategory_code"],
        subcategory_name=body["subcategory_name"],
        sort_order=body.get("sort_order", 0),
        actor_id=current_admin.admin_code,
    )
    return {"success": True, "data": {"id": row.id, "subcategory_code": row.subcategory_code, "subcategory_name": row.subcategory_name, "category_id": row.category_id, "category_code": row.category_code}, "message": None}


@router.put("/subcategories/{subcategory_id}")
def edit_subcategory(subcategory_id: int, body: dict, db: Session = Depends(get_db), current_admin=Depends(require_permission("catalog:write"))):
    row = update_subcategory(
        db,
        subcategory_id=subcategory_id,
        subcategory_name=body.get("subcategory_name"),
        sort_order=body.get("sort_order"),
        actor_id=current_admin.admin_code,
    )
    return {"success": True, "data": {"id": row.id, "subcategory_code": row.subcategory_code, "subcategory_name": row.subcategory_name}, "message": None}


@router.delete("/subcategories/{subcategory_id}")
def remove_subcategory(subcategory_id: int, db: Session = Depends(get_db), current_admin=Depends(require_permission("catalog:write"))):
    delete_subcategory(db, subcategory_id=subcategory_id, actor_id=current_admin.admin_code)
    return {"success": True, "data": None, "message": None}
