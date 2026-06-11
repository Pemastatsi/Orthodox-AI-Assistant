"""Unit tests for the usage metering service (T-005 billing, BILLING_MODE)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.services.metering_service import (
    local_usage_record_id,
    resolve_inline_usage_record_id,
)


def _period(year: int = 2026, month: int = 6) -> datetime:
    return datetime(year, month, 1, tzinfo=UTC)


def test_local_usage_record_id_is_deterministic_per_tenant_month() -> None:
    pid = _period(2026, 6)
    assert local_usage_record_id("tn_orthodoxethos", pid) == "unmetered_202606_tn_orthodoxethos"
    # Same inputs → same id; idempotent stamping relies on this.
    assert local_usage_record_id("tn_orthodoxethos", pid) == local_usage_record_id(
        "tn_orthodoxethos", pid
    )


def test_local_usage_record_id_varies_by_month_and_tenant() -> None:
    assert local_usage_record_id("tn_a", _period(2026, 6)) != local_usage_record_id(
        "tn_a", _period(2026, 7)
    )
    assert local_usage_record_id("tn_a", _period(2026, 6)) != local_usage_record_id(
        "tn_b", _period(2026, 6)
    )


def test_resolve_inline_local_mode_returns_local_id() -> None:
    pid = _period()
    assert resolve_inline_usage_record_id(
        "local", tenant_id="tn_a", period_start=pid
    ) == local_usage_record_id("tn_a", pid)


def test_resolve_inline_stripe_mode_defers_to_reporter() -> None:
    # stripe mode reports out-of-band; nothing is stamped inline on the hot path.
    assert (
        resolve_inline_usage_record_id("stripe", tenant_id="tn_a", period_start=_period())
        is None
    )


def test_resolve_inline_unknown_mode_defers() -> None:
    assert (
        resolve_inline_usage_record_id("bogus", tenant_id="tn_a", period_start=_period())
        is None
    )
