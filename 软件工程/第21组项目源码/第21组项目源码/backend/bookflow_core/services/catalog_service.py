from __future__ import annotations

from sqlalchemy import or_, select, func
from sqlalchemy.orm import Session
from bookflow_core.models import Book, BookCirculationStats, BookCopy, Loan, BookCategory, CirculationPolicy, COPY_STATUSES, Shelf, ShelfPosition, BookSubcategory, LibraryZone
from bookflow_core.core.exceptions import NotFoundError, BusinessRuleError
from bookflow_core.core.time import now
from bookflow_core.services.common import write_audit, write_status_event
from bookflow_core.services.statistics_service import UNAVAILABLE_COPY_STATUSES


COPY_STATUS_FILTERS = {
    "available": ["available"],
    "borrowed": ["borrowed"],
    "reserved": ["reserved"],
    "unavailable": list(UNAVAILABLE_COPY_STATUSES),
    "maintenance": ["maintenance"],
}


def _status_values(status: str) -> list[str]:
    return COPY_STATUS_FILTERS.get(status, [status])


def _clean_optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _cover_status(cover_url: str | None, requested_status: str | None = None) -> str:
    requested = _clean_optional_string(requested_status)
    if requested:
        return requested
    return "ready" if _clean_optional_string(cover_url) else "missing"


def get_active_policy(db: Session) -> CirculationPolicy:
    policy = db.scalar(select(CirculationPolicy).where(CirculationPolicy.is_active == True).order_by(CirculationPolicy.id.desc()))
    if not policy:
        raise BusinessRuleError("No active circulation policy found.")
    return policy


def classify_book(stats: BookCirculationStats, policy: CirculationPolicy) -> str:
    if (stats.borrow_90d or 0) >= int(policy.hot_borrow_90d_threshold or 0) or (stats.reserve_90d or 0) >= int(policy.hot_reserve_90d_threshold or 0):
        return "热门"
    if (stats.borrow_365d or 0) <= int(policy.cold_borrow_365d_threshold or 0) and (stats.days_since_last_borrow or 0) >= int(policy.cold_days_since_last_borrow_threshold or 0):
        return "冷门"
    return "普通"


def get_or_create_book_stats(db: Session, book_id: int) -> BookCirculationStats:
    stats = db.scalar(select(BookCirculationStats).where(BookCirculationStats.book_id == book_id))
    if not stats:
        from bookflow_core.core.time import now
        stats = BookCirculationStats(
            book_id=book_id,
            total_copies=0,
            available_copies=0,
            active_loans=0,
            reservations_waiting=0,
            borrow_90d=0,
            reserve_90d=0,
            borrow_365d=0,
            days_since_last_borrow=9999,
            circulation_type="普通",
            computed_at=now(),
        )
        db.add(stats)
        db.flush()
    return stats


def recalculate_book_circulation_type(db: Session, book_id: int) -> Book:
    book = db.get(Book, book_id)
    if not book:
        raise NotFoundError("Book not found.", details={"book_id": book_id})
    policy = get_active_policy(db)
    stats = get_or_create_book_stats(db, book_id)
    stats.circulation_type = classify_book(stats, policy)
    book.circulation_type = stats.circulation_type
    return book


def recalculate_all_circulation_types(db: Session) -> int:
    policy = get_active_policy(db) if db.scalar(select(CirculationPolicy)) else None
    if not policy:
        return 0
    count = 0
    for book in db.scalars(select(Book)).all():
        stats = get_or_create_book_stats(db, book.id)
        stats.circulation_type = classify_book(stats, policy)
        book.circulation_type = stats.circulation_type
        count += 1
    return count


def recalculate_book_inventory(db: Session, book_id: int) -> Book:
    book = db.get(Book, book_id)
    if not book:
        raise NotFoundError("Book not found.")
    total = db.scalar(select(func.count(BookCopy.id)).where(BookCopy.book_id == book_id)) or 0
    available = db.scalar(select(func.count(BookCopy.id)).where(BookCopy.book_id == book_id, BookCopy.copy_status == "available")) or 0
    active_loans = db.scalar(select(func.count(Loan.id)).where(Loan.book_id == book_id, Loan.status.in_(["active", "overdue"]))) or 0
    from datetime import date, timedelta
    from bookflow_core.core.time import today
    as_of = today()
    ninety_days_ago = as_of - timedelta(days=90)
    year_ago = as_of - timedelta(days=365)
    borrow_90d = db.scalar(select(func.count(Loan.id)).where(Loan.book_id == book_id, Loan.borrowed_at >= ninety_days_ago)) or 0
    borrow_365d = db.scalar(select(func.count(Loan.id)).where(Loan.book_id == book_id, Loan.borrowed_at >= year_ago)) or 0
    last_borrow = db.scalar(select(func.max(Loan.borrowed_at)).where(Loan.book_id == book_id))
    from bookflow_core.models import Reservation
    from bookflow_core.services.statistics_service import ACTIVE_RESERVATION_STATUSES
    reservations_waiting = db.scalar(select(func.count(Reservation.id)).where(Reservation.book_id == book_id, Reservation.status.in_(ACTIVE_RESERVATION_STATUSES))) or 0
    stats = get_or_create_book_stats(db, book_id)
    stats.total_copies = int(total)
    stats.available_copies = int(available)
    stats.active_loans = int(active_loans)
    stats.borrow_90d = int(borrow_90d)
    stats.borrow_365d = int(borrow_365d)
    stats.reservations_waiting = int(reservations_waiting)
    if last_borrow:
        if hasattr(last_borrow, "date"):
            last_borrow_date = last_borrow.date()
        elif isinstance(last_borrow, date):
            last_borrow_date = last_borrow
        else:
            last_borrow_date = date.fromisoformat(str(last_borrow)[:10])
        stats.days_since_last_borrow = max(0, (as_of - last_borrow_date).days)
    return book


def list_categories(db: Session, *, limit: int = 200, offset: int = 0) -> dict:
    stmt = select(BookCategory)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(BookCategory.sort_order, BookCategory.id).offset(offset).limit(limit)).all()
    return {
        "items": [
            {
                "id": row.id,
                "category_code": row.category_code,
                "category_name": row.category_name,
                "subcategory_examples": row.subcategory_examples,
                "book_title_count": row.book_title_count,
                "copy_count": row.copy_count,
                "primary_zone_id": row.primary_zone_id,
                "primary_zone_code": row.primary_zone_code,
                "clc_hint": row.clc_hint,
            }
            for row in rows
        ],
        "total": int(total),
        "limit": limit,
        "offset": offset,
    }


def list_subcategories(db: Session, *, category_id: int | None = None, category_code: str | None = None, limit: int = 500, offset: int = 0) -> dict:
    stmt = select(BookSubcategory)
    if category_id is not None:
        stmt = stmt.where(BookSubcategory.category_id == category_id)
    if category_code:
        stmt = stmt.where(BookSubcategory.category_code == category_code)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(BookSubcategory.category_code, BookSubcategory.sort_order, BookSubcategory.id).offset(offset).limit(limit)).all()
    return {
        "items": [
            {
                "id": row.id,
                "subcategory_code": row.subcategory_code,
                "subcategory_name": row.subcategory_name,
                "category_id": row.category_id,
                "category_code": row.category_code,
                "category_name": row.category_name,
                "allocated_book_title_count": row.allocated_book_title_count,
            }
            for row in rows
        ],
        "total": int(total),
        "limit": limit,
        "offset": offset,
    }


def list_books(
    db: Session,
    *,
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
    limit: int = 50,
    offset: int = 0,
) -> dict:
    stmt = select(Book).outerjoin(BookCategory, Book.category_id == BookCategory.id).outerjoin(BookSubcategory, Book.subcategory_id == BookSubcategory.id)
    if circulation_type:
        stmt = stmt.where(Book.circulation_type == circulation_type)
    if keyword:
        stmt = stmt.where(or_(Book.title.contains(keyword), Book.author.contains(keyword), Book.book_code.contains(keyword), Book.isbn.contains(keyword), Book.call_number.contains(keyword), Book.clc_code.contains(keyword)))
    if category_id is not None:
        stmt = stmt.where(Book.category_id == category_id)
    if category_code:
        stmt = stmt.where(or_(Book.category_code == category_code, BookCategory.category_code == category_code))
    if subcategory_id is not None:
        stmt = stmt.where(Book.subcategory_id == subcategory_id)
    if subcategory_code:
        stmt = stmt.where(or_(Book.subcategory_code == subcategory_code, BookSubcategory.subcategory_code == subcategory_code))
    if copy_status:
        stmt = stmt.where(Book.id.in_(select(BookCopy.book_id).where(BookCopy.copy_status.in_(_status_values(copy_status)))))
    if zone_id is not None or zone_code:
        copy_zone_filter = []
        book_zone_filter = []
        if zone_id is not None:
            copy_zone_filter.extend([BookCopy.current_zone_id == zone_id, BookCopy.home_zone_id == zone_id])
            book_zone_filter.append(Book.primary_zone_id == zone_id)
        if zone_code:
            copy_zone_filter.extend([BookCopy.current_zone_code == zone_code, BookCopy.home_zone_code == zone_code])
            book_zone_filter.extend([Book.primary_zone_code == zone_code, BookCategory.primary_zone_code == zone_code])
        copy_books = select(BookCopy.book_id).where(or_(*copy_zone_filter)) if copy_zone_filter else select(BookCopy.book_id).where(False)
        stmt = stmt.where(or_(*(book_zone_filter + [Book.id.in_(copy_books)])))
    if is_active is not None:
        stmt = stmt.where(Book.status == ("active" if is_active else "inactive"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(Book.id).offset(offset).limit(limit)).all()
    return {"items": items, "total": int(total), "limit": limit, "offset": offset}


def _copy_status_counts(db: Session, book_id: int) -> dict[str, int]:
    counts = {status: 0 for status in ["available", "borrowed", "reserved", "unavailable"]}
    rows = db.execute(
        select(BookCopy.copy_status, func.count(BookCopy.id))
        .where(BookCopy.book_id == book_id)
        .group_by(BookCopy.copy_status)
    ).all()
    for status, count in rows:
        value = int(count or 0)
        if status in UNAVAILABLE_COPY_STATUSES:
            counts["unavailable"] += value
        elif status in counts:
            counts[str(status)] = value
    return counts


def _primary_zone_for_book(db: Session, book: Book) -> LibraryZone | None:
    if book.primary_zone_id:
        zone = db.get(LibraryZone, book.primary_zone_id)
        if zone:
            return zone
    if book.primary_zone_code:
        zone = db.scalar(select(LibraryZone).where(LibraryZone.zone_code == book.primary_zone_code))
        if zone:
            return zone
    if book.category and book.category.primary_zone_id:
        zone = db.get(LibraryZone, book.category.primary_zone_id)
        if zone:
            return zone
    row = db.execute(
        select(Shelf.zone_id, func.count(BookCopy.id))
        .join(ShelfPosition, BookCopy.current_position_id == ShelfPosition.id)
        .join(Shelf, ShelfPosition.shelf_id == Shelf.id)
        .where(BookCopy.book_id == book.id)
        .group_by(Shelf.zone_id)
        .order_by(func.count(BookCopy.id).desc())
        .limit(1)
    ).first()
    return db.get(LibraryZone, row[0]) if row else None


def book_list_item_to_dict(db: Session, book: Book) -> dict:
    stats = get_or_create_book_stats(db, book.id)
    data = book_to_dict(book, stats)
    copy_stats = _copy_status_counts(db, book.id)
    zone = _primary_zone_for_book(db, book)
    data.update(
        {
            "copy_stats": copy_stats,
            "borrowed_copies": copy_stats["borrowed"],
            "reserved_copies": copy_stats["reserved"],
            "unavailable_copies": copy_stats["unavailable"],
            "primary_zone": {
                "zone_id": zone.id if zone else None,
                "zone_code": zone.zone_code if zone else None,
                "zone_name": zone.zone_name if zone else None,
            },
        }
    )
    return data


def list_hot_books(db: Session, limit: int = 10) -> list[Book]:
    rows = db.execute(
        select(Book, BookCirculationStats)
        .join(BookCirculationStats, BookCirculationStats.book_id == Book.id)
        .where(BookCirculationStats.circulation_type == "热门")
        .order_by(BookCirculationStats.borrow_90d.desc(), BookCirculationStats.reserve_90d.desc(), Book.id)
        .limit(limit)
    ).all()
    books: list[Book] = []
    for book, stats in rows:
        book._bookflow_stats = stats
        books.append(book)
    return books


def list_cold_books(db: Session, limit: int = 10) -> list[Book]:
    rows = db.execute(
        select(Book, BookCirculationStats)
        .join(BookCirculationStats, BookCirculationStats.book_id == Book.id)
        .where(BookCirculationStats.circulation_type == "冷门")
        .order_by(BookCirculationStats.days_since_last_borrow.desc(), Book.id)
        .limit(limit)
    ).all()
    books: list[Book] = []
    for book, stats in rows:
        book._bookflow_stats = stats
        books.append(book)
    return books


def get_copy_by_code(db: Session, copy_code: str) -> BookCopy:
    copy = db.scalar(select(BookCopy).where(BookCopy.copy_code == copy_code))
    if not copy:
        raise NotFoundError("Copy not found.", details={"copy_code": copy_code})
    return copy


def get_book(db: Session, book_id: int) -> Book:
    book = db.get(Book, book_id)
    if not book:
        raise NotFoundError("Book not found.", code="BOOK_NOT_FOUND", details={"book_id": book_id})
    return book


def _category_by_id_or_code(db: Session, *, category_id: int | None = None, category_code: str | None = None) -> BookCategory:
    stmt = select(BookCategory)
    if category_id is not None:
        stmt = stmt.where(BookCategory.id == category_id)
    elif category_code:
        stmt = stmt.where(BookCategory.category_code == category_code)
    else:
        raise BusinessRuleError("BookCategory is required.", code="VALIDATION_ERROR")
    row = db.scalar(stmt)
    if not row:
        raise NotFoundError("BookCategory not found.", code="VALIDATION_ERROR", details={"category_id": category_id, "category_code": category_code})
    return row


def _subcategory_by_id_or_code(
    db: Session,
    *,
    category: BookCategory,
    subcategory_id: int | None = None,
    subcategory_code: str | None = None,
) -> BookSubcategory | None:
    if subcategory_id is None and not subcategory_code:
        return None
    stmt = select(BookSubcategory).where(BookSubcategory.category_id == category.id)
    if subcategory_id is not None:
        stmt = stmt.where(BookSubcategory.id == subcategory_id)
    else:
        stmt = stmt.where(BookSubcategory.subcategory_code == subcategory_code)
    row = db.scalar(stmt)
    if not row:
        raise NotFoundError("BookSubcategory not found in category.", code="VALIDATION_ERROR", details={"subcategory_id": subcategory_id, "subcategory_code": subcategory_code})
    return row


def _book_sequence(book_code: str) -> int:
    try:
        return int(book_code.rsplit("-", 1)[1])
    except (ValueError, IndexError):
        return 0


def next_book_code(db: Session, category_code: str) -> str:
    prefix = f"BK-{category_code}-"
    rows = db.scalars(select(Book.book_code).where(Book.book_code.like(f"{prefix}%"))).all()
    next_seq = max([_book_sequence(code) for code in rows] or [0]) + 1
    return f"{prefix}{next_seq}"


def parse_book_code(book_code: str) -> tuple[str, int]:
    parts = book_code.split("-")
    if len(parts) != 3 or parts[0] != "BK":
        raise BusinessRuleError("Invalid book_code format.", code="VALIDATION_ERROR", details={"book_code": book_code})
    return parts[1], int(parts[2])


def next_copy_code(db: Session, book: Book) -> str:
    category_code, book_seq = parse_book_code(book.book_code)
    prefix = f"CP-{category_code}-{book_seq}-"
    rows = db.scalars(select(BookCopy.copy_code).where(BookCopy.copy_code.like(f"{prefix}%"))).all()
    next_seq = max([_book_sequence(code) for code in rows] or [0]) + 1
    return f"{prefix}{next_seq}"


def create_book(
    db: Session,
    *,
    title: str,
    category_id: int | None = None,
    category_code: str | None = None,
    subcategory_id: int | None = None,
    subcategory_code: str | None = None,
    book_code: str | None = None,
    source_book_id: int | None = None,
    author: str = "",
    publisher: str = "",
    publish_year: int | None = None,
    isbn: str = "",
    language: str | None = "中文",
    edition: str | None = None,
    pages: int | None = None,
    price_yuan: float | None = None,
    copy_count: int | None = None,
    primary_zone_id: int | None = None,
    primary_zone_code: str | None = None,
    recommended_reader: str | None = None,
    introduction: str = "",
    keywords: str = "",
    circulation_type: str = "普通",
    data_note: str | None = None,
    clc_hint: str | None = None,
    clc_code: str | None = None,
    call_number: str | None = None,
    isbn_status: str | None = None,
    bibliographic_status: str | None = None,
    book_source_class: str | None = None,
    cover_url: str | None = None,
    cover_source: str | None = None,
    cover_status: str | None = None,
    status: str | None = None,
    is_active: bool = True,
    initial_copies: int = 0,
    actor_type: str = "admin",
    actor_id: str = "admin",
    commit: bool = True,
) -> Book:
    try:
        category = _category_by_id_or_code(db, category_id=category_id, category_code=category_code)
        subcategory = _subcategory_by_id_or_code(db, category=category, subcategory_id=subcategory_id, subcategory_code=subcategory_code)
        code = book_code or next_book_code(db, category.category_code)
        if not code.startswith(f"BK-{category.category_code}-"):
            raise BusinessRuleError("book_code does not match category.", code="VALIDATION_ERROR", details={"book_code": code, "category_code": category.category_code})
        if db.scalar(select(Book).where(Book.book_code == code)):
            raise BusinessRuleError("book_code already exists.", code="VALIDATION_ERROR", details={"book_code": code})
        if circulation_type not in {"热门", "普通", "冷门"}:
            raise BusinessRuleError("Invalid circulation_type.", code="VALIDATION_ERROR", details={"circulation_type": circulation_type})
        zone = db.get(LibraryZone, primary_zone_id) if primary_zone_id else None
        if not zone and primary_zone_code:
            zone = db.scalar(select(LibraryZone).where(LibraryZone.zone_code == primary_zone_code))
        clean_cover_url = _clean_optional_string(cover_url)
        clean_cover_source = _clean_optional_string(cover_source) or ("manual" if clean_cover_url else None)
        book = Book(
            source_book_id=source_book_id,
            book_code=code,
            category_id=category.id,
            category_code=category.category_code,
            category_name=category.category_name,
            subcategory_id=subcategory.id if subcategory else None,
            subcategory_code=subcategory.subcategory_code if subcategory else None,
            subcategory_name=subcategory.subcategory_name if subcategory else None,
            clc_hint=clc_hint if clc_hint is not None else category.clc_hint,
            title=title,
            author=author,
            publisher=publisher,
            publish_year=publish_year,
            isbn=isbn,
            language=language,
            edition=edition,
            pages=pages,
            price_yuan=price_yuan,
            copy_count_snapshot=str(copy_count) if copy_count is not None else None,
            primary_zone_id=zone.id if zone else primary_zone_id,
            primary_zone_code=zone.zone_code if zone else primary_zone_code,
            recommended_reader=recommended_reader,
            introduction=introduction,
            keywords=keywords,
            circulation_type=circulation_type,
            data_note=data_note,
            clc_code=clc_code,
            call_number=call_number,
            isbn_status=isbn_status,
            bibliographic_status=bibliographic_status,
            book_source_class=book_source_class,
            cover_url=clean_cover_url,
            cover_source=clean_cover_source,
            cover_status=_cover_status(clean_cover_url, cover_status),
            cover_updated_at=now() if clean_cover_url or cover_status is not None else None,
            status=status or ("active" if is_active else "inactive"),
        )
        db.add(book)
        db.flush()
        stats = get_or_create_book_stats(db, book.id)
        stats.circulation_type = circulation_type
        if initial_copies:
            create_book_copies(db, book.id, count=initial_copies, actor_type=actor_type, actor_id=actor_id, commit=False)
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="create_book", target_table="books", target_id=book.book_code, detail={"title": title})
        if commit:
            db.commit()
            db.refresh(book)
        return book
    except Exception:
        if commit:
            db.rollback()
        raise


def update_book(
    db: Session,
    book_id: int,
    *,
    title: str | None = None,
    category_id: int | None = None,
    category_code: str | None = None,
    subcategory_id: int | None = None,
    subcategory_code: str | None = None,
    clc_hint: str | None = None,
    author: str | None = None,
    publisher: str | None = None,
    publish_year: int | None = None,
    isbn: str | None = None,
    language: str | None = None,
    edition: str | None = None,
    pages: int | None = None,
    price_yuan: float | None = None,
    copy_count: int | None = None,
    primary_zone_id: int | None = None,
    primary_zone_code: str | None = None,
    recommended_reader: str | None = None,
    introduction: str | None = None,
    keywords: str | None = None,
    circulation_type: str | None = None,
    data_note: str | None = None,
    clc_code: str | None = None,
    call_number: str | None = None,
    isbn_status: str | None = None,
    bibliographic_status: str | None = None,
    book_source_class: str | None = None,
    cover_url: str | None = None,
    cover_source: str | None = None,
    cover_status: str | None = None,
    status: str | None = None,
    is_active: bool | None = None,
    actor_type: str = "admin",
    actor_id: str = "admin",
    commit: bool = True,
) -> Book:
    try:
        book = get_book(db, book_id)
        before = book_to_dict(book)
        if category_id is not None or category_code:
            category = _category_by_id_or_code(db, category_id=category_id, category_code=category_code)
            book.category_id = category.id
            book.category_code = category.category_code
            book.category_name = category.category_name
        else:
            category = db.get(BookCategory, book.category_id)
        if subcategory_id is not None or subcategory_code:
            subcategory = _subcategory_by_id_or_code(db, category=category, subcategory_id=subcategory_id, subcategory_code=subcategory_code)
            book.subcategory_id = subcategory.id if subcategory else None
            book.subcategory_code = subcategory.subcategory_code if subcategory else None
            book.subcategory_name = subcategory.subcategory_name if subcategory else None
        if primary_zone_id is not None or primary_zone_code:
            zone = db.get(LibraryZone, primary_zone_id) if primary_zone_id else None
            if not zone and primary_zone_code:
                zone = db.scalar(select(LibraryZone).where(LibraryZone.zone_code == primary_zone_code))
            book.primary_zone_id = zone.id if zone else primary_zone_id
            book.primary_zone_code = zone.zone_code if zone else primary_zone_code
        for name, value in {
            "title": title,
            "clc_hint": clc_hint,
            "author": author,
            "publisher": publisher,
            "publish_year": publish_year,
            "isbn": isbn,
            "language": language,
            "edition": edition,
            "pages": pages,
            "price_yuan": price_yuan,
            "copy_count_snapshot": str(copy_count) if copy_count is not None else None,
            "recommended_reader": recommended_reader,
            "introduction": introduction,
            "keywords": keywords,
            "circulation_type": circulation_type,
            "data_note": data_note,
            "clc_code": clc_code,
            "call_number": call_number,
            "isbn_status": isbn_status,
            "bibliographic_status": bibliographic_status,
            "book_source_class": book_source_class,
            "status": status or ("active" if is_active else "inactive" if is_active is not None else None),
        }.items():
            if value is not None:
                if name == "circulation_type" and value not in {"热门", "普通", "冷门"}:
                    raise BusinessRuleError("Invalid circulation_type.", code="VALIDATION_ERROR", details={"circulation_type": value})
                if name == "circulation_type":
                    get_or_create_book_stats(db, book.id).circulation_type = value
                    book.circulation_type = value
                else:
                    setattr(book, name, value)
        if cover_url is not None or cover_source is not None or cover_status is not None:
            if cover_url is not None:
                book.cover_url = _clean_optional_string(cover_url)
            if cover_source is not None:
                book.cover_source = _clean_optional_string(cover_source) or ("manual" if book.cover_url else None)
            if cover_status is not None or cover_url is not None:
                book.cover_status = _cover_status(book.cover_url, cover_status)
            if book.cover_url and not book.cover_source:
                book.cover_source = "manual"
            book.cover_updated_at = now()
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="update_book", target_table="books", target_id=book.book_code, detail={"before": before, "after": book_to_dict(book)})
        if commit:
            db.commit()
            db.refresh(book)
        return book
    except Exception:
        if commit:
            db.rollback()
        raise


def _resolve_position_context(db: Session, position_id: int | None) -> tuple[ShelfPosition | None, Shelf | None, LibraryZone | None]:
    if position_id is None:
        return None, None, None
    position = db.get(ShelfPosition, position_id)
    if not position:
        raise NotFoundError("Shelf position not found.", code="VALIDATION_ERROR", details={"current_position_id": position_id})
    shelf = db.get(Shelf, position.shelf_id) if position.shelf_id else None
    zone = db.get(LibraryZone, shelf.zone_id) if shelf and shelf.zone_id else None
    return position, shelf, zone


def _apply_copy_location(copy: BookCopy, position: ShelfPosition | None, shelf: Shelf | None, zone: LibraryZone | None, *, set_home_if_empty: bool = False) -> None:
    copy.current_position_id = position.id if position else None
    copy.current_shelf_id = shelf.id if shelf else None
    copy.shelf_code = shelf.shelf_code if shelf else None
    copy.current_zone_id = zone.id if zone else None
    copy.current_zone_code = zone.zone_code if zone else None
    # The ORM relationship uses the name shelf_position; expose position_code through ShelfPosition instead of mutating that relationship.
    if set_home_if_empty and copy.home_zone_id is None and copy.home_shelf_id is None:
        copy.home_position_id = position.id if position else None
        copy.home_shelf_id = shelf.id if shelf else None
        copy.home_shelf_code = shelf.shelf_code if shelf else None
        copy.home_zone_id = zone.id if zone else None
        copy.home_zone_code = zone.zone_code if zone else None
        copy.home_shelf_position = position.position_code if position else None


def create_book_copies(
    db: Session,
    book_id: int,
    *,
    count: int,
    copy_code: str | None = None,
    barcode: str | None = None,
    copy_no: int | None = None,
    current_position_id: int | None = None,
    home_position_id: int | None = None,
    copy_status: str = "available",
    collection_type: str | None = "普通外借",
    can_borrow_outside_library: bool | None = None,
    status_code: str | None = None,
    status_name: str | None = None,
    acquisition_date=None,
    acquisition_source: str | None = None,
    condition_level: str | None = None,
    asset_price_yuan: float | None = None,
    remark: str = "",
    actor_type: str = "admin",
    actor_id: str = "admin",
    commit: bool = True,
) -> list[BookCopy]:
    if count < 1 or count > 100:
        raise BusinessRuleError("Copy batch count must be between 1 and 100.", code="VALIDATION_ERROR", details={"count": count})
    if copy_status not in COPY_STATUSES:
        raise BusinessRuleError("Invalid copy status.", code="COPY_STATUS_INVALID", details={"status": copy_status})
    if copy_status in UNAVAILABLE_COPY_STATUSES and not remark:
        raise BusinessRuleError("Unavailable copies require a remark.", code="VALIDATION_ERROR")
    try:
        if count > 1 and (copy_code or barcode or copy_no is not None):
            raise BusinessRuleError("copy_code/barcode/copy_no can only be specified when count is 1.", code="VALIDATION_ERROR")
        book = get_book(db, book_id)
        position, shelf, zone = _resolve_position_context(db, current_position_id)
        home_position, home_shelf, home_zone = _resolve_position_context(db, home_position_id) if home_position_id else (position, shelf, zone)
        created: list[BookCopy] = []
        for _ in range(count):
            code = copy_code or next_copy_code(db, book)
            if db.scalar(select(BookCopy).where(BookCopy.copy_code == code)):
                raise BusinessRuleError("copy_code already exists.", code="VALIDATION_ERROR", details={"copy_code": code})
            barcode_value = barcode or code
            if db.scalar(select(BookCopy).where(BookCopy.barcode == barcode_value)):
                raise BusinessRuleError("barcode already exists.", code="VALIDATION_ERROR", details={"barcode": barcode_value})
            copy = BookCopy(
                copy_code=code,
                barcode=barcode_value,
                book_id=book.id,
                source_book_id=book.source_book_id,
                copy_no=copy_no,
                category_code=book.category_code or (book.category.category_code if book.category else None),
                subcategory_code=book.subcategory_code or (book.subcategory.subcategory_code if book.subcategory else None),
                copy_status=copy_status,
                status_code=status_code or copy_status,
                status_name=status_name or copy_status,
                collection_type=collection_type or "普通外借",
                can_borrow_outside_library=can_borrow_outside_library if can_borrow_outside_library is not None else copy_status == "available",
                acquisition_date=acquisition_date,
                acquisition_source=acquisition_source,
                condition_level=condition_level,
                asset_price_yuan=asset_price_yuan,
                remark=remark,
            )
            _apply_copy_location(copy, home_position, home_shelf, home_zone, set_home_if_empty=True)
            _apply_copy_location(copy, position, shelf, zone)
            db.add(copy)
            db.flush()
            write_status_event(db, copy, "", copy_status, "create_book_copy", actor_type, actor_id)
            created.append(copy)
        recalculate_book_inventory(db, book.id)
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="create_book_copies", target_table="book_copies", target_id=book.book_code, detail={"count": count, "copy_status": copy_status})
        if commit:
            db.commit()
            for copy in created:
                db.refresh(copy)
        return created
    except Exception:
        if commit:
            db.rollback()
        raise


def update_copy_status(db: Session, copy_code: str, new_status: str, *, reason: str, actor_type: str, actor_id: str, commit: bool = True) -> BookCopy:
    if new_status not in COPY_STATUSES:
        raise BusinessRuleError("Invalid copy status.", code="COPY_STATUS_INVALID", details={"new_status": new_status})
    try:
        copy = get_copy_by_code(db, copy_code)
        old = copy.copy_status
        if old == new_status:
            return copy
        if old == "borrowed" and new_status in UNAVAILABLE_COPY_STATUSES and actor_type != "super_admin":
            raise BusinessRuleError("Borrowed copy cannot be directly disabled.", code="COPY_BORROWED_CANNOT_DISABLE", details={"copy_code": copy_code})
        copy.copy_status = new_status
        copy.status_code = new_status
        status_names = {"available": "在馆可借", "borrowed": "已借出", "reserved": "预约保留", "unavailable": "暂不可借", "maintenance": "维护中", "lost": "遗失", "discarded": "剔旧"}
        copy.status_name = status_names.get(new_status, new_status)
        copy.can_borrow_outside_library = new_status == "available"
        write_status_event(db, copy, old, new_status, reason, actor_type, actor_id)
        db.flush()
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="update_copy_status", target_table="book_copies", target_id=copy.copy_code, detail={"old_status": old, "new_status": new_status, "reason": reason})
        recalculate_book_inventory(db, copy.book_id)
        if commit:
            db.commit()
            db.refresh(copy)
        return copy
    except Exception:
        if commit:
            db.rollback()
        raise


def update_copy_status_by_id(db: Session, copy_id: int, new_status: str, *, reason: str, actor_type: str, actor_id: str, commit: bool = True) -> BookCopy:
    copy = db.get(BookCopy, copy_id)
    if not copy:
        raise NotFoundError("Copy not found.", code="COPY_NOT_FOUND", details={"copy_id": copy_id})
    return update_copy_status(db, copy.copy_code, new_status, reason=reason, actor_type=actor_type, actor_id=actor_id, commit=commit)


def update_copy_location(db: Session, copy_id: int, current_position_id: int, *, reason: str = "manual_location_update", actor_type: str, actor_id: str, commit: bool = True) -> BookCopy:
    try:
        copy = db.get(BookCopy, copy_id)
        if not copy:
            raise NotFoundError("Copy not found.", code="COPY_NOT_FOUND", details={"copy_id": copy_id})
        old_position = db.get(ShelfPosition, copy.current_position_id) if copy.current_position_id else None
        position, shelf, zone = _resolve_position_context(db, current_position_id)
        before = {
            "current_position_id": copy.current_position_id,
            "current_shelf_id": copy.current_shelf_id,
            "current_zone_id": copy.current_zone_id,
            "shelf_code": copy.shelf_code,
            "shelf_position": old_position.position_code if old_position else None,
        }
        from_position_id = copy.current_position_id
        from_zone_id = copy.current_zone_id
        _apply_copy_location(copy, position, shelf, zone)
        from bookflow_core.models import CopyLocationEvent
        db.add(CopyLocationEvent(copy_id=copy.id, from_position_id=from_position_id, to_position_id=position.id if position else None, from_zone_id=from_zone_id, to_zone_id=zone.id if zone else None, reason=reason, actor_type=actor_type, actor_code=actor_id))
        write_audit(db, actor_type=actor_type, actor_id=actor_id, action="update_copy_location", target_table="book_copies", target_id=copy.copy_code, detail={"before": before, "after": {"current_position_id": copy.current_position_id, "current_shelf_id": copy.current_shelf_id, "current_zone_id": copy.current_zone_id, "shelf_code": copy.shelf_code, "shelf_position": position.position_code if position else None}})
        if commit:
            db.commit()
            db.refresh(copy)
        return copy
    except Exception:
        if commit:
            db.rollback()
        raise


def copy_to_dict(db: Session, copy: BookCopy, *, include_book: bool = True) -> dict:
    book = db.get(Book, copy.book_id) if include_book else None
    position = db.get(ShelfPosition, copy.current_position_id) if copy.current_position_id else None
    shelf = db.get(Shelf, copy.current_shelf_id) if copy.current_shelf_id else None
    if shelf is None and position is not None and position.shelf_id:
        shelf = db.get(Shelf, position.shelf_id)
    zone = db.get(LibraryZone, copy.current_zone_id) if copy.current_zone_id else None
    if zone is None and shelf is not None and shelf.zone_id:
        zone = db.get(LibraryZone, shelf.zone_id)
    home_position = db.get(ShelfPosition, copy.home_position_id) if copy.home_position_id else None
    home_shelf = db.get(Shelf, copy.home_shelf_id) if copy.home_shelf_id else None
    home_zone = db.get(LibraryZone, copy.home_zone_id) if copy.home_zone_id else None
    active_record = db.scalar(select(Loan).where(Loan.copy_id == copy.id, Loan.status.in_(["active", "overdue"])).order_by(Loan.id.desc()))
    return {
        "id": copy.id,
        "source_copy_id": copy.source_copy_id,
        "copy_code": copy.copy_code,
        "source_book_id": copy.source_book_id,
        "copy_no": copy.copy_no,
        "barcode": copy.barcode,
        "category_code": copy.category_code,
        "subcategory_code": copy.subcategory_code,
        "collection_type": copy.collection_type,
        "can_borrow_outside_library": copy.can_borrow_outside_library,
        "status": copy.copy_status,
        "copy_status": copy.copy_status,
        "status_code": copy.status_code,
        "status_name": copy.status_name,
        "remark": copy.remark,
        "acquisition_date": str(copy.acquisition_date) if copy.acquisition_date else None,
        "acquisition_source": copy.acquisition_source,
        "condition_level": copy.condition_level,
        "asset_price_yuan": copy.asset_price_yuan,
        "book_id": copy.book_id,
        "book_code": book.book_code if book else None,
        "title": book.title if book else None,
        "author": book.author if book else None,
        "publisher": book.publisher if book else None,
        "publish_year": book.publish_year if book else None,
        "circulation_type": book.circulation_type if book else None,
        "cover_url": book.cover_url if book else None,
        "cover_source": book.cover_source if book else None,
        "cover_status": book.cover_status if book else None,
        "current_zone_id": copy.current_zone_id,
        "current_zone_code": copy.current_zone_code,
        "current_shelf_id": copy.current_shelf_id,
        "shelf_code": copy.shelf_code,
        "current_position_id": copy.current_position_id,
        "home_zone_id": copy.home_zone_id,
        "home_zone_code": copy.home_zone_code,
        "home_shelf_id": copy.home_shelf_id,
        "home_shelf_code": copy.home_shelf_code,
        "home_position_id": copy.home_position_id,
        "home_shelf_position": copy.home_shelf_position,
        "location": {
            "zone_id": zone.id if zone else copy.current_zone_id,
            "zone_code": zone.zone_code if zone else copy.current_zone_code,
            "zone_name": zone.zone_name if zone else None,
            "shelf_id": shelf.id if shelf else copy.current_shelf_id,
            "shelf_code": shelf.shelf_code if shelf else copy.shelf_code,
            "floor": shelf.floor if shelf else None,
            "current_position_id": copy.current_position_id,
            "current_shelf_id": copy.current_shelf_id,
            "current_zone_id": copy.current_zone_id,
            "position_code": position.position_code if position else None,
            "shelf_position": position.position_code if position else copy.home_shelf_position,
        },
        "home_location": {
            "zone_id": home_zone.id if home_zone else copy.home_zone_id,
            "zone_code": home_zone.zone_code if home_zone else copy.home_zone_code,
            "zone_name": home_zone.zone_name if home_zone else None,
            "shelf_id": home_shelf.id if home_shelf else copy.home_shelf_id,
            "shelf_code": home_shelf.shelf_code if home_shelf else copy.home_shelf_code,
            "position_id": copy.home_position_id,
            "position_code": home_position.position_code if home_position else copy.home_shelf_position,
        },
        "current_borrow_summary": {
            "loan_id": active_record.id,
            "reader_id": active_record.reader_id,
            "due_at": str(active_record.due_at),
            "status": active_record.status,
        }
        if active_record
        else None,
    }

def list_book_copies(db: Session, book_id: int, *, limit: int = 100, offset: int = 0) -> dict:
    get_book(db, book_id)
    stmt = select(BookCopy).where(BookCopy.book_id == book_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(BookCopy.id).offset(offset).limit(limit)).all()
    return {"items": [copy_to_dict(db, row) for row in rows], "total": int(total), "limit": limit, "offset": offset, **({"empty_state": True} if total == 0 else {})}


def list_copies(
    db: Session,
    *,
    book_id: int | None = None,
    status: str | None = None,
    zone: str | None = None,
    shelf: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    stmt = select(BookCopy).join(Book, BookCopy.book_id == Book.id).outerjoin(Shelf, BookCopy.current_shelf_id == Shelf.id).outerjoin(LibraryZone, BookCopy.current_zone_id == LibraryZone.id)
    if book_id is not None:
        stmt = stmt.where(BookCopy.book_id == book_id)
    if status:
        stmt = stmt.where(BookCopy.copy_status.in_(_status_values(status)))
    if zone:
        stmt = stmt.where(or_(LibraryZone.zone_code == zone, LibraryZone.zone_name.contains(zone)))
    if shelf:
        stmt = stmt.where(Shelf.shelf_code == shelf)
    if keyword:
        stmt = stmt.where(or_(BookCopy.copy_code.contains(keyword), BookCopy.barcode.contains(keyword), Book.title.contains(keyword), Book.book_code.contains(keyword)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(BookCopy.id).offset(offset).limit(limit)).all()
    return {"items": [copy_to_dict(db, row) for row in rows], "total": int(total), "limit": limit, "offset": offset, **({"empty_state": True} if total == 0 else {})}


def book_to_dict(book: Book, stats: BookCirculationStats | None = None) -> dict:
    stats = stats or getattr(book, "_bookflow_stats", None)
    return {
        "id": book.id,
        "source_book_id": book.source_book_id,
        "book_code": book.book_code,
        "category_id": book.category_id,
        "category_code": book.category_code or (book.category.category_code if book.category else None),
        "category_name": book.category_name or (book.category.category_name if book.category else None),
        "subcategory_id": book.subcategory_id,
        "subcategory_code": book.subcategory_code or (book.subcategory.subcategory_code if book.subcategory else None),
        "subcategory_name": book.subcategory_name or (book.subcategory.subcategory_name if book.subcategory else None),
        "clc_hint": book.clc_hint,
        "title": book.title,
        "author": book.author,
        "publisher": book.publisher,
        "publish_year": book.publish_year,
        "isbn": book.isbn,
        "language": book.language,
        "edition": book.edition,
        "pages": book.pages,
        "price_yuan": book.price_yuan,
        "copy_count_snapshot": book.copy_count_snapshot,
        "primary_zone_id": book.primary_zone_id,
        "primary_zone_code": book.primary_zone_code,
        "recommended_reader": book.recommended_reader,
        "keywords": book.keywords,
        "introduction": book.introduction,
        "data_note": book.data_note,
        "clc_code": book.clc_code,
        "call_number": book.call_number,
        "isbn_status": book.isbn_status,
        "bibliographic_status": book.bibliographic_status,
        "book_source_class": book.book_source_class,
        "cover_url": book.cover_url,
        "cover_source": book.cover_source,
        "cover_status": book.cover_status,
        "cover_updated_at": str(book.cover_updated_at) if book.cover_updated_at else None,
        "total_copies": stats.total_copies if stats else book.copy_count_snapshot,
        "available_copies": stats.available_copies if stats else None,
        "borrow_90d": stats.borrow_90d if stats else None,
        "reserve_90d": stats.reserve_90d if stats else None,
        "borrow_365d": stats.borrow_365d if stats else None,
        "days_since_last_borrow": stats.days_since_last_borrow if stats else None,
        "circulation_type": book.circulation_type,
        "status": book.status,
    }

def book_detail(db: Session, book_id: int) -> dict:
    book = get_book(db, book_id)
    data = book_to_dict(book, get_or_create_book_stats(db, book.id))
    data["copy_stats"] = {
        status: int(db.scalar(select(func.count(BookCopy.id)).where(BookCopy.book_id == book.id, BookCopy.copy_status.in_(_status_values(status)))) or 0)
        for status in ["available", "borrowed", "reserved", "unavailable"]
    }
    zone = _primary_zone_for_book(db, book)
    data["primary_zone"] = {
        "zone_id": zone.id if zone else None,
        "zone_code": zone.zone_code if zone else None,
        "zone_name": zone.zone_name if zone else None,
    }
    data["sample_copies"] = [copy_to_dict(db, row) for row in db.scalars(select(BookCopy).where(BookCopy.book_id == book.id).order_by(BookCopy.id).limit(5)).all()]
    return data


# ── Category / Subcategory CRUD ──

from bookflow_core.services.catalog_category_service import (
    create_category,
    create_subcategory,
    delete_category,
    delete_subcategory,
    update_category,
    update_subcategory,
)
