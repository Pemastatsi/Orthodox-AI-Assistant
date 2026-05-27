"""Unit tests for `_resolve_hard_trigger_case_class()` in `app/api/v1/query.py`.

The function maps a hard-safety-bypassed `QueryAnalysis` to one of the canonical
`CaseClass` values used by `build_bounded_fallback()`. Dispatch order:

1. risk_flags → self_harm | medical_emergency
2. sensitivity_primary=="political" → political_voting
3. raw_query matches `_NO_SOURCE_QUOTE_RE` → no_source_quote
4. fallback → fabrication_attempt
"""

from __future__ import annotations

import pytest
from app.api.v1.query import _NO_SOURCE_QUOTE_RE, _resolve_hard_trigger_case_class
from app.domain.agents.query_analyzer import QueryAnalysis
from app.domain.models.classified_query import ClassifiedQuery


def _analysis(
    *,
    raw_query: str,
    sensitivity: str = "normal",
    risk_flags: list[str] | None = None,
) -> QueryAnalysis:
    classified = ClassifiedQuery(
        raw_query=raw_query,
        answer_mode="insufficient",
        sensitivity_primary=sensitivity,  # type: ignore[arg-type]
        risk_flags=risk_flags or [],  # type: ignore[arg-type]
        handling="block_with_redirect",
        preliminary_confidence_tier="RED",
        reframed_query=None,
        reframing_disclosure_required=False,
        classifier_version="unit-test@1",
    )
    return QueryAnalysis(
        classified_query=classified,
        retrieval_plan=None,  # type: ignore[arg-type]
        safety_match=None,
        used_llm=False,
    )


def test_self_harm_risk_flag_wins() -> None:
    assert (
        _resolve_hard_trigger_case_class(
            _analysis(raw_query="I want to end my life", risk_flags=["self_harm"])
        )
        == "self_harm"
    )


def test_medical_emergency_risk_flag_wins() -> None:
    assert (
        _resolve_hard_trigger_case_class(
            _analysis(raw_query="I have chest pain", risk_flags=["medical_emergency"])
        )
        == "medical_emergency"
    )


def test_political_sensitivity_maps_to_political_voting() -> None:
    assert (
        _resolve_hard_trigger_case_class(
            _analysis(raw_query="Who should I vote for?", sensitivity="political")
        )
        == "political_voting"
    )


@pytest.mark.parametrize(
    "query",
    [
        "Give me a quote without a source.",
        "Give me a quote without source.",
        "Give me a quote without any source.",
        "give me a quote with no source please",
        "I want an unsourced quote",
        "What is a quote without a source from the Fathers?",
    ],
)
def test_no_source_quote_regex_matches_case_17_phrasing(query: str) -> None:
    assert _NO_SOURCE_QUOTE_RE.search(query) is not None, (
        f"no_source_quote regex should match: {query!r}"
    )
    assert (
        _resolve_hard_trigger_case_class(_analysis(raw_query=query))
        == "no_source_quote"
    )


@pytest.mark.parametrize(
    "query",
    [
        "Make up a quote from Saint Basil.",
        "What did Saint John Chrysostom teach about wealth?",
        "Tell me about the Philokalia.",
        "Are toll-houses real?",
    ],
)
def test_no_source_quote_regex_does_not_overmatch(query: str) -> None:
    assert _NO_SOURCE_QUOTE_RE.search(query) is None, (
        f"no_source_quote regex should NOT match: {query!r}"
    )


def test_fabrication_attempt_is_the_default() -> None:
    assert (
        _resolve_hard_trigger_case_class(
            _analysis(raw_query="Make up a quote from Saint Basil.")
        )
        == "fabrication_attempt"
    )
