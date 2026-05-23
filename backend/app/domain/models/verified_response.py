"""VerifiedResponse model — `docs/schemas/verified-response.schema.json` (final A6 output)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.domain.models._base import WireModel
from app.domain.models.classified_query import ConfidenceTier, Handling

CorpusOrigin = Literal["tenant", "starter_corpus"]


class Citation(WireModel):
    citation_id: str
    chunk_id: str
    source_id: str
    title: str
    source_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    chunk_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    approved: Literal[True] = True
    corpus_origin: CorpusOrigin
    work: str | None = None
    father: str | None = None
    page: str | None = None
    timestamp: str | None = None
    quote: str | None = None


class Verification(WireModel):
    passed: bool
    checked_at: datetime
    verifier_version: str
    failure_reason: str | None = None


class Reframing(WireModel):
    was_reframed: bool
    original_query: str | None = None
    reframed_query: str | None = None
    disclosure_text: str | None = None


class VerifiedResponseUsage(WireModel):
    served_answer_count: int = Field(ge=0, le=1)
    fresh_model_run_count: int = Field(ge=0, le=1)
    model_route_id: str
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)


class VerifiedResponse(WireModel):
    answer: str
    confidence_tier: ConfidenceTier
    handling: Handling
    citations: list[Citation] = Field(default_factory=list)
    verification: Verification
    reframing: Reframing
    usage: VerifiedResponseUsage
    served_from_cache: bool
    schema_version: str
    run_id: str
