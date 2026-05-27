"""Billing-period math for `billing_usage` rollups.

ADR-0005 §1 + db-schema.md §billing_usage: rows are keyed by
`(tenant_id, period_start)` where `period_start` is the first day of the current UTC
month, midnight, tz-aware. `period_end` is the first of the next month.
"""

from __future__ import annotations

from datetime import UTC, datetime


def compute_period_start(now: datetime) -> datetime:
    """First-of-month UTC midnight for the month containing `now`."""
    now = now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)
    return datetime(now.year, now.month, 1, tzinfo=UTC)


def compute_period_end(period_start: datetime) -> datetime:
    """First-of-next-month UTC midnight. `period_start` must already be a period start."""
    year = period_start.year + (1 if period_start.month == 12 else 0)
    month = 1 if period_start.month == 12 else period_start.month + 1
    return datetime(year, month, 1, tzinfo=UTC)


__all__ = ["compute_period_end", "compute_period_start"]
