"""BillingUsage repository — `billing_usage` rollups.

Per ADR-0005: cache hits increment `served_answer_count`; cache misses that reach A5
increment `fresh_model_run_count`. One UPSERT per request lands here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text

from app.domain.models.billing_usage import BillingUsage
from app.domain.repositories._base import AsyncSession, assert_tenant
from app.domain.services.usage_service import compute_period_end, compute_period_start


def _row_to_obj(row: Any) -> BillingUsage:
    return BillingUsage(
        tenant_id=row["tenant_id"],
        period_start=row["period_start"],
        period_end=row["period_end"],
        served_answer_count=row["served_answer_count"],
        fresh_model_run_count=row["fresh_model_run_count"],
        prompt_tokens=row.get("prompt_tokens", 0),
        completion_tokens=row.get("completion_tokens", 0),
        embedding_tokens=row.get("embedding_tokens", 0),
        stripe_usage_record_id=row.get("stripe_usage_record_id"),
        reported_at=row.get("reported_at"),
    )


class BillingUsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def increment(
        self,
        *,
        tenant_id: str,
        served_answer_count: int = 0,
        fresh_model_run_count: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        embedding_tokens: int = 0,
        now: datetime | None = None,
    ) -> None:
        """UPSERT current-month row, adding the supplied deltas to existing counters."""
        assert_tenant(tenant_id)
        from datetime import UTC

        when = now or datetime.now(UTC)
        period_start = compute_period_start(when)
        period_end = compute_period_end(period_start)
        await self._session.execute(
            text(
                """
                INSERT INTO billing_usage (
                    tenant_id, period_start, period_end, served_answer_count,
                    fresh_model_run_count, prompt_tokens, completion_tokens,
                    embedding_tokens
                ) VALUES (
                    :tenant_id, :period_start, :period_end, :served, :fresh,
                    :prompt_tokens, :completion_tokens, :embedding_tokens
                )
                ON CONFLICT (tenant_id, period_start) DO UPDATE
                SET served_answer_count =
                        billing_usage.served_answer_count + EXCLUDED.served_answer_count,
                    fresh_model_run_count =
                        billing_usage.fresh_model_run_count + EXCLUDED.fresh_model_run_count,
                    prompt_tokens =
                        billing_usage.prompt_tokens + EXCLUDED.prompt_tokens,
                    completion_tokens =
                        billing_usage.completion_tokens + EXCLUDED.completion_tokens,
                    embedding_tokens =
                        billing_usage.embedding_tokens + EXCLUDED.embedding_tokens
                """
            ),
            {
                "tenant_id": tenant_id,
                "period_start": period_start,
                "period_end": period_end,
                "served": served_answer_count,
                "fresh": fresh_model_run_count,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "embedding_tokens": embedding_tokens,
            },
        )

    async def get_current(
        self, *, tenant_id: str, now: datetime | None = None
    ) -> BillingUsage | None:
        assert_tenant(tenant_id)
        from datetime import UTC

        period_start = compute_period_start(now or datetime.now(UTC))
        result = await self._session.execute(
            text(
                """
                SELECT * FROM billing_usage
                WHERE tenant_id = :tenant_id AND period_start = :period_start
                """
            ),
            {"tenant_id": tenant_id, "period_start": period_start},
        )
        row = result.mappings().one_or_none()
        return _row_to_obj(row) if row else None


__all__ = ["BillingUsageRepository"]
