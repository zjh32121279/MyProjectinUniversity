#!/usr/bin/env python3
"""Import 20 readers + 100 books with copies from CSV data package."""
import csv
import sqlite3
import random
from pathlib import Path
from collections import defaultdict

BASE = Path(r"C:\Users\hp\Downloads\BookFlow_core_新版")
CSV_DIR = BASE / "docs" / "reference" / "BookFlow_新数据" / "bookflow_ops_csv_package" / "tables"
DB_PATH = BASE / "backend" / "data" / "bookflow.db"


def read_csv(name: str) -> list[dict]:
    path = CSV_DIR / f"{name}.csv"
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def clear(conn, table: str):
    conn.execute(f"DELETE FROM {table}")
    conn.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")


def main():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = OFF")

    print("Loading CSVs...")
    books_csv = read_csv("books")
    copies_csv = read_csv("book_copies")
    readers_csv = read_csv("reader_accounts")
    creds_csv = read_csv("reader_credentials")
    notifs_csv = read_csv("reader_notification_settings")
    cats_csv = read_csv("book_categories")
    subcats_csv = read_csv("book_subcategories")

    # ── 1. Categories ──────────────────────────────────────────────────
    print("Importing categories...")
    clear(conn, "book_categories")
    clear(conn, "book_subcategories")

    for row in cats_csv:
        conn.execute(
            "INSERT INTO book_categories (id, category_code, category_name, subcategory_examples,"
            " book_title_count, copy_count, primary_zone_id, primary_zone_code, clc_hint,"
            " sort_order, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                int(row["id"]), row["category_code"], row["category_name"],
                row.get("subcategory_examples", ""), int(row.get("book_title_count", 0)),
                int(row.get("copy_count", 0)),
                int(row["primary_zone_id"]) if row.get("primary_zone_id") else None,
                row.get("primary_zone_code", ""), row.get("clc_hint", ""),
                int(row.get("sort_order", 0)), row.get("created_at", ""), row.get("updated_at", ""),
            ],
        )

    for row in subcats_csv:
        conn.execute(
            "INSERT INTO book_subcategories (id, subcategory_code, subcategory_name, category_id,"
            " category_code, category_name, allocated_book_title_count, sort_order, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                int(row["id"]), row["subcategory_code"], row["subcategory_name"],
                int(row.get("category_id", 0)), row.get("category_code", ""),
                row.get("category_name", ""), int(row.get("allocated_book_title_count", 0)),
                int(row.get("sort_order", 0)), row.get("created_at", ""), row.get("updated_at", ""),
            ],
        )

    # ── 2. Books — 100 books across all 18 categories ─────────────────
    print("Selecting 100 books...")
    clear(conn, "books")

    by_cat: dict[str, list[dict]] = defaultdict(list)
    for b in books_csv:
        by_cat[b["category_code"]].append(b)

    selected: list[dict] = []
    cats = sorted(by_cat.keys())
    per_cat, extra = divmod(100, len(cats))  # 5 per cat + 10 extra

    for i, cat in enumerate(cats):
        pool = by_cat[cat]
        n = per_cat + (1 if i < extra else 0)
        picked = random.sample(pool, min(n, len(pool)))
        selected.extend(picked)

    book_id_map: dict[str, int] = {}  # source_book_id → new numeric id

    book_cols = [
        "id","source_book_id","book_code","category_id","category_code","category_name",
        "subcategory_id","subcategory_code","subcategory_name","clc_hint","title","author",
        "publisher","publish_year","isbn","language","edition","pages","price_yuan",
        "copy_count_snapshot","primary_zone_id","primary_zone_code","recommended_reader",
        "keywords","introduction","circulation_type","data_note","clc_code","call_number",
        "isbn_status","bibliographic_status","book_source_class","status","created_at","updated_at",
    ]

    for idx, b in enumerate(selected, start=1):
        vals = [idx] + [b.get(c, "") for c in book_cols[1:]]
        placeholders = ",".join(["?"] * len(book_cols))
        conn.execute(f"INSERT INTO books ({','.join(book_cols)}) VALUES ({placeholders})", vals)
        book_id_map[b["source_book_id"]] = idx

    print(f"  Imported {len(selected)} books, {len(cats)} categories covered")

    # ── 3. Copies for selected books ───────────────────────────────────
    print("Importing copies...")
    clear(conn, "book_copies")

    copy_cols = [
        "id","source_copy_id","copy_code","source_book_id","book_id","copy_no","barcode",
        "category_code","subcategory_code","collection_type","can_borrow_outside_library",
        "status_code","status_name","copy_status","current_zone_id","current_zone_code",
        "current_shelf_id","shelf_code","current_position_id","shelf_position",
        "home_zone_id","home_zone_code","home_shelf_id","home_shelf_code",
        "home_position_id","home_shelf_position","acquisition_date","acquisition_source",
        "condition_level","asset_price_yuan","remark","created_at","updated_at",
    ]

    copy_id = 1
    for b in selected:
        src_id = b["source_book_id"]
        new_book_id = book_id_map[src_id]
        matches = [c for c in copies_csv if c["source_book_id"] == src_id]
        for c in matches[:3]:
            vals = [copy_id]
            for col in copy_cols[1:]:
                if col == "book_id":
                    vals.append(new_book_id)
                else:
                    vals.append(c.get(col, ""))
            placeholders = ",".join(["?"] * len(copy_cols))
            conn.execute(f"INSERT INTO book_copies ({','.join(copy_cols)}) VALUES ({placeholders})", vals)
            copy_id += 1

    print(f"  Imported {copy_id - 1} copies")

    # ── 4. Readers — 20 readers ────────────────────────────────────────
    print("Importing 20 readers...")
    clear(conn, "reader_accounts")
    clear(conn, "reader_credentials")
    clear(conn, "reader_notification_settings")

    selected_readers = readers_csv[:20]

    reader_cols = [
        "id","source_reader_id","reader_code","reader_type_code","reader_type_name",
        "name","phone_masked","phone_hash","email","status","credit_score",
        "registered_at","active_90d","current_borrow_count","borrow_suspended_until",
        "remark","created_at","updated_at",
    ]

    for idx, r in enumerate(selected_readers, start=1):
        vals = [idx] + [r.get(c, "") for c in reader_cols[1:]]
        placeholders = ",".join(["?"] * len(reader_cols))
        conn.execute(f"INSERT INTO reader_accounts ({','.join(reader_cols)}) VALUES ({placeholders})", vals)

    # Credentials
    cred_cols = ["id","reader_id","login_name","phone_hash","email","password_hash","status","last_login_at","created_at","updated_at"]
    for idx, r in enumerate(selected_readers, start=1):
        csv_reader_id = r["id"]
        cred = next((c for c in creds_csv if c["reader_id"] == csv_reader_id), None)
        vals = [
            idx, idx,
            cred["login_name"] if cred else r["reader_code"],
            cred["phone_hash"] if cred else "",
            cred["email"] if cred else "",
            cred["password_hash"] if cred else "pbkdf2_sha256$180000$placeholder_hash_imported",
            "active", None,
            r.get("created_at", ""), r.get("created_at", ""),
        ]
        placeholders = ",".join(["?"] * len(cred_cols))
        conn.execute(f"INSERT INTO reader_credentials ({','.join(cred_cols)}) VALUES ({placeholders})", vals)

    # Notification settings
    notif_cols = ["id","reader_id","borrow_due_enabled","reservation_arrival_enabled","system_notice_enabled","email_enabled","sms_enabled","created_at","updated_at"]
    for idx, r in enumerate(selected_readers, start=1):
        vals = [idx, idx, 1, 1, 1, 1 if r.get("email") else 0, 1, r.get("created_at", ""), r.get("created_at", "")]
        placeholders = ",".join(["?"] * len(notif_cols))
        conn.execute(f"INSERT INTO reader_notification_settings ({','.join(notif_cols)}) VALUES ({placeholders})", vals)

    print(f"  Imported {len(selected_readers)} readers with credentials & notification settings")

    # ── Commit ─────────────────────────────────────────────────────────
    conn.commit()
    conn.close()

    # ── Summary ────────────────────────────────────────────────────────
    print("\n=== Done ===")
    cats_used = set(b["category_code"] for b in selected)
    print(f"Books: {len(selected)} across {len(cats_used)} categories")
    print(f"Copies: {copy_id - 1}")
    print(f"Readers: {len(selected_readers)}")


if __name__ == "__main__":
    main()
