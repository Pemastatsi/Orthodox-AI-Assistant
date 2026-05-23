"""BillingUsage model — `docs/schemas/billing-usage.schema.json`."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.domain.models._base import WireModel


class BillingUsage(WireModel):
    tenant_id: str
    period_start: datetime
    period_end: datetime
    served_answer_count: int = Field(ge=0)
    fresh_model_run_count: int = Field(ge=0)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    embedding_tokens: int = Field(default=0, ge=0)
    stripe_usage_record_id: str | None = None
    reported_at: datetime | None = None
