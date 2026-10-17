from __future__ import annotations

import os
import threading
from contextlib import suppress

from bookflow_core.core.database import get_session
from bookflow_core.services.circulation_service import scan_overdues

_stop_event = threading.Event()
_thread: threading.Thread | None = None
_lock = threading.Lock()


def _enabled() -> bool:
    return os.getenv("BOOKFLOW_OVERDUE_SCAN_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}


def _interval_seconds() -> int:
    try:
        return max(60, int(os.getenv("BOOKFLOW_OVERDUE_SCAN_INTERVAL_SECONDS", "3600")))
    except ValueError:
        return 3600


def _scan_once() -> None:
    with get_session() as db:
        scan_overdues(db, actor_type="system", actor_id="overdue_scheduler")


def _run_loop() -> None:
    if os.getenv("BOOKFLOW_OVERDUE_SCAN_ON_STARTUP", "true").strip().lower() not in {"0", "false", "no", "off"}:
        with suppress(Exception):
            _scan_once()
    while not _stop_event.wait(_interval_seconds()):
        with suppress(Exception):
            _scan_once()


def start_overdue_scheduler() -> bool:
    global _thread
    if not _enabled():
        return False
    with _lock:
        if _thread and _thread.is_alive():
            return True
        _stop_event.clear()
        _thread = threading.Thread(target=_run_loop, name="bookflow-overdue-scheduler", daemon=True)
        _thread.start()
        return True


def stop_overdue_scheduler() -> None:
    _stop_event.set()
