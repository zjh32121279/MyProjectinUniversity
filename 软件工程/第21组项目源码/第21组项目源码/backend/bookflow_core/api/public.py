from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from bookflow_core.api.deps import get_optional_reader
from bookflow_core.core.database import get_db
from bookflow_core.models import ReaderAccount
from bookflow_core.schemas.public import SearchEventRequest
from bookflow_core.services.public_catalog_service import (
    filter_options,
    get_public_book,
    get_public_book_availability,
    get_public_book_copies,
    hot_keywords,
    library_profile,
    list_public_books,
    list_public_categories,
    list_public_zones,
    public_location_map,
    record_search_event,
)

router = APIRouter(prefix="/public", tags=["public"])


def _response(data, message: str | None = None):
    return {"success": True, "data": data, "message": message}


@router.get("/library/profile")
def get_library_profile(db: Session = Depends(get_db)):
    return _response(library_profile(db))


@router.get("/catalog/books")
def books(
    keyword: str | None = None,
    category: str | None = None,
    category_code: str | None = None,
    availability: str | None = None,
    circulation_type: str | None = None,
    zone: str | None = None,
    floor: str | None = None,
    sort: str | None = None,
    page: int = 1,
    page_size: int = Query(20, le=100),
    limit: int | None = Query(default=None, le=100),
    offset: int | None = 0,
    db: Session = Depends(get_db),
):
    if limit is not None:
        page_size = limit
        page = int((offset or 0) / max(limit, 1)) + 1
    data = list_public_books(
        db,
        keyword=keyword,
        category=category or category_code,
        availability=availability,
        circulation_type=circulation_type,
        zone=zone,
        floor=floor,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return _response(data, "暂无数据" if data.get("empty_state") else None)


@router.get("/catalog/books/{book_id}")
def book_detail(book_id: int, db: Session = Depends(get_db)):
    return _response(get_public_book(db, book_id))


@router.get("/catalog/books/{book_id}/copies")
def book_copies(book_id: int, limit: int = Query(100, le=200), offset: int = 0, db: Session = Depends(get_db)):
    data = get_public_book_copies(db, book_id, limit=limit, offset=offset)
    return _response(data, "暂无数据" if data.get("empty_state") else None)


@router.get("/catalog/books/{book_id}/availability")
def book_availability(book_id: int, db: Session = Depends(get_db)):
    return _response(get_public_book_availability(db, book_id))


@router.get("/catalog/categories")
def categories(db: Session = Depends(get_db)):
    return _response(list_public_categories(db))


@router.get("/catalog/filter-options")
def catalog_filter_options(db: Session = Depends(get_db)):
    return _response(filter_options(db))


@router.get("/locations/zones")
def zones(db: Session = Depends(get_db)):
    data = list_public_zones(db)
    return _response(data, "暂无数据" if data.get("empty_state") else None)


@router.get("/locations/map")
def location_map(db: Session = Depends(get_db)):
    data = public_location_map(db)
    return _response(data, "暂无数据" if data.get("empty_state") else None)


@router.get("/search/hot-keywords")
def search_hot_keywords(limit: int = Query(10, le=50), db: Session = Depends(get_db)):
    return _response(hot_keywords(db, limit=limit))


@router.post("/search/events")
def search_event(req: SearchEventRequest, db: Session = Depends(get_db), current_reader: ReaderAccount | None = Depends(get_optional_reader)):
    return _response(record_search_event(db, keyword=req.keyword, reader_id=current_reader.id if current_reader else None))
