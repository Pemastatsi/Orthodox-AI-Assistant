"""RetrievalEvalRun model — `docs/schemas/retrieval-eval-run.schema.json`.

One execution of the retrieval-eval suite for a route under test against a pinned gold-set
version. Mirrors `safety_suite_runs` (ADR-0004); the second of two binding gates for
`purpose IN ('embedding','rerank')` route certification (`docs/contracts/retrieval-eval-suite.md`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.domain.models._base import WireModel

RetrievalEvalPurpose = Literal["embedding", "rerank"]
RetrievalConfigLabel = Literal["dense_only", "hybrid", "hybrid_rerank"]


class RetrievalEvalRegression(WireModel):
    metric: str
    baseline: float
    observed: float


class RetrievalEvalRun(WireModel):
    retrieval_eval_run_id: str
    route_id: str
    purpose: RetrievalEvalPurpose
    config_label: RetrievalConfigLabel | None = None
    gold_set_tenant_id: str
    gold_set_version: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}\.[0-9]+$")
    case_count: int = Field(ge=0)
    scores: dict[str, float]
    passed: bool
    is_first_run: bool = False
    judge_applied: bool = False
    regressions: list[RetrievalEvalRegression] | None = None
    initiated_by: str
    started_at: datetime
    finished_at: datetime
    created_at: datetime | None = None
