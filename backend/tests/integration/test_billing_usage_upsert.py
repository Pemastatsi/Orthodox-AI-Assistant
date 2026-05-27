"""BillingUsageRepository.increment UPSERT semantics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_first_increment_inserts_row(seed_tenant: tuple[str, str]) -> None:
    tenant_id, _ = seed_tenant
    from app.domain.repositories._base import session_scope
    from app.domain.repositories.billing_usage_repository import BillingUsageRepository

    async with session_scope() as session:
        repo = BillingUsageRepository(session)
        await repo.increment(
            tenant_id=tenant_id,
            served_answer_count=1,
            fresh_model_run_count=1,
            prompt_tokens=120,
            completion_tokens=42,
        )

    async with session_scope() as session:
        repo = BillingUsageRepository(session)
        row = await repo.get_current(tenant_id=tenant_id)

    assert row is not None
    assert row.served_answer_count == 1
    assert row.fresh_model_run_count == 1
    assert row.prompt_tokens == 120
    assert row.completion_tokens == 42


@pytest.mark.asyncio
async def test_second_increment_upserts_existing_row(seed_tenant: tuple[str, str]) -> None:
    tenant_id, _ = seed_tenant
    from app.domain.repositories._base import session_scope
    from app.domain.repositories.billing_usage_repository import BillingUsageRepository

    async with session_scope() as session:
        repo = BillingUsageRepository(session)
        await repo.increment(tenant_id=tenant_id, served_answer_count=1, fresh_model_run_count=1)
        await repo.increment(tenant_id=tenant_id, served_answer_count=1, fresh_model_run_count=0)
        await repo.increment(tenant_id=tenant_id, served_answer_count=1, fresh_model_run_count=0)

    async with session_scope() as session:
        repo = BillingUsageRepository(session)
        row = await repo.get_current(tenant_id=tenant_id)

    assert row is not None
    assert row.served_answer_count == 3
    assert row.fresh_model_run_count == 1


@pytest.mark.asyncio
async def test_period_boundary_creates_new_row(seed_tenant: tuple[str, str]) -> None:
    """A query in May and a query in June land in distinct rows."""
    tenant_id, _ = seed_tenant
    from app.domain.repositories._base import session_scope
    from app.domain.repositories.billing_usage_repository import BillingUsageRepository

    may = datetime(2026, 5, 15, 12, 0, tzinfo=UTC)
    june = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)

    async with session_scope() as session:
        repo = BillingUsageRepository(session)
        await repo.increment(tenant_id=tenant_id, served_answer_count=2, now=may)
        await repo.increment(tenant_id=tenant_id, served_answer_count=5, now=june)

    async with session_scope() as session:
        repo = BillingUsageRepository(session)
        may_row = await repo.get_current(tenant_id=tenant_id, now=may)
        june_row = await repo.get_current(tenant_id=tenant_id, now=june)

    assert may_row is not None and may_row.served_answer_count == 2
    assert june_row is not None and june_row.served_answer_count == 5
    assert may_row.period_start != june_row.period_start


@pytest.mark.asyncio
async def test_zero_deltas_still_creates_row(seed_tenant: tuple[str, str]) -> None:
    """An increment with all zero deltas creates the row but never decrements."""
    tenant_id, _ = seed_tenant
    from app.domain.repositories._base import session_scope
    from app.domain.repositories.billing_usage_repository import BillingUsageRepository

    when = datetime.now(UTC) - timedelta(days=2)
    async with session_scope() as session:
        repo = BillingUsageRepository(session)
        await repo.increment(tenant_id=tenant_id, now=when)

    async with session_scope() as session:
        repo = BillingUsageRepository(session)
        row = await repo.get_current(tenant_id=tenant_id, now=when)

    assert row is not None
    assert row.served_answer_count == 0
    assert row.fresh_model_run_count == 0
