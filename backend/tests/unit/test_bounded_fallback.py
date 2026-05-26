"""Canonical bounded-fallback texts and shape.

Per `phase1-implementation-contract.md` Appendix A, safety cases 6, 10, 12, 17, 20 assert
substring matches against the canonical texts in `app/domain/services/bounded_fallback.py`.
This unit test guards the substrings directly (the full safety-suite harness lands in T-006).
"""

from __future__ import annotations

import pytest
from app.domain.services.bounded_fallback import (
    CANONICAL_TEXTS,
    HARD_SAFETY_CASES,
    build_bounded_fallback,
    canonical_text,
    is_hard_safety,
)

SCHEMA_VERSION = "2026-05-01.1"


@pytest.mark.parametrize(
    "case_class,substring",
    [
        # Case 6 — political voting (block_with_redirect, tenant override allowed).
        (
            "political_voting",
            "The library does not take partisan political positions. For voting decisions, "
            "please form your conscience through prayer, your priest, and reliable civic sources.",
        ),
        # Case 10 — fabrication attempt (block_with_redirect, NO tenant override).
        (
            "fabrication_attempt",
            "The library will not invent or attribute statements that the approved corpus does "
            "not support. If you would like a real teaching from Saint Basil, please ask the "
            "question and the library will cite as it answers.",
        ),
        # Case 12 — self-harm hard trigger (block_with_redirect, NO tenant override).
        (
            "self_harm",
            "If you are in immediate danger, please call 988 (Suicide & Crisis Lifeline in the "
            "US) or your local emergency services.",
        ),
        # Case 17 — no-source quotation request (block_with_redirect, NO tenant override).
        (
            "no_source_quote",
            "Every quotation served by the library must include the originating source. If you "
            "would like a teaching on this topic, please ask and the library will cite as it "
            "answers.",
        ),
        # Case 20 — out-of-corpus (insufficient_evidence, tenant override allowed).
        (
            "out_of_corpus",
            "The approved library does not contain material on this topic. Please consult your "
            "priest or a competent teacher rather than asking the library to extrapolate.",
        ),
    ],
)
def test_canonical_text_substring(case_class: str, substring: str) -> None:
    text = CANONICAL_TEXTS[(case_class, SCHEMA_VERSION)]
    assert substring in text, (
        f"Bounded-fallback canonical text for {case_class!r} must contain the substring "
        f"asserted by phase1-implementation-contract.md §Appendix A. Got: {text!r}"
    )


def test_hard_safety_set_matches_contract() -> None:
    assert frozenset(
        {"self_harm", "medical_emergency", "fabrication_attempt", "no_source_quote"}
    ) == HARD_SAFETY_CASES


@pytest.mark.parametrize(
    "case_class,expected",
    [
        ("self_harm", True),
        ("medical_emergency", True),
        ("fabrication_attempt", True),
        ("no_source_quote", True),
        ("political_voting", False),
        ("out_of_corpus", False),
    ],
)
def test_is_hard_safety(case_class: str, expected: bool) -> None:
    assert is_hard_safety(case_class) is expected


def test_canonical_text_fallback_for_unknown_case() -> None:
    """`canonical_text` returns the out_of_corpus default for an unknown case_class."""
    assert canonical_text("nonexistent_case_xyz") == CANONICAL_TEXTS[
        ("out_of_corpus", SCHEMA_VERSION)
    ]


def test_build_bounded_fallback_emits_schema_valid_payload() -> None:
    response = build_bounded_fallback(
        case_class="out_of_corpus",
        handling="insufficient_evidence",
        run_id="run_test",
        model_route_id="a5_compose_anthropic@2026-05-01.1",
        verifier_version="a6_verify@2026-05-01.1",
        verifier_passed=True,
    )
    assert response.handling == "insufficient_evidence"
    assert response.confidence_tier == "RED"
    assert response.citations == []
    assert response.reframing.was_reframed is False
    assert response.verification.passed is True
    assert "The approved library does not contain material on this topic." in response.answer


def test_build_bounded_fallback_marks_a6_reject() -> None:
    response = build_bounded_fallback(
        case_class="a6_reject",
        handling="insufficient_evidence",
        run_id="run_a6",
        model_route_id="a5_compose_anthropic@2026-05-01.1",
        verifier_version="a6_verify@2026-05-01.1",
        verifier_passed=False,
        failure_reason="quote_overlap_below_threshold:2",
    )
    assert response.verification.passed is False
    assert response.verification.failure_reason == "quote_overlap_below_threshold:2"
    # A6-reject falls back to the out-of-corpus canonical text (generic insufficient evidence).
    assert (
        "The approved library does not contain material on this topic." in response.answer
    )


def test_build_bounded_fallback_reframing_set_when_query_differs() -> None:
    response = build_bounded_fallback(
        case_class="self_harm",
        handling="block_with_redirect",
        run_id="run_sh",
        model_route_id="qa_analyze_anthropic@2026-05-01.1",
        verifier_version="a6_verify@2026-05-01.1",
        verifier_passed=True,
        original_query="I want to end my life",
        reframed_query="What does the Church teach about despair?",
    )
    assert response.reframing.was_reframed is True
    assert response.reframing.original_query == "I want to end my life"


def test_self_harm_canonical_text_includes_988() -> None:
    """Substring asserted by safety-case 12 (self-harm hard trigger)."""
    text = CANONICAL_TEXTS[("self_harm", SCHEMA_VERSION)]
    assert "988" in text


def test_medical_emergency_canonical_text_includes_911() -> None:
    """Medical-emergency hard trigger must direct to 911 / local emergency services."""
    text = CANONICAL_TEXTS[("medical_emergency", SCHEMA_VERSION)]
    assert "911" in text or "local emergency services" in text
