from __future__ import annotations

import argparse
import json
from pathlib import Path

from import_bookflow_csv_dataset import (
    resolve_csv_dir,
    resolve_db_path,
    validate_database,
    validation_rows,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the imported BookFlow CSV dataset against the SQLite database.")
    parser.add_argument("--csv-dir", type=Path, default=None, help="CSV package directory containing 00_load_order.txt.")
    parser.add_argument("--db", type=Path, default=None, help="SQLite database path. Defaults to backend/data/bookflow.db.")
    parser.add_argument("--json", action="store_true", help="Print the full validation payload as JSON.")
    args = parser.parse_args()

    csv_dir = resolve_csv_dir(args.csv_dir)
    db_path = resolve_db_path(args.db)
    result = validate_database(db_path, csv_dir)
    print(f"csv_dir={csv_dir}")
    print(f"db_path={db_path}")
    print(f"ok={result['ok']}")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for row in validation_rows(result):
            print(f"{row['section']},{row['name']},{row['expected']},{row['actual']},{row['status']}")
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
