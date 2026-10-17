from __future__ import annotations
import re
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from bookflow_core.core.exceptions import NotFoundError
from bookflow_core.models import Book, BookCategory, BookCopy, BookSubcategory
from bookflow_core.services.catalog_service import book_list_item_to_dict, book_to_dict, list_cold_books, list_hot_books, update_copy_status
from bookflow_core.services.common import create_snapshot
from bookflow_core.services.public_catalog_service import get_public_book_copies, list_public_books

MAX_SEARCH_CANDIDATES = 200

_PUNCTUATION_RE = re.compile(r"[\s,，。？?！!；;：:、（）()【】\[\]{}<>《》\"'“”‘’]+")
_LEADING_NOISE = (
    "我想知道",
    "想知道",
    "帮我看看",
    "帮我查查",
    "帮我查",
    "请问",
    "问一下",
    "查一下",
    "搜索一下",
    "检索一下",
    "找一下",
    "找一找",
    "我们馆内",
    "馆内",
    "图书馆",
    "你们馆",
    "我记得",
    "记得",
)
_QUERY_NOISE = (
    "相关书籍",
    "相关图书",
    "相关的书",
    "相关书",
    "有哪些",
    "有没有",
    "有多少",
    "多少本",
    "几本",
    "书籍",
    "图书",
    "馆藏",
    "相关",
    "之类",
    "类似",
    "目前",
    "现在",
    "我们",
    "你们",
    "帮我",
    "可以",
    "一下",
    "吗",
    "呢",
    "吧",
)
_SERIES_CONTINUATION_MARKERS = (
    "后两部",
    "后二部",
    "后2部",
    "后续两部",
    "续作",
    "续集",
    "第二部",
    "第2部",
    "第三部",
    "第3部",
)
_TERM_EXPANSIONS = {
    "科幻": ["科幻小说", "科学幻想", "science fiction", "sci-fi"],
    "科幻小说": ["科幻", "科学幻想", "science fiction", "sci-fi"],
    "乡土志": ["地方志", "方志", "地方文献", "地方历史", "志书"],
    "方志": ["地方志", "地方文献", "地方历史", "志书"],
    "地方志": ["方志", "地方文献", "地方历史", "志书"],
}
_SERIES_HINTS = {
    "三体": ["三体", "三体Ⅱ", "三体II", "三体2", "黑暗森林", "三体Ⅲ", "三体III", "三体3", "死神永生"],
}

_FIELD_LABELS = {
    "title": "题名",
    "author": "作者",
    "book_code": "书目编号",
    "isbn": "ISBN",
    "keywords": "关键词",
    "category_name": "一级分类",
    "subcategory_name": "二级分类",
    "clc_hint": "分类提示",
    "clc_code": "中图法",
    "call_number": "索书号",
}


def _copy_snapshot(db: Session, copy_code: str) -> dict:
    copy = db.scalar(select(BookCopy).where(BookCopy.copy_code == copy_code))
    if not copy:
        raise NotFoundError("Copy not found.")
    return {"copy_code": copy.copy_code, "copy_status": copy.copy_status, "book_id": copy.book_id, "current_position_id": copy.current_position_id}


def ai_get_hot_books(db: Session, payload: dict, *, actor_id: str) -> dict:
    return {"items": [book_to_dict(b) for b in list_hot_books(db, int(payload.get("limit", 10)))]}


def ai_get_cold_books(db: Session, payload: dict, *, actor_id: str) -> dict:
    return {"items": [book_to_dict(b) for b in list_cold_books(db, int(payload.get("limit", 10)))]}


def _compact_text(value: object | None) -> str:
    return _PUNCTUATION_RE.sub("", str(value or "").strip())


def _clean_query_phrase(value: object | None) -> str:
    text = _compact_text(value)
    for prefix in _LEADING_NOISE:
        if text.startswith(prefix):
            text = text[len(prefix) :]
    for noise in _QUERY_NOISE:
        text = text.replace(noise, "")
    text = text.replace("还有", "").replace("只有", "")
    while text.endswith("的"):
        text = text[:-1]
    return text.strip()


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = value.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _extract_series_base(raw_keyword: str, cleaned: str) -> str:
    text = _compact_text(raw_keyword)
    if any(marker in text for marker in _SERIES_CONTINUATION_MARKERS):
        for known_base in _SERIES_HINTS:
            if known_base in text:
                return known_base
        match = re.search(r"(.+?)(?:还有|有)?后[两二2]部", text)
        if match:
            return _clean_query_phrase(match.group(1))
    for known_base in _SERIES_HINTS:
        if known_base in cleaned and any(marker in cleaned for marker in _SERIES_CONTINUATION_MARKERS):
            return known_base
    return ""


def _search_terms(keyword: str) -> dict[str, Any]:
    raw = str(keyword or "").strip()
    quoted = [part.strip() for part in re.findall(r"《([^》]+)》", raw) if part.strip()]
    cleaned = _clean_query_phrase(raw)
    continuation = any(marker in _compact_text(raw) for marker in _SERIES_CONTINUATION_MARKERS)
    series_base = _extract_series_base(raw, cleaned)

    base_terms = [raw, cleaned, *quoted]
    if series_base:
        base_terms.append(series_base)
        base_terms.extend(_SERIES_HINTS.get(series_base, []))

    for term, expansions in _TERM_EXPANSIONS.items():
        if term in raw or term in cleaned:
            base_terms.append(term)
            base_terms.extend(expansions)

    cleaned_terms: list[str] = []
    for term in base_terms:
        compact = _clean_query_phrase(term)
        if compact:
            cleaned_terms.append(compact)
        if term and term != compact:
            plain = _compact_text(term)
            if plain:
                cleaned_terms.append(plain)

    terms = _dedupe([term for term in cleaned_terms if len(term) >= 2 or term.isascii()])
    expansions = [term for term in terms if term not in {raw, cleaned, *quoted}]
    normalized = series_base or (cleaned or (quoted[0] if quoted else raw))
    return {
        "raw": raw,
        "normalized": normalized,
        "terms": terms,
        "expansions": expansions,
        "series_base": series_base,
        "series_continuation": bool(continuation and series_base),
    }


def _book_field_values(book: Book) -> dict[str, str]:
    category_name = book.category_name or (book.category.category_name if getattr(book, "category", None) else "")
    subcategory_name = book.subcategory_name or (book.subcategory.subcategory_name if getattr(book, "subcategory", None) else "")
    return {
        "title": str(book.title or ""),
        "author": str(book.author or ""),
        "book_code": str(book.book_code or ""),
        "isbn": str(book.isbn or ""),
        "keywords": str(book.keywords or ""),
        "category_name": str(category_name or ""),
        "subcategory_name": str(subcategory_name or ""),
        "clc_hint": str(book.clc_hint or ""),
        "clc_code": str(book.clc_code or ""),
        "call_number": str(book.call_number or ""),
    }


def _field_match_score(field: str, value: str, term: str) -> int:
    if not value or not term:
        return 0
    value_lower = value.lower()
    term_lower = term.lower()
    if field == "title":
        if value_lower == term_lower:
            return 130
        if value_lower.startswith(term_lower):
            return 105
        if term_lower in value_lower:
            return 90
    if field == "author" and term_lower in value_lower:
        return 55
    if field in {"book_code", "isbn"} and term_lower in value_lower:
        return 45
    if field in {"keywords", "subcategory_name"} and term_lower in value_lower:
        return 36
    if field == "category_name" and term_lower in value_lower:
        return 30
    if field in {"clc_hint", "clc_code", "call_number"} and term_lower in value_lower:
        return 22
    return 0


def _score_book(book: Book, terms: list[str], *, series_base: str = "", series_continuation: bool = False) -> dict[str, Any]:
    fields = _book_field_values(book)
    score = 0
    matched_fields: set[str] = set()
    matched_terms: set[str] = set()
    details: list[dict[str, str]] = []
    for term in terms:
        for field, value in fields.items():
            part_score = _field_match_score(field, value, term)
            if not part_score:
                continue
            score += part_score
            matched_fields.add(field)
            matched_terms.add(term)
            details.append({"field": field, "label": _FIELD_LABELS.get(field, field), "term": term})

    exact_series_root = False
    if series_base:
        title = fields["title"].lower()
        base = series_base.lower()
        exact_series_root = title == base
        if base in title:
            score += 80
        if series_continuation and not exact_series_root:
            score += 120
        if series_continuation and exact_series_root:
            score -= 80

    metadata_fields = {"keywords", "category_name", "subcategory_name", "clc_hint", "clc_code", "call_number"}
    identity_fields = {"title", "author", "book_code", "isbn"}
    metadata_only = bool(matched_fields & metadata_fields) and not bool(matched_fields & identity_fields)
    notes: list[str] = []
    if metadata_only:
        notes.append("该条目主要由目录分类/关键词命中，不代表系统已核验其题材归属。")
    if series_continuation and exact_series_root:
        notes.append("该条目是系列首部；当前查询更像是在找后续作品。")
    return {
        "score": score,
        "matched_fields": sorted(matched_fields),
        "matched_terms": sorted(matched_terms),
        "match_details": details[:8],
        "metadata_only_match": metadata_only,
        "notes": notes,
        "exact_series_root": exact_series_root,
    }


def _candidate_books(db: Session, terms: list[str], *, availability: str | None, max_rows: int) -> list[Book]:
    if not terms:
        return []
    clauses = []
    for term in terms:
        like_fields = (
            Book.title,
            Book.author,
            Book.book_code,
            Book.isbn,
            Book.keywords,
            Book.category_name,
            Book.subcategory_name,
            Book.clc_hint,
            Book.clc_code,
            Book.call_number,
            BookCategory.category_name,
            BookCategory.category_code,
            BookSubcategory.subcategory_name,
            BookSubcategory.subcategory_code,
        )
        clauses.extend(field.contains(term) for field in like_fields)

    stmt = (
        select(Book)
        .outerjoin(BookCategory, Book.category_id == BookCategory.id)
        .outerjoin(BookSubcategory, Book.subcategory_id == BookSubcategory.id)
        .where(Book.status == "active")
        .where(or_(*clauses))
    )
    available_copies = select(BookCopy.id).where(BookCopy.book_id == Book.id, BookCopy.copy_status == "available").exists()
    if availability == "available":
        stmt = stmt.where(available_copies)
    elif availability in {"unavailable", "none"}:
        stmt = stmt.where(~available_copies)
    return db.scalars(stmt.order_by(Book.id).limit(max_rows)).unique().all()


def _related_query_suggestions(query_info: dict[str, Any]) -> list[str]:
    suggestions = list(query_info["expansions"])
    if query_info["normalized"] and query_info["normalized"] not in suggestions:
        suggestions.insert(0, query_info["normalized"])
    compact = str(query_info.get("normalized") or "")
    for noise in ("完全不存在的", "不存在的", "有没有", "查找", "搜索", "检索"):
        compact = compact.replace(noise, "")
    if compact and compact not in suggestions:
        suggestions.append(compact)
    for token in ("火星", "种植", "手册", "指南", "地方志", "方志", "科幻", "三体"):
        if token in compact and token not in suggestions:
            suggestions.append(token)
    return _dedupe(suggestions)[:8]


def _copy_location_text(copy: dict) -> str:
    location = copy.get("location") if isinstance(copy.get("location"), dict) else {}
    parts = [
        location.get("zone_name") or location.get("zone_code") or copy.get("current_zone_code"),
        location.get("shelf_code") or copy.get("shelf_code"),
        location.get("shelf_position") or location.get("position_code") or copy.get("shelf_position"),
    ]
    return " / ".join(str(item) for item in parts if item) or ""


def _location_samples(db: Session, book_id: int, *, limit: int = 3) -> list[dict]:
    data = get_public_book_copies(db, book_id, limit=50, offset=0)
    copies = data.get("items") if isinstance(data, dict) else []
    if not isinstance(copies, list):
        return []
    preferred = [item for item in copies if item.get("copy_status") == "available"] or copies
    result: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for copy in preferred:
        if not isinstance(copy, dict):
            continue
        location = copy.get("location") if isinstance(copy.get("location"), dict) else {}
        key = (
            str(location.get("zone_code") or copy.get("current_zone_code") or ""),
            str(location.get("shelf_code") or copy.get("shelf_code") or ""),
            str(location.get("shelf_position") or location.get("position_code") or copy.get("shelf_position") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "copy_code": copy.get("copy_code"),
                "copy_status": copy.get("copy_status") or copy.get("status"),
                "zone_name": location.get("zone_name"),
                "zone_code": location.get("zone_code") or copy.get("current_zone_code"),
                "shelf_code": location.get("shelf_code") or copy.get("shelf_code"),
                "shelf_position": location.get("shelf_position") or location.get("position_code") or copy.get("shelf_position"),
                "location_text": _copy_location_text(copy),
            }
        )
        if len(result) >= limit:
            break
    return result


def ai_search_books(db: Session, payload: dict, *, actor_id: str) -> dict:
    keyword = str(payload.get("keyword") or "").strip()
    availability = payload.get("availability")
    sort = payload.get("sort") or ("availability" if availability == "available" else None)
    limit = min(max(int(payload.get("limit", 10)), 1), 20)
    clean_availability = availability if availability in {"available", "unavailable", "none"} else None
    clean_sort = sort if sort in {"availability", "newest", "title"} else None
    query_info = _search_terms(keyword)
    if not keyword:
        data = list_public_books(
            db,
            keyword=None,
            availability=clean_availability,
            sort=clean_sort,
            page=1,
            page_size=limit,
        )
        source_items = [{"item": item, "search_meta": {}} for item in data.get("items", []) if isinstance(item, dict)]
        total = int(data.get("total", len(source_items)) or 0)
    else:
        rows = _candidate_books(db, query_info["terms"], availability=clean_availability, max_rows=max(MAX_SEARCH_CANDIDATES, limit * 8))
        scored: list[tuple[Book, dict[str, Any]]] = []
        for book in rows:
            meta = _score_book(
                book,
                query_info["terms"],
                series_base=query_info["series_base"],
                series_continuation=query_info["series_continuation"],
            )
            if meta["score"] > 0:
                scored.append((book, meta))
        if query_info["series_continuation"] and any(not meta["exact_series_root"] for _book, meta in scored):
            scored = [(book, meta) for book, meta in scored if not meta["exact_series_root"]]
        scored.sort(key=lambda pair: (-pair[1]["score"], str(pair[0].title or ""), pair[0].id))
        total = len(scored)
        source_items = []
        for book, meta in scored[:limit]:
            item = book_list_item_to_dict(db, book)
            source_items.append({"item": item, "search_meta": meta})

    items: list[dict] = []
    for record in source_items:
        item = record["item"]
        search_meta = record["search_meta"]
        book_id = item.get("id")
        locations = _location_samples(db, int(book_id), limit=3) if book_id else []
        items.append(
            {
                "book_id": book_id,
                "book_code": item.get("book_code"),
                "title": item.get("title"),
                "author": item.get("author"),
                "publisher": item.get("publisher"),
                "publish_year": item.get("publish_year"),
                "isbn": item.get("isbn"),
                "category_name": item.get("category_name"),
                "circulation_type": item.get("circulation_type"),
                "total_copies": item.get("total_copies"),
                "available_copies": item.get("available_copies"),
                "copy_stats": item.get("copy_stats"),
                "primary_zone": item.get("primary_zone"),
                "locations": locations,
                "search_score": search_meta.get("score"),
                "matched_fields": search_meta.get("matched_fields", []),
                "matched_terms": search_meta.get("matched_terms", []),
                "match_details": search_meta.get("match_details", []),
                "metadata_only_match": bool(search_meta.get("metadata_only_match", False)),
                "notes": search_meta.get("notes", []),
            }
        )
    return {
        "query": keyword,
        "normalized_query": query_info["normalized"],
        "query_terms": query_info["terms"],
        "query_expansions": query_info["expansions"],
        "search_strategy": "expanded_keyword_rank" if keyword else "public_catalog_default",
        "series_base": query_info["series_base"],
        "series_continuation": query_info["series_continuation"],
        "items": items,
        "total": total,
        "returned_count": len(items),
        "limit": limit,
        "offset": 0,
        "empty_suggestions": [] if items else _related_query_suggestions(query_info),
    }


def ai_update_copy_status(db: Session, payload: dict, *, actor_id: str) -> dict:
    copy_code = payload["copy_code"]
    before = _copy_snapshot(db, copy_code)
    copy = update_copy_status(db, copy_code, payload["new_status"], reason=payload.get("reason", "ai_update_copy_status"), actor_type="ai_admin", actor_id=actor_id, commit=False)
    after = _copy_snapshot(db, copy.copy_code)
    create_snapshot(db, action_type="ai_update_copy_status", target_table="book_copies", target_id=copy.copy_code, before=before, after=after, actor_type="ai_admin", actor_id=actor_id)
    return {"copy_code": copy.copy_code, "copy_status": copy.copy_status}
