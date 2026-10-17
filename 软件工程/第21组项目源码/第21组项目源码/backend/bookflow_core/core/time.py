from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

# China Standard Time (UTC+8)
CST = timezone(timedelta(hours=8))


def now() -> datetime:
    """Return current datetime in China Standard Time (UTC+8, tz-aware)."""
    return datetime.now(CST)


def today() -> date:
    """Return current date in China Standard Time."""
    return datetime.now(CST).date()
