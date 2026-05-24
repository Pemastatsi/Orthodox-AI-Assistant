"""Tests for `app.domain.agents.query_analyzer.QueryAnalyzer`."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.auth import make_dev_principal
from app.domain.agents.query_analyzer import QueryAnalyzer
from app.domain.services.safety_config import load_sensitivity_keywords

from tests.fixtures.fakes import (
    FakeStructuredProvider,
    RefusingStructuredProvider,
    default_query_analyzer_responder,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONFIG_PATH = _REPO_ROOT / "config" / "sensitivity_keywords.yaml"


@pytest.fixture()
def safety_config():
    return load_sensitivity_keywords(_CONFIG_PATH)


@pytest.fixture()
def principal():
    return make_dev_principal(tenant_id="tn_test", role="member", user_id="usr_test")


def _analyzer(provider, safety_config):
    return QueryAnalyzer(
        provider=provider,
        safety_config=safety_config,
        prompt_version="qa_analyze@2026-05-01.1",
        model_route_id="fake@1",
    )


async def test_hard_trigger_short_circuits_no_llm_call(safety_config, principal):
    provider = FakeStructuredProvider()
    analyzer = _analyzer(provider, safety_config)

    result = await analyzer.analyze(
        query_text="I want to kill myself tonight",
        principal=principal,
        run_id="run_hard",
    )

    assert result.used_llm is False
    assert result.safety_match is not None
    assert result.safety_match.rule_id == "sk_self_harm_en_001"
    assert result.classified_query.handling == "block_with_redirect"
    assert result.classified_query.preliminary_confidence_tier == "RED"
    assert "self_harm" in result.classified_query.risk_flags
    assert provider.calls == []  # no LLM call


async def test_soft_trigger_flows_to_llm_with_candidate_hint(safety_config, principal):
    provider = FakeStructuredProvider()
    analyzer = _analyzer(provider, safety_config)

    await analyzer.analyze(
        query_text="should I divorce my wife",
        principal=principal,
        run_id="run_soft",
    )

    assert len(provider.calls) == 1
    user_text = next(
        m.content for m in provider.calls[0]["messages"] if m.role == "user"
    )
    assert "should I divorce my wife" in user_text
    assert "sk_pastoral_advice_divorce_en_001" in user_text


async def test_no_trigger_calls_llm_without_candidate_hint(safety_config, principal):
    provider = FakeStructuredProvider()
    analyzer = _analyzer(provider, safety_config)

    result = await analyzer.analyze(
        query_text="what do the Fathers teach about prayer?",
        principal=principal,
        run_id="run_prayer",
    )

    assert result.safety_match is None
    assert result.used_llm is True
    assert len(provider.calls) == 1
    user_text = next(
        m.content for m in provider.calls[0]["messages"] if m.role == "user"
    )
    assert "Keyword pre-screen" not in user_text


async def test_semantic_query_invariant_overrides_llm(safety_config, principal):
    """ADR-0007: semanticQuery MUST equal reframedQuery ?? rawQuery; any drift is overridden."""

    def responder(query_text, schema):
        classified, plan = default_query_analyzer_responder(query_text, schema)
        plan["semanticQuery"] = "this is a model-rewritten version of the query"
        return classified, plan

    provider = FakeStructuredProvider(responder=responder)
    analyzer = _analyzer(provider, safety_config)

    result = await analyzer.analyze(
        query_text="what do the Fathers teach about prayer?",
        principal=principal,
        run_id="run_invariant",
    )

    assert (
        result.retrieval_plan.semantic_query == "what do the Fathers teach about prayer?"
    )


async def test_reframed_query_drives_semantic_query(safety_config, principal):
    """When the LLM reframes, semanticQuery follows the reframing, not the raw query."""

    def responder(query_text, schema):
        classified, plan = default_query_analyzer_responder(query_text, schema)
        classified["reframedQuery"] = "What does the Church teach about marriage?"
        classified["reframingDisclosureRequired"] = True
        classified["sensitivityPrimary"] = "pastoral_advice"
        classified["handling"] = "reframe_to_teaching"
        plan["semanticQuery"] = "What does the Church teach about marriage?"
        return classified, plan

    provider = FakeStructuredProvider(responder=responder)
    analyzer = _analyzer(provider, safety_config)

    result = await analyzer.analyze(
        query_text="should I divorce my wife",
        principal=principal,
        run_id="run_reframe",
    )

    assert result.classified_query.reframed_query == "What does the Church teach about marriage?"
    assert result.retrieval_plan.semantic_query == "What does the Church teach about marriage?"


async def test_tenant_id_overridden_from_principal(safety_config, principal):
    """LLM-emitted tenantId is ALWAYS overwritten with Principal.tenantId."""

    def responder(query_text, schema):
        classified, plan = default_query_analyzer_responder(query_text, schema)
        plan["tenantId"] = "tn_evil"
        plan["filters"]["tenantId"] = "tn_evil"
        return classified, plan

    provider = FakeStructuredProvider(responder=responder)
    analyzer = _analyzer(provider, safety_config)

    result = await analyzer.analyze(
        query_text="benign question about the Fathers",
        principal=principal,
        run_id="run_tenant",
    )

    assert result.retrieval_plan.tenant_id == "tn_test"
    assert result.retrieval_plan.filters.tenant_id == "tn_test"


async def test_raw_query_is_restamped_verbatim(safety_config, principal):
    """Even if the LLM drops or alters rawQuery, we re-stamp it from the request."""

    def responder(query_text, schema):
        classified, plan = default_query_analyzer_responder(query_text, schema)
        classified["rawQuery"] = "LLM-paraphrased version"
        return classified, plan

    provider = FakeStructuredProvider(responder=responder)
    analyzer = _analyzer(provider, safety_config)

    result = await analyzer.analyze(
        query_text="What is the Orthodox view of the Eucharist?",
        principal=principal,
        run_id="run_rawquery",
    )

    assert (
        result.classified_query.raw_query
        == "What is the Orthodox view of the Eucharist?"
    )


async def test_refusal_falls_back_deterministically(safety_config, principal):
    provider = RefusingStructuredProvider()
    analyzer = _analyzer(provider, safety_config)

    result = await analyzer.analyze(
        query_text="benign question",
        principal=principal,
        run_id="run_refusal",
    )

    assert result.classified_query.handling == "insufficient_evidence"
    assert result.classified_query.sensitivity_primary == "normal"
    assert result.classified_query.classifier_version == "deterministic_a1@refusal_fallback"
    assert result.used_llm is True


async def test_invalid_payload_falls_back(safety_config, principal):
    def responder(query_text, schema):
        # Emit a classifiedQuery missing required fields → Pydantic raises ValidationError.
        return {"rawQuery": query_text}, {}

    provider = FakeStructuredProvider(responder=responder)
    analyzer = _analyzer(provider, safety_config)

    result = await analyzer.analyze(
        query_text="benign question",
        principal=principal,
        run_id="run_invalid",
    )

    assert result.classified_query.handling == "insufficient_evidence"
    assert result.classified_query.classifier_version == "deterministic_a1@refusal_fallback"
