from datetime import UTC, datetime

import pytest

from valor.runtime_gateway.domain.usage_limit import decide_usage_limit, utc_day_window


@pytest.mark.parametrize(
    ("at", "start", "end"),
    [
        (
            datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 2, 0, 0, tzinfo=UTC),
        ),
        (
            datetime(2026, 1, 1, 23, 59, 59, 999000, tzinfo=UTC),
            datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 2, 0, 0, tzinfo=UTC),
        ),
        (
            datetime(2026, 1, 2, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 2, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 3, 0, 0, tzinfo=UTC),
        ),
    ],
)
def test_utc_calendar_day_window(at: datetime, start: datetime, end: datetime) -> None:
    assert utc_day_window(at) == (window := utc_day_window(start))
    assert (window.start, window.end) == (start, end)


@pytest.mark.parametrize(
    ("consumed", "allowed"),
    [(0, True), (900, True), (901, False), (1000, False)],
)
def test_usage_limit_boundary(consumed: int, allowed: bool) -> None:
    window = utc_day_window(datetime(2026, 1, 1, tzinfo=UTC))
    decision = decide_usage_limit(
        consumed_units=consumed, limit_units=1000, allowance_units=100, window=window
    )
    assert decision.allowed is allowed
    assert decision.consumed_units == consumed


def test_usage_window_rejects_naive_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        utc_day_window(datetime(2026, 1, 1))
