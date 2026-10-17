from __future__ import annotations

from sqlalchemy import text

from bookflow_core.core.database import get_session
from bookflow_core.services.location_service import repair_shelf_position_links


def run() -> dict:
    with get_session() as db:
        db.execute(text("UPDATE reservations SET status = 'ready_for_pickup' WHERE status IN ('reserved', 'ready')"))
        repair = repair_shelf_position_links(db, commit=False)
        db.commit()
        return {"reservation_status_normalized": True, "shelf_position_links": repair}


if __name__ == "__main__":
    print(run())
