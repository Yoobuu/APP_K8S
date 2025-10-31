from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def ensure_utc(dt: datetime) -> datetime:
    """Return datetime normalized to UTC with timezone information."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def floor_to_hour(dt: datetime) -> datetime:
    """Truncate datetime to the beginning of the hour."""
    normalized = ensure_utc(dt)
    return normalized.replace(minute=0, second=0, microsecond=0)


def norm_enum(value: Optional[str]) -> str:
    """Normalize enum-like strings for deduplication keys."""
    if not value:
        return ""
    return value.strip().lower()

