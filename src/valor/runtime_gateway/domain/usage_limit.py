"""Explicit UTC-day Runtime Principal usage-limit semantics."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True, slots=True)
class UsageWindow:
    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class UsageLimitDecision:
    allowed: bool
    consumed_units: int
    limit_units: int
    allowance_units: int
    window: UsageWindow


def utc_day_window(at: datetime) -> UsageWindow:
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Usage window time must be timezone-aware.")
    utc_at = at.astimezone(UTC)
    start = utc_at.replace(hour=0, minute=0, second=0, microsecond=0)
    return UsageWindow(start, start + timedelta(days=1))


def decide_usage_limit(
    *, consumed_units: int, limit_units: int, allowance_units: int, window: UsageWindow
) -> UsageLimitDecision:
    if consumed_units < 0:
        raise ValueError("Consumed usage must not be negative.")
    if limit_units <= 0 or allowance_units <= 0 or allowance_units > limit_units:
        raise ValueError("Usage limit configuration is invalid.")
    return UsageLimitDecision(
        consumed_units + allowance_units <= limit_units,
        consumed_units,
        limit_units,
        allowance_units,
        window,
    )
