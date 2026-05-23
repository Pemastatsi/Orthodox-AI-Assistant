"""RunTrace model — `docs/schemas/run-trace.schema.json`."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.domain.models._base import WireModel
from app.domain.models.classified_query import ConfidenceTier, Handling

StageName = Literal[
    "a1_a2_query_analyzer",
    "a3_retrieval",
    "a4_evidence_packager",
    "a5_composer",
    "a6_verifier",
    "cache_lookup",
    "cache_store",
]
StageOutcome = Literal["ok", "fallback", "error", "skipped"]


class Stage(WireModel):
    stage: StageName
    started_at: datetime
    finished_at: datetime
    outcome: StageOutcome
    model_route_id: str | None = None
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    error_code: str | None = None
    notes: str | None = Field(default=None, max_length=256)
    details: dict[str, Any] = Field(default_factory=dict)


class RunTraceUsage(WireModel):
    served_answer_count: int = Field(ge=0, le=1)
    fresh_model_run_count: int = Field(ge=0, le=1)


class RunTrace(WireModel):
    run_id: str
    tenant_id: str
    user_id: str
    started_at: datetime
    stages: list[Stage] = Field(default_factory=list)
    cache_hit: bool
    usage: RunTraceUsage
    session_id: str | None = None
    finished_at: datetime | None = None
    final_handling: Handling | None = None
    final_confidence_tier: ConfidenceTier | None = None
    verifier_passed: bool | None = None
    evidence_packet_ref: str | None = None
