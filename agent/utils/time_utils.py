# agent/utils/time_utils.py

from datetime import datetime, timezone, timedelta
from typing import Optional

IST_OFFSET = timedelta(hours=5, minutes=30)
IST = timezone(IST_OFFSET)


def utc_now() -> datetime:
    """
    Returns current UTC time (timezone-aware).
    """
    return datetime.now(timezone.utc)


def parse_utc_iso(ts: Optional[str]) -> Optional[datetime]:
    """
    Parse ISO 8601 UTC timestamp from Frejun / APIs.
    Example: 2026-01-29T07:31:47.947Z
    """
    if not ts:
        return None

    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def to_ist(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Convert UTC datetime to IST.
    """
    if not dt:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(IST)


def format_ist(dt: Optional[datetime]) -> Optional[str]:
    """
    Format datetime in IST for humans.
    Example: 29 Jan 2026, 12:58:47 PM IST
    """
    if not dt:
        return None

    ist_dt = to_ist(dt)
    return ist_dt.strftime("%d %b %Y, %I:%M:%S %p IST")


def iso_ist(dt: Optional[datetime]) -> Optional[str]:
    """
    ISO 8601 IST string (for storage / debugging).
    """
    if not dt:
        return None

    return to_ist(dt).isoformat()
