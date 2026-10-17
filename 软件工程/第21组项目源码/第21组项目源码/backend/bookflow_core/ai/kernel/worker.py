from __future__ import annotations

import os
import threading
from contextlib import suppress
from typing import Iterable

from bookflow_core.ai.kernel.agent import process_next_task
from bookflow_core.core.database import get_session

_stop_event = threading.Event()
_thread: threading.Thread | None = None
_lock = threading.Lock()


def _env_enabled(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() not in {"0", "false", "no", "off"}


def _env_int(name: str, default: int, minimum: int) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _queue_names(value: str | Iterable[str] | None = None) -> list[str | None]:
    if value is None:
        value = os.getenv("BOOKFLOW_AI_KERNEL_WORKER_QUEUE_NAMES", "")
    if isinstance(value, str):
        items = [item.strip() for item in value.split(",") if item.strip()]
    else:
        raw_items = list(value)
        if raw_items == [None]:
            return [None]
        items = [str(item).strip() for item in raw_items if item is not None and str(item).strip()]
    return items or [None]


def _worker_id(value: str | None = None) -> str:
    return str(value or os.getenv("BOOKFLOW_AI_KERNEL_WORKER_ID", "ai-kernel-worker"))


def worker_enabled() -> bool:
    return _env_enabled("BOOKFLOW_AI_KERNEL_WORKER_ENABLED", "true")


def worker_status() -> dict:
    return {
        "enabled": worker_enabled(),
        "running": bool(_thread and _thread.is_alive()),
        "worker_id": _worker_id(),
        "interval_seconds": _env_int("BOOKFLOW_AI_KERNEL_WORKER_INTERVAL_SECONDS", 5, 1),
        "batch_size": _env_int("BOOKFLOW_AI_KERNEL_WORKER_BATCH_SIZE", 3, 1),
        "lease_seconds": _env_int("BOOKFLOW_AI_KERNEL_WORKER_LEASE_SECONDS", 300, 30),
        "queue_names": _queue_names(),
    }


def run_ai_kernel_worker_once(
    *,
    worker_id: str | None = None,
    queue_names: str | Iterable[str] | None = None,
    batch_size: int | None = None,
    lease_seconds: int | None = None,
) -> dict:
    actor_id = _worker_id(worker_id)
    queues = _queue_names(queue_names)
    limit = max(1, int(batch_size or _env_int("BOOKFLOW_AI_KERNEL_WORKER_BATCH_SIZE", 3, 1)))
    lease = max(30, int(lease_seconds or _env_int("BOOKFLOW_AI_KERNEL_WORKER_LEASE_SECONDS", 300, 30)))
    processed: list[dict] = []
    errors: list[dict] = []

    for _ in range(limit):
        did_work = False
        for queue_name in queues:
            db = get_session()
            try:
                result = process_next_task(db, worker_id=actor_id, queue_name=queue_name, lease_seconds=lease, commit=True)
                if result.get("status") == "idle":
                    continue
                processed.append(result)
                did_work = True
            except Exception as exc:
                db.rollback()
                errors.append({"queue_name": queue_name, "error": str(exc)})
            finally:
                db.close()
        if not did_work:
            break

    return {
        "status": "ok" if not errors else "partial_failure",
        "worker_id": actor_id,
        "processed_count": len(processed),
        "error_count": len(errors),
        "processed": processed,
        "errors": errors,
    }


def _run_loop(worker_id: str, queue_names: list[str | None], interval_seconds: int, batch_size: int, lease_seconds: int) -> None:
    if _env_enabled("BOOKFLOW_AI_KERNEL_WORKER_RUN_ON_STARTUP", "true"):
        with suppress(Exception):
            run_ai_kernel_worker_once(worker_id=worker_id, queue_names=queue_names, batch_size=batch_size, lease_seconds=lease_seconds)
    while not _stop_event.wait(interval_seconds):
        with suppress(Exception):
            run_ai_kernel_worker_once(worker_id=worker_id, queue_names=queue_names, batch_size=batch_size, lease_seconds=lease_seconds)


def start_ai_kernel_worker(
    *,
    worker_id: str | None = None,
    queue_names: str | Iterable[str] | None = None,
    interval_seconds: int | None = None,
    batch_size: int | None = None,
    lease_seconds: int | None = None,
) -> bool:
    global _thread
    if not worker_enabled():
        return False
    actor_id = _worker_id(worker_id)
    queues = _queue_names(queue_names)
    interval = max(1, int(interval_seconds or _env_int("BOOKFLOW_AI_KERNEL_WORKER_INTERVAL_SECONDS", 5, 1)))
    limit = max(1, int(batch_size or _env_int("BOOKFLOW_AI_KERNEL_WORKER_BATCH_SIZE", 3, 1)))
    lease = max(30, int(lease_seconds or _env_int("BOOKFLOW_AI_KERNEL_WORKER_LEASE_SECONDS", 300, 30)))
    with _lock:
        if _thread and _thread.is_alive():
            return True
        _stop_event.clear()
        _thread = threading.Thread(
            target=_run_loop,
            args=(actor_id, queues, interval, limit, lease),
            name="bookflow-ai-kernel-worker",
            daemon=True,
        )
        _thread.start()
        return True


def stop_ai_kernel_worker() -> None:
    _stop_event.set()
