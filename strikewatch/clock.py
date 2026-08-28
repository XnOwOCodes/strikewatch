"""US/Eastern clock. Tests freeze time via Settings.now / STRIKEWATCH_NOW."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

RTH_OPEN_MIN = 9 * 60 + 30
RTH_CLOSE_MIN = 16 * 60


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ET)
    return dt.astimezone(ET)


def now_et(frozen: datetime | None = None) -> datetime:
    if frozen is None:
        return datetime.now(ET)
    if frozen.tzinfo is None:
        return frozen.replace(tzinfo=ET)
    return frozen.astimezone(ET)


def is_us_regular_hours(ts: datetime) -> bool:
    """Mon–Fri 09:30–16:00 America/New_York. No holiday calendar on purpose."""
    local = now_et(ts)
    if local.weekday() >= 5:
        return False
    minutes = local.hour * 60 + local.minute
    return RTH_OPEN_MIN <= minutes < RTH_CLOSE_MIN


def iso(ts: datetime | None = None) -> str:
    return now_et(ts).isoformat()
