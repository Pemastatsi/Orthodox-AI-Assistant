"""FlaggedQuery model — `docs/schemas/flagged-query.schema.json`."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.domain.models._base import WireModel

FlagReason = Literal[
    "red_tier",
    "insufficient_evidence",
    "block_with_redirect",
    "verifier_failed",
    "hard_safety_trigger",
    "user_reported",
]


class FlaggedQuery(WireModel):
    flagged_query_id: str
    tenant_id: str
    user_id: str
    query_text_redacted: str
    flag_reason: FlagReason
    created_at: datetime
    run_id: str | None = None
    raw_sensitive_log_id: str | None = None
    sensitivity_primary: str | None = None
    risk_flags: list[str] = Field(default_factory=list)
    embedding: list[float] | None = None
    embedding_model: str | None = None
    cluster_id: str | None = None
