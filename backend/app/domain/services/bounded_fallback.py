"""Canonical bounded-fallback responses per `phase1-implementation-contract.md` Appendix A.

The hard-safety templates (cases 10, 12, 17) are platform-fixed and NEVER tenant-overridable.
The soft-handled templates (cases 6, 20) accept a tenant `disclaimerTemplateId` override of the
closing line only — that override happens in T-006 (admin/tenant config); this module exposes
the canonical defaults only.

Any change to these constants requires a founder review and a safety-suite run. The unit tests
in `tests/unit/test_bounded_fallback.py` plus the safety-suite cases 6/10/12/17/20 (T-006) will
fail loudly if a substring drift is introduced.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final, Literal

from app.domain.models.classified_query import ConfidenceTier, Handling
from app.domain.models.verified_response import (
    Reframing,
    Verification,
    VerifiedResponse,
    VerifiedResponseUsage,
)

# Phase 1 schema version used in canonical-text keys. Bump when the underlying schema bumps.
_SCHEMA_VERSION: Final[str] = "2026-05-01.1"

# (case_class, schema_version) → canonical answer text.
# Each substring listed in `phase1-implementation-contract.md` Appendix A is contained verbatim.
CANONICAL_TEXTS: Final[dict[tuple[str, str], str]] = {
    ("political_voting", _SCHEMA_VERSION): (
        "The library does not take partisan political positions. For voting decisions, "
        "please form your conscience through prayer, your priest, and reliable civic sources."
    ),
    ("fabrication_attempt", _SCHEMA_VERSION): (
        "The library will not invent or attribute statements that the approved corpus does "
        "not support. If you would like a real teaching from Saint Basil, please ask the "
        "question and the library will cite as it answers."
    ),
    ("self_harm", _SCHEMA_VERSION): (
        "If you are in immediate danger, please call 988 (Suicide & Crisis Lifeline in the "
        "US) or your local emergency services. If you are outside the US, please contact "
        "your local emergency services. The library cannot provide personal crisis support "
        "and is not a substitute for trained human help."
    ),
    ("medical_emergency", _SCHEMA_VERSION): (
        "If you are experiencing a medical emergency, please call 911 (US) or your local "
        "emergency services immediately. The library is not a medical resource and cannot "
        "provide diagnosis or treatment guidance."
    ),
    ("no_source_quote", _SCHEMA_VERSION): (
        "Every quotation served by the library must include the originating source. If you "
        "would like a teaching on this topic, please ask and the library will cite as it "
        "answers."
    ),
    ("out_of_corpus", _SCHEMA_VERSION): (
        "The approved library does not contain material on this topic. Please consult your "
        "priest or a competent teacher rather than asking the library to extrapolate."
    ),
}

# Hard-safety cases are platform-fixed: tenants MUST NOT be able to override them.
HARD_SAFETY_CASES: Final[frozenset[str]] = frozenset(
    {"self_harm", "medical_emergency", "fabrication_attempt", "no_source_quote"}
)

CaseClass = Literal[
    "political_voting",
    "fabrication_attempt",
    "self_harm",
    "medical_emergency",
    "no_source_quote",
    "out_of_corpus",
    "a6_reject",
    "insufficient_evidence_generic",
]


def canonical_text(case_class: str, schema_version: str = _SCHEMA_VERSION) -> str:
    """Look up the canonical text for a case_class. Falls back to a generic out-of-corpus
    message when no specific case matches (e.g. plain insufficient_evidence or a6_reject)."""
    if (case_class, schema_version) in CANONICAL_TEXTS:
        return CANONICAL_TEXTS[(case_class, schema_version)]
    return CANONICAL_TEXTS[("out_of_corpus", schema_version)]


def is_hard_safety(case_class: str) -> bool:
    return case_class in HARD_SAFETY_CASES


def build_bounded_fallback(
    *,
    case_class: CaseClass,
    handling: Handling,
    run_id: str,
    model_route_id: str,
    confidence_tier: ConfidenceTier = "RED",
    verifier_version: str,
    verifier_passed: bool,
    schema_version: str = _SCHEMA_VERSION,
    failure_reason: str | None = None,
    original_query: str | None = None,
    reframed_query: str | None = None,
    served_from_cache: bool = False,
) -> VerifiedResponse:
    """Build a `BoundedFallbackResponse` (per verified-response.schema.json oneOf branch).

    `citations` is always empty for a bounded fallback. `reframing.wasReframed` is True only
    when the original query was reframed before the bounded path was taken; otherwise it is
    False, matching `phase1-implementation-contract.md` §Bounded Fallback Response Shapes.
    """
    answer_text = canonical_text(case_class, schema_version)
    was_reframed = reframed_query is not None and reframed_query != original_query
    return VerifiedResponse(
        answer=answer_text,
        confidence_tier=confidence_tier,
        handling=handling,
        citations=[],
        verification=Verification(
            passed=verifier_passed,
            checked_at=datetime.now(UTC),
            verifier_version=verifier_version,
            failure_reason=failure_reason,
        ),
        reframing=Reframing(
            was_reframed=was_reframed,
            original_query=original_query if was_reframed else None,
            reframed_query=reframed_query if was_reframed else None,
            disclosure_text=None,
        ),
        usage=VerifiedResponseUsage(
            served_answer_count=1,
            fresh_model_run_count=0,
            model_route_id=model_route_id,
        ),
        served_from_cache=served_from_cache,
        schema_version=schema_version,
        run_id=run_id,
    )


__all__ = [
    "CANONICAL_TEXTS",
    "CaseClass",
    "HARD_SAFETY_CASES",
    "build_bounded_fallback",
    "canonical_text",
    "is_hard_safety",
]
