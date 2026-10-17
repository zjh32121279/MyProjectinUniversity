from __future__ import annotations

from sqlalchemy import and_, exists, func, or_, select, text
from sqlalchemy.orm import Session

from bookflow_core.models import (
    Book,
    BookCategory,
    BookCirculationStats,
    BookCopy,
    BookSubcategory,
    LibraryProfile,
    LibraryZone,
    SystemSetting,
    Reservation,
    Shelf,
)
from bookflow_core.services.catalog_service import book_detail, book_list_item_to_dict, copy_to_dict, list_book_copies
from bookflow_core.services.location_service import location_tree, zone_to_dict
from bookflow_core.services.statistics_service import ACTIVE_RESERVATION_STATUSES
from bookflow_core.core.time import now


def _setting_value(db: Session, key: str, fallback: str | None = None) -> str | None:
    value = db.scalar(select(SystemSetting.setting_value).where(SystemSetting.setting_key == key, SystemSetting.is_active == True))
    return value if value not in (None, "") else fallback


def library_profile(db: Session) -> dict | None:
    profile = db.scalar(select(LibraryProfile).order_by(LibraryProfile.id))
    if not profile:
        return None
    address = _setting_value(db, "library.address", "天津市滨海新区文化路 18 号")
    opening_hours = _setting_value(db, "library.open_hours", "周一至周日 08:30-20:30")
    phone = _setting_value(db, "library.phone", "022-8899-3200")
    service_email = _setting_value(db, "library.service_email", "service@bookflow.local")
    return {
        "id": profile.id,
        "name": profile.library_name,
        "library_name": profile.library_name,
        "library_type": profile.library_type,
        "service_population": profile.service_population,
        "building_area_sqm": profile.building_area_sqm,
        "open_floors": profile.open_floors,
        "paper_collection_count": profile.paper_collection_count,
        "lendable_collection_count": profile.lendable_collection_count,
        "in_library_reference_count": profile.in_library_reference_count,
        "periodical_count": profile.periodical_count,
        "reading_seat_count": profile.reading_seat_count,
        "shelf_count": profile.shelf_count,
        "registered_reader_count": profile.registered_reader_count,
        "monthly_active_reader_count": profile.monthly_active_reader_count,
        "weekday_daily_visits": profile.weekday_daily_visits,
        "weekend_daily_visits": profile.weekend_daily_visits,
        "updated_at": str(profile.updated_at) if profile.updated_at else None,
        "address": address,
        "opening_hours": opening_hours,
        "phone": phone,
        "service_phone": phone,
        "service_email": service_email,
        "service_description": profile.service_population,
    }


def _location_filter(zone: str | None, floor: str | None):
    if not zone and not floor:
        return None
    location = (
        select(BookCopy.id)
        .join(Shelf, BookCopy.current_shelf_id == Shelf.id)
        .join(LibraryZone, Shelf.zone_id == LibraryZone.id)
        .where(BookCopy.book_id == Book.id)
    )
    filters = []
    if zone:
        filters.append(or_(LibraryZone.zone_code == zone, LibraryZone.zone_name.contains(zone)))
    if floor:
        filters.append(or_(LibraryZone.floor == floor, Shelf.floor == floor))
    return exists(location.where(and_(*filters)))


def list_public_books(
    db: Session,
    *,
    keyword: str | None = None,
    category: str | None = None,
    availability: str | None = None,
    circulation_type: str | None = None,
    zone: str | None = None,
    floor: str | None = None,
    sort: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    stmt = (
        select(Book)
        .outerjoin(BookCategory, Book.category_id == BookCategory.id)
        .outerjoin(BookSubcategory, Book.subcategory_id == BookSubcategory.id)
        .outerjoin(BookCirculationStats, BookCirculationStats.book_id == Book.id)
        .where(Book.status == "active")
    )
    available_count = select(func.count(BookCopy.id)).where(BookCopy.book_id == Book.id, BookCopy.copy_status == "available").correlate(Book).scalar_subquery()
    popularity_score = (func.coalesce(BookCirculationStats.borrow_90d, 0) + func.coalesce(BookCirculationStats.reserve_90d, 0) * 2)
    if keyword:
        stmt = stmt.where(
            or_(
                Book.title.contains(keyword),
                Book.author.contains(keyword),
                Book.book_code.contains(keyword),
                Book.isbn.contains(keyword),
                Book.keywords.contains(keyword),
            )
        )
    if category:
        stmt = stmt.where(
            or_(
                BookCategory.category_code == category,
                BookCategory.category_name.contains(category),
                BookSubcategory.subcategory_code == category,
                BookSubcategory.subcategory_name.contains(category),
            )
        )
    if circulation_type:
        stmt = stmt.where(or_(Book.circulation_type == circulation_type, BookCirculationStats.circulation_type == circulation_type))
    if availability == "available":
        stmt = stmt.where(available_count > 0)
    elif availability in {"unavailable", "none"}:
        stmt = stmt.where(available_count <= 0)
    location_clause = _location_filter(zone, floor)
    if location_clause is not None:
        stmt = stmt.where(location_clause)
    if sort == "popular":
        stmt = stmt.order_by(popularity_score.desc(), available_count.desc(), Book.id)
    elif sort == "availability":
        stmt = stmt.order_by(available_count.desc(), Book.id)
    elif sort == "newest":
        stmt = stmt.order_by(Book.publish_year.desc().nullslast(), Book.id.desc())
    elif sort == "title":
        stmt = stmt.order_by(Book.title, Book.id)
    else:
        stmt = stmt.order_by(Book.id)
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "items": [book_list_item_to_dict(db, row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "limit": page_size,
        "offset": (page - 1) * page_size,
        **({"empty_state": True} if total == 0 else {}),
    }


def get_public_book(db: Session, book_id: int) -> dict:
    return book_detail(db, book_id)


def get_public_book_copies(db: Session, book_id: int, *, limit: int = 100, offset: int = 0) -> dict:
    return list_book_copies(db, book_id, limit=limit, offset=offset)


def get_public_book_availability(db: Session, book_id: int) -> dict:
    available = int(db.scalar(select(func.count(BookCopy.id)).where(BookCopy.book_id == book_id, BookCopy.copy_status == "available")) or 0)
    total = int(db.scalar(select(func.count(BookCopy.id)).where(BookCopy.book_id == book_id)) or 0)
    waiting = int(
        db.scalar(
            select(func.count(Reservation.id)).where(
                Reservation.book_id == book_id,
                Reservation.status.in_(ACTIVE_RESERVATION_STATUSES),
            )
        )
        or 0
    )
    return {
        "book_id": book_id,
        "available": available > 0,
        "available_count": available,
        "total_count": total,
        "reservation_queue": waiting,
    }


def list_public_categories(db: Session) -> list[dict]:
    rows = db.scalars(select(BookCategory).order_by(BookCategory.sort_order, BookCategory.id)).all()
    return [
        {
            "id": row.id,
            "code": row.category_code,
            "category_code": row.category_code,
            "name": row.category_name,
            "subcategory_examples": row.subcategory_examples,
            "book_count": int(db.scalar(select(func.count(Book.id)).where(Book.category_id == row.id)) or 0),
        }
        for row in rows
    ]


def filter_options(db: Session) -> dict:
    floors = [
        value
        for value in db.scalars(select(LibraryZone.floor).where(LibraryZone.floor != None).distinct().order_by(LibraryZone.floor)).all()
        if value
    ]
    statuses = [
        value
        for value in db.scalars(select(BookCopy.copy_status).where(BookCopy.copy_status != None).distinct().order_by(BookCopy.copy_status)).all()
        if value
    ]
    return {
        "categories": list_public_categories(db),
        "zones": [zone_to_dict(row) for row in db.scalars(select(LibraryZone).order_by(LibraryZone.sort_order, LibraryZone.id)).all()],
        "floors": floors,
        "availability": statuses,
    }


def list_public_zones(db: Session) -> dict:
    rows = db.scalars(select(LibraryZone).where(LibraryZone.is_public == True).order_by(LibraryZone.sort_order, LibraryZone.id)).all()
    return {"items": [zone_to_dict(row) for row in rows], "total": len(rows), **({"empty_state": True} if not rows else {})}


def public_location_map(db: Session) -> dict:
    return location_tree(db)


def hot_keywords(db: Session, *, limit: int = 10) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT keyword, COUNT(*) AS count
            FROM search_events
            WHERE keyword IS NOT NULL AND TRIM(keyword) <> ''
            GROUP BY keyword
            ORDER BY count DESC, MAX(created_at) DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings().all()
    return [{"keyword": row["keyword"], "count": row["count"]} for row in rows]


def record_search_event(db: Session, *, keyword: str, reader_id: int | None = None) -> dict:
    normalized = keyword.strip()
    if not normalized:
        return {"recorded": False}
    db.execute(
        text("INSERT INTO search_events (keyword, reader_id, created_at) VALUES (:keyword, :reader_id, :created_at)"),
        {"keyword": normalized, "reader_id": reader_id, "created_at": now()},
    )
    db.commit()
    return {"recorded": True}
