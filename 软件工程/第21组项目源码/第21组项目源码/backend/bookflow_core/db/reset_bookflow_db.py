from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from bookflow_core.core.database import create_db
from bookflow_core.db.models import Base
from bookflow_core.db.views import VIEW_SQL

DEFAULT_DB = BACKEND_ROOT / "data" / "bookflow.db"


def _url_for(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def reset(db_path: Path = DEFAULT_DB) -> dict:
    if db_path.stem != "bookflow":
        raise ValueError(f"Refusing to reset a database not named bookflow: {db_path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    create_db(_url_for(db_path))
    return {
        "ok": True,
        "database": str(db_path),
        "tables": len(Base.metadata.tables),
        "views": len(VIEW_SQL),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete and recreate the BookFlow SQLite database schema.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    print(json.dumps(reset(args.db), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

