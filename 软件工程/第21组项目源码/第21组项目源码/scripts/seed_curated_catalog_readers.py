from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "data" / "bookflow.db"
SEED_MARK = "curated_docs_seed_20260605"
TARGET_READER_COUNT = 20
TARGET_BOOK_COUNT = 100
COPIES_PER_BOOK = 2

sys.path.insert(0, str((ROOT / "backend").resolve()))
from bookflow_core.core.security import hash_password  # noqa: E402


READER_TYPE_MAP = {
    "R01": ("child", "儿童读者"),
    "R02": ("teen", "青少年读者"),
    "R03": ("adult", "成人读者"),
    "R04": ("senior", "老年读者"),
    "R05": ("institution", "机构账号"),
}

READER_TYPES = [
    ("child", "儿童读者", "CH"),
    ("teen", "青少年读者", "TE"),
    ("adult", "成人读者", "AD"),
    ("senior", "老年读者", "SR"),
    ("institution", "机构账号", "IN"),
]

CATEGORY_ZONE_FALLBACK = {
    "C01": "Z03",
    "C02": "Z03",
    "C03": "Z09",
    "C04": "Z03",
    "C05": "Z07",
    "C06": "Z07",
    "C07": "Z07",
    "C08": "Z08",
    "C09": "Z08",
    "C10": "Z08",
    "C11": "Z08",
    "C12": "Z08",
    "C13": "Z09",
    "C14": "Z09",
    "C15": "Z08",
    "C16": "Z10",
    "C17": "Z10",
    "C18": "Z04",
}


def text(value: Any, fallback: str = "") -> str:
    raw = str(value or "").strip()
    if raw.lower() in {"null", "none", "nan"}:
        return fallback
    return raw or fallback


def intval(value: Any, fallback: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return fallback


def floatval(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return fallback


def now_text() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def find_package_tables() -> Path:
    for root in (ROOT / "docs" / "reference").glob("BookFlow_*"):
        tables = root / "bookflow_ops_csv_package" / "tables"
        if tables.is_dir():
            return tables
    raise FileNotFoundError("BookFlow CSV package tables directory was not found.")


def read_csv(tables: Path, filename: str) -> list[dict[str, str]]:
    path = tables / filename
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def isbn13(seed: int) -> str:
    base = f"978730{seed:06d}"[:12]
    digits = [int(char) for char in base]
    checksum = (10 - (sum(d if index % 2 == 0 else d * 3 for index, d in enumerate(digits)) % 10)) % 10
    return f"{base}{checksum}"


def phone_for(index: int) -> tuple[str, str]:
    prefix = ["130", "131", "132", "135", "136", "137", "138", "139"][index % 8]
    suffix = f"{2600 + index:04d}"
    full = f"{prefix}{4200 + index:04d}{suffix}"
    return full, hashlib.sha256(full.encode("utf-8")).hexdigest()


def choose_readers(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    seen_names: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        mapped = READER_TYPE_MAP.get(text(row.get("reader_type_code")))
        if not mapped:
            continue
        reader_type, _reader_type_name = mapped
        name = text(row.get("name"))
        if not name or name in seen_names[reader_type]:
            continue
        seen_names[reader_type].add(name)
        grouped[reader_type].append(row)

    selected: list[dict[str, Any]] = []
    global_index = 1
    for reader_type, reader_type_name, code_prefix in READER_TYPES:
        source_rows = grouped.get(reader_type, [])[:4]
        while len(source_rows) < 4:
            source_rows.append({"id": str(900000 + len(source_rows)), "name": f"{reader_type_name}{len(source_rows) + 1:02d}"})
        for offset, row in enumerate(source_rows, start=1):
            full_phone, phone_hash = phone_for(global_index)
            created_at = datetime(2026, 5, 10, 9, 0, 0) + timedelta(days=global_index % 18, hours=global_index % 7)
            selected.append(
                {
                    "source_reader_id": intval(row.get("id"), global_index),
                    "reader_code": f"RD-{code_prefix}-{offset:03d}",
                    "reader_type_code": reader_type,
                    "reader_type_name": reader_type_name,
                    "name": text(row.get("name"), f"{reader_type_name}{offset:02d}"),
                    "phone_masked": full_phone,
                    "phone_hash": phone_hash,
                    "email": f"reader-{reader_type}-{offset:03d}@bookflow.local",
                    "status": "active",
                    "credit_score": str(96 - (offset % 3) * 2),
                    "registered_at": created_at.isoformat(sep=" "),
                    "active_90d": "1",
                    "current_borrow_count": 0,
                    "borrow_suspended_until": "",
                    "remark": f"{SEED_MARK}; regenerated contact fields from clean seed policy",
                    "password_hash": hash_password("Reader@2026"),
                    "created_at": created_at.isoformat(sep=" "),
                    "updated_at": now_text(),
                }
            )
            global_index += 1
    return selected


def choose_books(book_rows: list[dict[str, str]], subcategories: list[dict[str, str]]) -> list[dict[str, str]]:
    by_subcategory: dict[str, list[dict[str, str]]] = defaultdict(list)
    clean_rows: list[dict[str, str]] = []
    for row in book_rows:
        if not text(row.get("title")) or not text(row.get("category_code")) or not text(row.get("subcategory_code")):
            continue
        clean_rows.append(row)
        by_subcategory[text(row.get("subcategory_code"))].append(row)

    selected: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(row: dict[str, str]) -> bool:
        signature = "|".join([text(row.get("title")).lower(), text(row.get("author")).lower(), text(row.get("publisher")).lower()])
        if signature in seen:
            return False
        seen.add(signature)
        selected.append(row)
        return True

    for subcategory in sorted(subcategories, key=lambda item: (text(item.get("category_code")), intval(item.get("sort_order")), text(item.get("subcategory_code")))):
        for row in by_subcategory.get(text(subcategory.get("subcategory_code")), []):
            if add(row):
                break

    category_codes = sorted({text(row.get("category_code")) for row in clean_rows if text(row.get("category_code"))})
    by_category: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in sorted(clean_rows, key=lambda item: intval(item.get("id"))):
        by_category[text(row.get("category_code"))].append(row)

    while len(selected) < TARGET_BOOK_COUNT:
        changed = False
        counts = {code: sum(1 for row in selected if text(row.get("category_code")) == code) for code in category_codes}
        for category_code in sorted(category_codes, key=lambda code: (counts.get(code, 0), code)):
            for row in by_category.get(category_code, []):
                if add(row):
                    changed = True
                    break
            if len(selected) >= TARGET_BOOK_COUNT:
                break
        if not changed:
            break

    if len(selected) < TARGET_BOOK_COUNT:
        raise RuntimeError(f"Only selected {len(selected)} clean book rows; expected {TARGET_BOOK_COUNT}.")
    return selected[:TARGET_BOOK_COUNT]


def existing_zone_codes(conn: sqlite3.Connection) -> set[str]:
    return {row["zone_code"] for row in conn.execute("SELECT zone_code FROM library_zones")}


def normalized_zone_code(raw: str, category_code: str, valid_codes: set[str]) -> str:
    candidates = [part.strip() for part in text(raw).replace("；", "/").replace(",", "/").split("/") if part.strip()]
    candidates.append(CATEGORY_ZONE_FALLBACK.get(category_code, "Z08"))
    for candidate in candidates:
        if candidate in valid_codes:
            return candidate
    return "Z08" if "Z08" in valid_codes else sorted(valid_codes)[0]


def zone_id(conn: sqlite3.Connection, zone_code: str) -> int | None:
    row = conn.execute("SELECT id FROM library_zones WHERE zone_code = ?", (zone_code,)).fetchone()
    return int(row["id"]) if row else None


def upsert_categories(conn: sqlite3.Connection, rows: list[dict[str, str]]) -> dict[str, int]:
    valid_zones = existing_zone_codes(conn)
    category_ids: dict[str, int] = {}
    for row in sorted(rows, key=lambda item: intval(item.get("sort_order"))):
        code = text(row.get("category_code"))
        primary_zone_code = normalized_zone_code(text(row.get("primary_zone_code")), code, valid_zones)
        values = {
            "category_name": text(row.get("category_name"), code),
            "subcategory_examples": text(row.get("subcategory_examples")),
            "primary_zone_id": zone_id(conn, primary_zone_code),
            "primary_zone_code": primary_zone_code,
            "clc_hint": text(row.get("clc_hint")),
            "sort_order": intval(row.get("sort_order")),
            "updated_at": now_text(),
        }
        existing = conn.execute("SELECT id FROM book_categories WHERE category_code = ? ORDER BY id LIMIT 1", (code,)).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE book_categories
                SET category_name = ?, subcategory_examples = ?, primary_zone_id = ?, primary_zone_code = ?,
                    clc_hint = ?, sort_order = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    values["category_name"],
                    values["subcategory_examples"],
                    values["primary_zone_id"],
                    values["primary_zone_code"],
                    values["clc_hint"],
                    values["sort_order"],
                    values["updated_at"],
                    existing["id"],
                ),
            )
            category_ids[code] = int(existing["id"])
        else:
            cur = conn.execute(
                """
                INSERT INTO book_categories
                    (category_code, category_name, subcategory_examples, book_title_count, copy_count,
                     primary_zone_id, primary_zone_code, clc_hint, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, 0, 0, ?, ?, ?, ?, ?, ?)
                """,
                (
                    code,
                    values["category_name"],
                    values["subcategory_examples"],
                    values["primary_zone_id"],
                    values["primary_zone_code"],
                    values["clc_hint"],
                    values["sort_order"],
                    now_text(),
                    values["updated_at"],
                ),
            )
            category_ids[code] = int(cur.lastrowid)
    return category_ids


def upsert_subcategories(conn: sqlite3.Connection, rows: list[dict[str, str]], category_ids: dict[str, int]) -> dict[str, int]:
    subcategory_ids: dict[str, int] = {}
    for row in sorted(rows, key=lambda item: (text(item.get("category_code")), intval(item.get("sort_order")))):
        code = text(row.get("subcategory_code"))
        category_code = text(row.get("category_code"))
        category_id = category_ids[category_code]
        category_name = conn.execute("SELECT category_name FROM book_categories WHERE id = ?", (category_id,)).fetchone()["category_name"]
        existing = conn.execute("SELECT id FROM book_subcategories WHERE subcategory_code = ?", (code,)).fetchone()
        payload = (
            text(row.get("subcategory_name"), code),
            category_id,
            category_code,
            category_name,
            0,
            intval(row.get("sort_order")),
            now_text(),
        )
        if existing:
            conn.execute(
                """
                UPDATE book_subcategories
                SET subcategory_name = ?, category_id = ?, category_code = ?, category_name = ?,
                    allocated_book_title_count = ?, sort_order = ?, updated_at = ?
                WHERE id = ?
                """,
                (*payload, existing["id"]),
            )
            subcategory_ids[code] = int(existing["id"])
        else:
            cur = conn.execute(
                """
                INSERT INTO book_subcategories
                    (subcategory_code, subcategory_name, category_id, category_code, category_name,
                     allocated_book_title_count, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (code, *payload[:-1], now_text(), payload[-1]),
            )
            subcategory_ids[code] = int(cur.lastrowid)
    return subcategory_ids


def ensure_shelf_positions(conn: sqlite3.Connection) -> int:
    created = 0
    shelves = conn.execute("SELECT id, shelf_code, layer_count, side_rule FROM shelves ORDER BY id").fetchall()
    for shelf in shelves:
        sides = ["左", "右"] if text(shelf["side_rule"]).lower() in {"", "both", "left/right", "左/右"} else ["单面"]
        layer_count = max(1, intval(shelf["layer_count"], 4))
        for layer_no in range(1, layer_count + 1):
            for side in sides:
                position_code = f"{shelf['shelf_code']}-{layer_no}-{side}"
                if conn.execute("SELECT 1 FROM shelf_positions WHERE position_code = ?", (position_code,)).fetchone():
                    continue
                conn.execute(
                    """
                    INSERT INTO shelf_positions
                        (position_code, shelf_id, layer_no, side, capacity_estimate, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (position_code, shelf["id"], layer_no, side, 24, now_text(), now_text()),
                )
                created += 1
    return created


def positions_by_zone(conn: sqlite3.Connection) -> dict[str, list[sqlite3.Row]]:
    rows = conn.execute(
        """
        SELECT p.id AS position_id, p.position_code, s.id AS shelf_id, s.shelf_code, z.id AS zone_id, z.zone_code
        FROM shelf_positions p
        JOIN shelves s ON p.shelf_id = s.id
        JOIN library_zones z ON s.zone_id = z.id
        ORDER BY z.zone_code, s.id, p.layer_no, p.side
        """
    ).fetchall()
    grouped: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        grouped[row["zone_code"]].append(row)
    return grouped


def delete_previous_seed(conn: sqlite3.Connection) -> dict[str, int]:
    book_ids = [row["id"] for row in conn.execute("SELECT id FROM books WHERE data_note = ?", (SEED_MARK,))]
    reader_ids = [row["id"] for row in conn.execute("SELECT id FROM reader_accounts WHERE remark LIKE ?", (f"{SEED_MARK}%",))]
    deleted = {"books": len(book_ids), "readers": len(reader_ids)}
    if book_ids:
        placeholders = ",".join("?" for _ in book_ids)
        conn.execute(f"DELETE FROM book_circulation_stats WHERE book_id IN ({placeholders})", book_ids)
        conn.execute(f"DELETE FROM book_copies WHERE book_id IN ({placeholders})", book_ids)
        conn.execute(f"DELETE FROM books WHERE id IN ({placeholders})", book_ids)
    if reader_ids:
        placeholders = ",".join("?" for _ in reader_ids)
        conn.execute(f"DELETE FROM reader_notification_settings WHERE reader_id IN ({placeholders})", reader_ids)
        conn.execute(f"DELETE FROM reader_stats WHERE reader_id IN ({placeholders})", reader_ids)
        conn.execute(f"DELETE FROM reader_credentials WHERE reader_id IN ({placeholders})", reader_ids)
        for table, column in [
            ("reader_status_events", "reader_id"),
            ("reader_credit_events", "reader_id"),
            ("reader_login_events", "reader_id"),
            ("search_events", "reader_id"),
            ("notifications", "recipient_reader_id"),
            ("loans", "reader_id"),
            ("reservations", "reader_id"),
            ("overdue_cases", "reader_id"),
            ("circulation_service_requests", "reader_id"),
        ]:
            conn.execute(f"UPDATE {table} SET {column} = NULL WHERE {column} IN ({placeholders})", reader_ids)
        conn.execute(f"DELETE FROM reader_accounts WHERE id IN ({placeholders})", reader_ids)
    return deleted


def insert_readers(conn: sqlite3.Connection, readers: list[dict[str, Any]]) -> int:
    for reader in readers:
        cur = conn.execute(
            """
            INSERT INTO reader_accounts
                (source_reader_id, reader_code, reader_type_code, reader_type_name, name, phone_masked,
                 phone_hash, email, status, credit_score, registered_at, active_90d, current_borrow_count,
                 borrow_suspended_until, remark, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reader["source_reader_id"],
                reader["reader_code"],
                reader["reader_type_code"],
                reader["reader_type_name"],
                reader["name"],
                reader["phone_masked"],
                reader["phone_hash"],
                reader["email"],
                reader["status"],
                reader["credit_score"],
                reader["registered_at"],
                reader["active_90d"],
                reader["current_borrow_count"],
                reader["borrow_suspended_until"],
                reader["remark"],
                reader["created_at"],
                reader["updated_at"],
            ),
        )
        reader_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO reader_credentials
                (reader_id, login_name, phone_hash, email, password_hash, status, last_login_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'active', NULL, ?, ?)
            """,
            (reader_id, reader["reader_code"], reader["phone_hash"], reader["email"], reader["password_hash"], reader["created_at"], reader["updated_at"]),
        )
        conn.execute(
            """
            INSERT INTO reader_notification_settings
                (reader_id, borrow_due_enabled, reservation_arrival_enabled, system_notice_enabled,
                 email_enabled, sms_enabled, created_at, updated_at)
            VALUES (?, 1, 1, 1, 1, 0, ?, ?)
            """,
            (reader_id, reader["created_at"], reader["updated_at"]),
        )
        conn.execute(
            """
            INSERT INTO reader_stats
                (reader_id, active_loans, overdue_count, total_borrow_count, total_reservation_count, last_borrowed_at, computed_at)
            VALUES (?, '0', 0, 0, 0, NULL, ?)
            """,
            (reader_id, reader["updated_at"]),
        )
    return len(readers)


def clean_book_payload(row: dict[str, str], index: int, category_ids: dict[str, int], subcategory_ids: dict[str, int], conn: sqlite3.Connection) -> dict[str, Any]:
    category_code = text(row.get("category_code"))
    subcategory_code = text(row.get("subcategory_code"))
    category = conn.execute("SELECT * FROM book_categories WHERE id = ?", (category_ids[category_code],)).fetchone()
    subcategory = conn.execute("SELECT * FROM book_subcategories WHERE id = ?", (subcategory_ids[subcategory_code],)).fetchone()
    publish_year = intval(row.get("publish_year"), 2018 + (index % 7))
    if publish_year < 1900 or publish_year > 2026:
        publish_year = 2018 + (index % 7)
    clc_hint = text(row.get("clc_hint"), text(category["clc_hint"]))
    return {
        "source_book_id": intval(row.get("id"), index),
        "book_code": f"BK-{category_code}-{index:03d}",
        "category_id": int(category["id"]),
        "category_code": category_code,
        "category_name": text(category["category_name"]),
        "subcategory_id": int(subcategory["id"]),
        "subcategory_code": subcategory_code,
        "subcategory_name": text(subcategory["subcategory_name"]),
        "clc_hint": clc_hint,
        "title": text(row.get("title"), f"馆藏图书{index:03d}"),
        "author": text(row.get("author"), "佚名"),
        "publisher": text(row.get("publisher"), "BookFlow整理"),
        "publish_year": publish_year,
        "isbn": isbn13(index),
        "language": text(row.get("language"), "中文"),
        "edition": text(row.get("edition"), "第1版"),
        "pages": max(24, intval(row.get("pages"), 120 + index * 3 % 380)),
        "price_yuan": round(max(12.0, floatval(row.get("price_yuan"), 28.0 + (index % 30) * 1.2)), 2),
        "copy_count_snapshot": str(COPIES_PER_BOOK),
        "primary_zone_id": category["primary_zone_id"],
        "primary_zone_code": category["primary_zone_code"],
        "recommended_reader": text(row.get("recommended_reader"), text(category["category_name"])),
        "keywords": text(row.get("keywords"), f"{category_code},{subcategory_code},{text(category['category_name'])}"),
        "introduction": text(row.get("introduction"), f"{text(row.get('title'), '本书')}属于{text(category['category_name'])}/{text(subcategory['subcategory_name'])}馆藏，由BookFlow按当前字段标准整理。"),
        "circulation_type": "普通",
        "data_note": SEED_MARK,
        "clc_code": text(row.get("clc_code"), clc_hint.split("/")[0]),
        "call_number": f"{clc_hint.split('/')[0]}-{category_code}-{index:03d}",
        "isbn_status": "generated",
        "bibliographic_status": "normalized",
        "book_source_class": "curated_docs_sample",
        "status": "active",
    }


def insert_books_and_copies(
    conn: sqlite3.Connection,
    selected_books: list[dict[str, str]],
    category_ids: dict[str, int],
    subcategory_ids: dict[str, int],
) -> tuple[int, int, int]:
    grouped_positions = positions_by_zone(conn)
    any_positions = [row for rows in grouped_positions.values() for row in rows]
    if not any_positions:
        raise RuntimeError("No shelf positions available after position generation.")
    position_cursor: dict[str, int] = defaultdict(int)
    books_inserted = 0
    copies_inserted = 0
    stats_inserted = 0
    as_of = date(2026, 6, 5)

    for index, source_row in enumerate(selected_books, start=1):
        payload = clean_book_payload(source_row, index, category_ids, subcategory_ids, conn)
        cur = conn.execute(
            """
            INSERT INTO books
                (source_book_id, book_code, category_id, category_code, category_name, subcategory_id,
                 subcategory_code, subcategory_name, clc_hint, title, author, publisher, publish_year,
                 isbn, language, edition, pages, price_yuan, copy_count_snapshot, primary_zone_id,
                 primary_zone_code, recommended_reader, keywords, introduction, circulation_type,
                 data_note, clc_code, call_number, isbn_status, bibliographic_status, book_source_class,
                 status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["source_book_id"],
                payload["book_code"],
                payload["category_id"],
                payload["category_code"],
                payload["category_name"],
                payload["subcategory_id"],
                payload["subcategory_code"],
                payload["subcategory_name"],
                payload["clc_hint"],
                payload["title"],
                payload["author"],
                payload["publisher"],
                payload["publish_year"],
                payload["isbn"],
                payload["language"],
                payload["edition"],
                payload["pages"],
                payload["price_yuan"],
                payload["copy_count_snapshot"],
                payload["primary_zone_id"],
                payload["primary_zone_code"],
                payload["recommended_reader"],
                payload["keywords"],
                payload["introduction"],
                payload["circulation_type"],
                payload["data_note"],
                payload["clc_code"],
                payload["call_number"],
                payload["isbn_status"],
                payload["bibliographic_status"],
                payload["book_source_class"],
                payload["status"],
                now_text(),
                now_text(),
            ),
        )
        book_id = int(cur.lastrowid)
        books_inserted += 1

        zone_positions = grouped_positions.get(payload["primary_zone_code"]) or any_positions
        for copy_no in range(1, COPIES_PER_BOOK + 1):
            cursor = position_cursor[payload["primary_zone_code"]]
            position = zone_positions[cursor % len(zone_positions)]
            position_cursor[payload["primary_zone_code"]] += 1
            copy_code = f"CP-{payload['category_code']}-{index:03d}-{copy_no}"
            barcode = f"BC{index:05d}{copy_no:02d}"
            acquisition_date = as_of - timedelta(days=30 + ((index + copy_no) % 90))
            conn.execute(
                """
                INSERT INTO book_copies
                    (source_copy_id, copy_code, source_book_id, book_id, copy_no, barcode, category_code,
                     subcategory_code, collection_type, can_borrow_outside_library, status_code, status_name,
                     copy_status, current_zone_id, current_zone_code, current_shelf_id, shelf_code,
                     current_position_id, shelf_position, home_zone_id, home_zone_code, home_shelf_id,
                     home_shelf_code, home_position_id, home_shelf_position, acquisition_date,
                     acquisition_source, condition_level, asset_price_yuan, remark, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'S01', '在馆可借', 'available', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    index * 10 + copy_no,
                    copy_code,
                    payload["source_book_id"],
                    book_id,
                    copy_no,
                    barcode,
                    payload["category_code"],
                    payload["subcategory_code"],
                    "可外借馆藏",
                    position["zone_id"],
                    position["zone_code"],
                    position["shelf_id"],
                    position["shelf_code"],
                    position["position_id"],
                    position["position_code"],
                    position["zone_id"],
                    position["zone_code"],
                    position["shelf_id"],
                    position["shelf_code"],
                    position["position_id"],
                    position["position_code"],
                    acquisition_date.isoformat(),
                    "馆藏整理补录",
                    "良好",
                    payload["price_yuan"],
                    SEED_MARK,
                    now_text(),
                    now_text(),
                ),
            )
            copies_inserted += 1

        if index % 10 in {1, 2}:
            circulation_type = "热门"
            borrow_90d = 12 + (index % 6)
            reserve_90d = 2 + (index % 3)
            borrow_365d = borrow_90d + 30
            days_since_last_borrow = 7 + (index % 10)
        elif index % 10 in {9, 0}:
            circulation_type = "冷门"
            borrow_90d = 0
            reserve_90d = 0
            borrow_365d = index % 2
            days_since_last_borrow = 210 + (index % 80)
        else:
            circulation_type = "普通"
            borrow_90d = 2 + (index % 5)
            reserve_90d = index % 2
            borrow_365d = 8 + (index % 15)
            days_since_last_borrow = 25 + (index % 75)
        conn.execute("UPDATE books SET circulation_type = ? WHERE id = ?", (circulation_type, book_id))
        conn.execute(
            """
            INSERT INTO book_circulation_stats
                (book_id, source_book_id, title_snapshot, total_copies, available_copies, active_loans,
                 reservations_waiting, borrow_90d, reserve_90d, borrow_365d, days_since_last_borrow,
                 circulation_type, last_borrow_date, stat_date, computed_at)
            VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                book_id,
                payload["source_book_id"],
                payload["title"],
                COPIES_PER_BOOK,
                COPIES_PER_BOOK,
                borrow_90d,
                reserve_90d,
                borrow_365d,
                days_since_last_borrow,
                circulation_type,
                (as_of - timedelta(days=days_since_last_borrow)).isoformat(),
                as_of.isoformat(),
                now_text(),
            ),
        )
        stats_inserted += 1
    return books_inserted, copies_inserted, stats_inserted


def refresh_counts(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        UPDATE book_categories
        SET book_title_count = COALESCE((SELECT COUNT(*) FROM books WHERE books.category_id = book_categories.id), 0),
            copy_count = COALESCE((SELECT COUNT(*) FROM book_copies JOIN books ON books.id = book_copies.book_id WHERE books.category_id = book_categories.id), 0),
            updated_at = ?
        """,
        (now_text(),),
    )
    conn.execute(
        """
        UPDATE book_subcategories
        SET allocated_book_title_count = COALESCE((SELECT COUNT(*) FROM books WHERE books.subcategory_id = book_subcategories.id), 0),
            updated_at = ?
        """,
        (now_text(),),
    )
    conn.execute(
        """
        UPDATE library_profiles
        SET paper_collection_count = (SELECT COUNT(*) FROM book_copies),
            lendable_collection_count = (SELECT COUNT(*) FROM book_copies WHERE copy_status = 'available'),
            registered_reader_count = (SELECT COUNT(*) FROM reader_accounts),
            monthly_active_reader_count = (SELECT COUNT(*) FROM reader_accounts WHERE active_90d = '1'),
            shelf_count = (SELECT COUNT(*) FROM shelves),
            updated_at = ?
        WHERE id = (SELECT id FROM library_profiles ORDER BY id LIMIT 1)
        """,
        (now_text(),),
    )


def validate(conn: sqlite3.Connection) -> dict[str, Any]:
    checks = {
        "reader_accounts": conn.execute("SELECT COUNT(*) FROM reader_accounts").fetchone()[0],
        "reader_credentials": conn.execute("SELECT COUNT(*) FROM reader_credentials").fetchone()[0],
        "book_categories": conn.execute("SELECT COUNT(*) FROM book_categories").fetchone()[0],
        "book_subcategories": conn.execute("SELECT COUNT(*) FROM book_subcategories").fetchone()[0],
        "books": conn.execute("SELECT COUNT(*) FROM books").fetchone()[0],
        "book_copies": conn.execute("SELECT COUNT(*) FROM book_copies").fetchone()[0],
        "book_circulation_stats": conn.execute("SELECT COUNT(*) FROM book_circulation_stats").fetchone()[0],
        "shelf_positions": conn.execute("SELECT COUNT(*) FROM shelf_positions").fetchone()[0],
        "foreign_key_issues": [dict(row) for row in conn.execute("PRAGMA foreign_key_check").fetchall()],
        "reader_types": [dict(row) for row in conn.execute("SELECT reader_type_code, COUNT(*) AS count FROM reader_accounts GROUP BY reader_type_code ORDER BY reader_type_code")],
        "category_coverage": [dict(row) for row in conn.execute("SELECT category_code, COUNT(*) AS books FROM books GROUP BY category_code ORDER BY category_code")],
        "subcategory_count_with_books": conn.execute("SELECT COUNT(DISTINCT subcategory_code) FROM books").fetchone()[0],
        "copy_statuses": [dict(row) for row in conn.execute("SELECT copy_status, COUNT(*) AS count FROM book_copies GROUP BY copy_status ORDER BY copy_status")],
    }
    if checks["foreign_key_issues"]:
        raise RuntimeError(f"Foreign key issues found: {checks['foreign_key_issues']}")
    return checks


def main() -> int:
    tables = find_package_tables()
    backup = DB_PATH.with_name(f"bookflow.backup_before_curated_seed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    shutil.copy2(DB_PATH, backup)

    category_rows = read_csv(tables, "book_categories.csv")
    subcategory_rows = read_csv(tables, "book_subcategories.csv")
    reader_rows = read_csv(tables, "reader_accounts.csv")
    book_rows = read_csv(tables, "books.csv")
    selected_readers = choose_readers(reader_rows)
    selected_books = choose_books(book_rows, subcategory_rows)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN")
        deleted = delete_previous_seed(conn)
        category_ids = upsert_categories(conn, category_rows)
        subcategory_ids = upsert_subcategories(conn, subcategory_rows, category_ids)
        positions_created = ensure_shelf_positions(conn)
        readers_inserted = insert_readers(conn, selected_readers)
        books_inserted, copies_inserted, stats_inserted = insert_books_and_copies(conn, selected_books, category_ids, subcategory_ids)
        refresh_counts(conn)
        checks = validate(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(
        json.dumps(
            {
                "backup": str(backup.resolve()),
                "deleted_previous_seed": deleted,
                "positions_created": positions_created,
                "readers_inserted": readers_inserted,
                "books_inserted": books_inserted,
                "copies_inserted": copies_inserted,
                "stats_inserted": stats_inserted,
                "checks": checks,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
