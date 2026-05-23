"""ClassifiedQuery model — `docs/schemas/classified-query.schema.json` (A1 output)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.domain.models._base import WireModel
from app.domain.models.answer_mode import AnswerMode

SensitivityPrimary = Literal[
    "normal",
    "pastoral_advice",
    "political",
    "medical",
    "comparative_religion",
    "canonical_dispute",
    "other_sensitive",
]
RiskFlag = Literal[
    "self_harm",
    "medical_emergency",
    "canonical_dispute_active",
    "minor_protection",
]
Handling = Literal[
    "answer",
    "answer_with_disclaimer",
    "reframe_to_teaching",
    "block_with_redirect",
    "insufficient_evidence",
]
ConfidenceTier = Literal["GREEN", "YELLOW", "RED"]


class ClassifiedQuery(WireModel):
    raw_query: str = Field(min_length=1)
    answer_mode: AnswerMode
    sensitivity_primary: SensitivityPrimary
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    handling: Handling
    preliminary_confidence_tier: ConfidenceTier
    reframed_query: str | None = None
    reframing_disclosure_required: bool = False
    classifier_version: str | None = None
