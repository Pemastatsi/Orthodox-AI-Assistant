"""compute_period_start / compute_period_end boundary math."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from app.domain.services.usage_service import compute_period_end, compute_period_start


def test_period_start_first_of_month_midnight_utc() -> None:
    now = datetime(2026, 5, 27, 13, 42, 1, tzinfo=UTC)
    assert compute_period_start(now) == datetime(2026, 5, 1, tzinfo=UTC)


def test_period_start_normalises_naive_to_utc() -> None:
    naive = datetime(2026, 5, 27, 13, 42, 1)
    assert compute_period_start(naive) == datetime(2026, 5, 1, tzinfo=UTC)


def test_period_start_normalises_non_utc_tz() -> None:
    # 2026-06-01 01:30 in UTC+3 == 2026-05-31 22:30 UTC → May period.
    eet = timezone(timedelta(hours=3))
    aware = datetime(2026, 6, 1, 1, 30, tzinfo=eet)
    assert compute_period_start(aware) == datetime(2026, 5, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    "ps,expected",
    [
        (datetime(2026, 5, 1, tzinfo=UTC), datetime(2026, 6, 1, tzinfo=UTC)),
        (datetime(2026, 12, 1, tzinfo=UTC), datetime(2027, 1, 1, tzinfo=UTC)),
        (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 2, 1, tzinfo=UTC)),
        (datetime(2026, 2, 1, tzinfo=UTC), datetime(2026, 3, 1, tzinfo=UTC)),
    ],
)
def test_period_end_first_of_next_month(ps: datetime, expected: datetime) -> None:
    assert compute_period_end(ps) == expected
