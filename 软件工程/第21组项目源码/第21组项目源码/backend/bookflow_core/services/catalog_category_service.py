from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bookflow_core.core.exceptions import BusinessRuleError, NotFoundError
from bookflow_core.core.time import now
from bookflow_core.models import Book, BookCategory, BookSubcategory
from bookflow_core.services.common import write_audit


# ── Category / Subcategory CRUD ──
def create_category(db: Session, *, category_code: str, category_name: str, subcategory_examples: str | None = None, primary_zone_code: str | None = None, clc_hint: str | None = None, sort_order: int = 0, actor_id: str = "admin") -> BookCategory:
    existing = db.scalar(select(BookCategory).where(BookCategory.category_code == category_code))
    if existing:
        raise BusinessRuleError("该分类编号已存在。", code="VALIDATION_ERROR")
    row = BookCategory(
        category_code=category_code,
        category_name=category_name,
        subcategory_examples=subcategory_examples or "",
        primary_zone_code=primary_zone_code or "",
        clc_hint=clc_hint or "",
        sort_order=sort_order,
        book_title_count=0,
        copy_count=0,
        created_at=now(),
        updated_at=now(),
    )
    db.add(row)
    db.flush()
    write_audit(db, actor_type="admin", actor_id=actor_id, action="create_category", target_table="book_categories", target_id=row.id, detail={"category_code": category_code, "category_name": category_name})
    db.commit()
    return row


def update_category(db: Session, *, category_id: int, category_name: str | None = None, subcategory_examples: str | None = None, primary_zone_code: str | None = None, clc_hint: str | None = None, sort_order: int | None = None, actor_id: str = "admin") -> BookCategory:
    row = db.get(BookCategory, category_id)
    if not row:
        raise NotFoundError("BookCategory not found.", code="NOT_FOUND")
    if category_name is not None:
        row.category_name = category_name
    if subcategory_examples is not None:
        row.subcategory_examples = subcategory_examples
    if primary_zone_code is not None:
        row.primary_zone_code = primary_zone_code
    if clc_hint is not None:
        row.clc_hint = clc_hint
    if sort_order is not None:
        row.sort_order = sort_order
    row.updated_at = now()
    write_audit(db, actor_type="admin", actor_id=actor_id, action="update_category", target_table="book_categories", target_id=row.id, detail={"category_name": row.category_name})
    db.commit()
    return row


def delete_category(db: Session, *, category_id: int, actor_id: str = "admin") -> None:
    row = db.get(BookCategory, category_id)
    if not row:
        raise NotFoundError("BookCategory not found.", code="NOT_FOUND")
    book_count = db.scalar(select(func.count(Book.id)).where(Book.category_id == category_id)) or 0
    if book_count > 0:
        raise BusinessRuleError(f"该分类下还有 {book_count} 本图书，无法删除。", code="BUSINESS_RULE")
    sub_count = db.scalar(select(func.count(BookSubcategory.id)).where(BookSubcategory.category_id == category_id)) or 0
    if sub_count > 0:
        raise BusinessRuleError(f"该分类下还有 {sub_count} 个二级分类，请先删除二级分类。", code="BUSINESS_RULE")
    write_audit(db, actor_type="admin", actor_id=actor_id, action="delete_category", target_table="book_categories", target_id=row.id, detail={"category_code": row.category_code, "category_name": row.category_name})
    db.delete(row)
    db.commit()


def create_subcategory(db: Session, *, category_id: int, subcategory_code: str, subcategory_name: str, sort_order: int = 0, actor_id: str = "admin") -> BookSubcategory:
    category = db.get(BookCategory, category_id)
    if not category:
        raise NotFoundError("BookCategory not found.", code="NOT_FOUND")
    existing = db.scalar(select(BookSubcategory).where(BookSubcategory.subcategory_code == subcategory_code))
    if existing:
        raise BusinessRuleError("该二级分类编号已存在。", code="VALIDATION_ERROR")
    row = BookSubcategory(
        subcategory_code=subcategory_code,
        subcategory_name=subcategory_name,
        category_id=category.id,
        category_code=category.category_code,
        category_name=category.category_name,
        sort_order=sort_order,
        allocated_book_title_count=0,
        created_at=now(),
        updated_at=now(),
    )
    db.add(row)
    db.flush()
    write_audit(db, actor_type="admin", actor_id=actor_id, action="create_subcategory", target_table="book_subcategories", target_id=row.id, detail={"subcategory_code": subcategory_code, "subcategory_name": subcategory_name, "category_code": category.category_code})
    db.commit()
    return row


def update_subcategory(db: Session, *, subcategory_id: int, subcategory_name: str | None = None, sort_order: int | None = None, actor_id: str = "admin") -> BookSubcategory:
    row = db.get(BookSubcategory, subcategory_id)
    if not row:
        raise NotFoundError("BookSubcategory not found.", code="NOT_FOUND")
    if subcategory_name is not None:
        row.subcategory_name = subcategory_name
    if sort_order is not None:
        row.sort_order = sort_order
    row.updated_at = now()
    write_audit(db, actor_type="admin", actor_id=actor_id, action="update_subcategory", target_table="book_subcategories", target_id=row.id, detail={"subcategory_name": row.subcategory_name})
    db.commit()
    return row


def delete_subcategory(db: Session, *, subcategory_id: int, actor_id: str = "admin") -> None:
    row = db.get(BookSubcategory, subcategory_id)
    if not row:
        raise NotFoundError("BookSubcategory not found.", code="NOT_FOUND")
    book_count = db.scalar(select(func.count(Book.id)).where(Book.subcategory_id == subcategory_id)) or 0
    if book_count > 0:
        raise BusinessRuleError(f"该二级分类下还有 {book_count} 本图书，无法删除。", code="BUSINESS_RULE")
    write_audit(db, actor_type="admin", actor_id=actor_id, action="delete_subcategory", target_table="book_subcategories", target_id=row.id, detail={"subcategory_code": row.subcategory_code, "subcategory_name": row.subcategory_name})
    db.delete(row)
    db.commit()
