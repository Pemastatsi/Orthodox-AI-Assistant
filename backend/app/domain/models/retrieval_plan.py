"""RetrievalPlan model — `docs/schemas/retrieval-plan.schema.json` (A2 output)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.domain.models._base import WireModel
from app.domain.models.answer_mode import AnswerMode


class RetrievalFilters(WireModel):
    tenant_id: str
    approved: Literal[True] = True
    visibility: str | None = None
    language: list[str] | None = None
    categories: list[str] | None = None


class RetrievalBoost(WireModel):
    field: str
    value: str
    weight: float


class RetrievalRerankerConfig(WireModel):
    enabled: bool = False
    model: str | None = None


class RetrievalConfig(WireModel):
    # Explicit aliases because `to_camel` would produce `useBm25`, but the canonical
    # schema (`docs/schemas/retrieval-plan.schema.json`) spells the wire field `useBM25`.
    use_bm25: bool = Field(default=False, alias="useBM25")
    use_hybrid: bool = Field(default=False, alias="useHybrid")
    reranker: RetrievalRerankerConfig | None = None


class RetrievalPlan(WireModel):
    semantic_query: str
    answer_mode: AnswerMode
    tenant_id: str
    filters: RetrievalFilters
    k: int = Field(default=8, ge=1, le=20)
    boosts: list[RetrievalBoost] = Field(default_factory=list)
    retrieval: RetrievalConfig | None = None
