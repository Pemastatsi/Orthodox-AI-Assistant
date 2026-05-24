"""A1 + A2 QueryAnalyzer.

Implements the combined A1 (sensitivity classification) + A2 (retrieval planning) step
of the Phase 1 query pipeline per `docs/contracts/phase1-implementation-contract.md`
and ADR-0007.

Pipeline:

1. Hard-trigger keyword screen against `config/sensitivity_keywords.yaml` runs **before**
   any LLM call. A match short-circuits to a deterministic `block_with_redirect` result.
2. Otherwise, a single `LLMProvider.generate_structured` call produces a
   `ClassifiedQuery` + `RetrievalPlan` pair.
3. ADR-0007 invariant is re-asserted: `RetrievalPlan.semanticQuery` MUST equal
   `ClassifiedQuery.reframedQuery ?? ClassifiedQuery.rawQuery`.
4. `tenantId` placeholders in the plan are overwritten from the caller's `Principal` —
   any LLM-emitted value is dropped before retrieval.
5. Refusals (or invalid JSON that survived adapter validation) fall back to a
   deterministic conservative result.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from pydantic import ValidationError

from app.adapters.providers.base import LLMProvider, StructuredResult
from app.core.errors import (
    ProviderInvalidResponseError,
    ProviderRefusedError,
    ProviderUnavailableError,
)
from app.core.logging import get_logger
from app.domain.models.classified_query import ClassifiedQuery
from app.domain.models.principal import Principal
from app.domain.models.retrieval_plan import RetrievalFilters, RetrievalPlan
from app.domain.prompts.query_analyzer_a1_a2 import build_messages
from app.domain.services.safety_config import (
    SafetyConfig,
    SafetyMatch,
    match_sensitivity,
)

logger = get_logger(__name__)


_DETERMINISTIC_CLASSIFIER_VERSION = "deterministic_a1@hard_trigger"
_FALLBACK_CLASSIFIER_VERSION = "deterministic_a1@refusal_fallback"


@dataclass(frozen=True)
class QueryAnalysis:
    """Bundle of A1 + A2 outputs plus the upstream safety match (if any)."""

    classified_query: ClassifiedQuery
    retrieval_plan: RetrievalPlan
    safety_match: SafetyMatch | None
    used_llm: bool


class QueryAnalyzer:
    def __init__(
        self,
        *,
        provider: LLMProvider,
        safety_config: SafetyConfig,
        prompt_version: str,
        model_route_id: str,
    ) -> None:
        self._provider = provider
        self._safety_config = safety_config
        self._prompt_version = prompt_version
        self._model_route_id = model_route_id

    async def analyze(
        self,
        *,
        query_text: str,
        principal: Principal,
        run_id: str,
    ) -> QueryAnalysis:
        start = time.perf_counter()
        safety_match = match_sensitivity(query_text, self._safety_config)

        if safety_match is not None and safety_match.hard_trigger:
            classified = self._build_hard_trigger_classified_query(
                query_text=query_text, safety_match=safety_match
            )
            plan = self._build_degenerate_plan(
                query_text=query_text, principal=principal, classified=classified
            )
            self._log_classified(
                classified=classified,
                principal=principal,
                run_id=run_id,
                duration_ms=_ms_since(start),
                source="hard_trigger",
                model_route_id=None,
                safety_rule_id=safety_match.rule_id,
            )
            return QueryAnalysis(
                classified_query=classified,
                retrieval_plan=plan,
                safety_match=safety_match,
                used_llm=False,
            )

        try:
            result = await self._call_provider(
                query_text=query_text,
                soft_trigger=safety_match,
                principal=principal,
                run_id=run_id,
            )
        except (ProviderRefusedError, ProviderInvalidResponseError) as exc:
            logger.warning(
                "query_analyzer.provider_fallback",
                run_id=run_id,
                tenant_id=principal.tenant_id,
                reason=type(exc).__name__,
            )
            classified, plan = self._build_refusal_fallback(
                query_text=query_text, principal=principal
            )
            self._log_classified(
                classified=classified,
                principal=principal,
                run_id=run_id,
                duration_ms=_ms_since(start),
                source="refusal_fallback",
                model_route_id=self._model_route_id,
                safety_rule_id=safety_match.rule_id if safety_match else None,
            )
            return QueryAnalysis(
                classified_query=classified,
                retrieval_plan=plan,
                safety_match=safety_match,
                used_llm=True,
            )

        try:
            classified, plan = self._parse_result(
                result=result, query_text=query_text
            )
        except (ValidationError, ProviderInvalidResponseError) as exc:
            logger.warning(
                "query_analyzer.invalid_payload",
                run_id=run_id,
                tenant_id=principal.tenant_id,
                errors=str(exc),
            )
            classified, plan = self._build_refusal_fallback(
                query_text=query_text, principal=principal
            )
            self._log_classified(
                classified=classified,
                principal=principal,
                run_id=run_id,
                duration_ms=_ms_since(start),
                source="invalid_payload_fallback",
                model_route_id=self._model_route_id,
                safety_rule_id=safety_match.rule_id if safety_match else None,
            )
            return QueryAnalysis(
                classified_query=classified,
                retrieval_plan=plan,
                safety_match=safety_match,
                used_llm=True,
            )

        classified, plan = self._enforce_invariants(
            classified=classified, plan=plan, principal=principal, query_text=query_text
        )
        self._log_classified(
            classified=classified,
            principal=principal,
            run_id=run_id,
            duration_ms=_ms_since(start),
            source="llm",
            model_route_id=self._model_route_id,
            safety_rule_id=safety_match.rule_id if safety_match else None,
        )
        return QueryAnalysis(
            classified_query=classified,
            retrieval_plan=plan,
            safety_match=safety_match,
            used_llm=True,
        )

    async def _call_provider(
        self,
        *,
        query_text: str,
        soft_trigger: SafetyMatch | None,
        principal: Principal,
        run_id: str,
    ) -> StructuredResult:
        messages = build_messages(query_text=query_text, soft_trigger=soft_trigger)
        try:
            result = await self._provider.generate_structured(
                messages=messages,
                schema=_combined_schema(),
                route_id=self._model_route_id,
                tenant_id=principal.tenant_id,
                run_id=run_id,
            )
        except ProviderUnavailableError:
            # Re-raise; the API layer maps to `provider_unavailable` (503).
            raise

        if result.finish_reason == "refusal":
            raise ProviderRefusedError("A1/A2 classifier refused")
        return result

    def _parse_result(
        self, *, result: StructuredResult, query_text: str
    ) -> tuple[ClassifiedQuery, RetrievalPlan]:
        data = result.data
        classified_raw = data.get("classifiedQuery") or data.get("classified_query")
        plan_raw = data.get("retrievalPlan") or data.get("retrieval_plan")
        if not isinstance(classified_raw, dict) or not isinstance(plan_raw, dict):
            raise ProviderInvalidResponseError(
                "A1/A2 payload missing classifiedQuery / retrievalPlan keys"
            )
        # Make sure the LLM didn't drop the verbatim raw query — re-stamp it.
        classified_raw = {**classified_raw, "rawQuery": query_text}
        classified = ClassifiedQuery.model_validate(classified_raw)
        plan = RetrievalPlan.model_validate(plan_raw)
        return classified, plan

    def _enforce_invariants(
        self,
        *,
        classified: ClassifiedQuery,
        plan: RetrievalPlan,
        principal: Principal,
        query_text: str,
    ) -> tuple[ClassifiedQuery, RetrievalPlan]:
        # ADR-0007: semanticQuery MUST equal reframedQuery ?? rawQuery.
        expected_semantic = classified.reframed_query or classified.raw_query or query_text
        plan_updates: dict[str, object] = {}
        if plan.semantic_query != expected_semantic:
            logger.warning(
                "query_analyzer.semantic_query_override",
                emitted=plan.semantic_query,
                expected=expected_semantic,
            )
            plan_updates["semantic_query"] = expected_semantic

        # Tenant injection — any LLM-emitted value is dropped.
        if plan.tenant_id != principal.tenant_id:
            plan_updates["tenant_id"] = principal.tenant_id
        if plan.filters.tenant_id != principal.tenant_id:
            plan_updates["filters"] = plan.filters.model_copy(
                update={"tenant_id": principal.tenant_id}
            )
        # Force approved=True regardless of what the LLM emitted (the model is already typed to
        # `Literal[True]` so this is defense-in-depth).
        if "filters" not in plan_updates and plan.filters.approved is not True:
            plan_updates["filters"] = plan.filters.model_copy(update={"approved": True})

        if plan_updates:
            plan = plan.model_copy(update=plan_updates)
        return classified, plan

    def _build_hard_trigger_classified_query(
        self, *, query_text: str, safety_match: SafetyMatch
    ) -> ClassifiedQuery:
        return ClassifiedQuery(
            raw_query=query_text,
            answer_mode="insufficient",
            sensitivity_primary=safety_match.sensitivity,
            risk_flags=list(safety_match.risk_flags),
            handling="block_with_redirect",
            preliminary_confidence_tier="RED",
            reframed_query=None,
            reframing_disclosure_required=False,
            classifier_version=_DETERMINISTIC_CLASSIFIER_VERSION,
        )

    def _build_degenerate_plan(
        self,
        *,
        query_text: str,
        principal: Principal,
        classified: ClassifiedQuery,
    ) -> RetrievalPlan:
        """Placeholder plan emitted alongside a hard-trigger ClassifiedQuery. The API layer
        does not call A3 when `handling == block_with_redirect`; this plan exists only so
        downstream consumers always see both objects."""
        del classified
        return RetrievalPlan(
            semantic_query=query_text,
            answer_mode="insufficient",
            tenant_id=principal.tenant_id,
            filters=RetrievalFilters(tenant_id=principal.tenant_id, approved=True),
            k=1,
            boosts=[],
        )

    def _build_refusal_fallback(
        self, *, query_text: str, principal: Principal
    ) -> tuple[ClassifiedQuery, RetrievalPlan]:
        classified = ClassifiedQuery(
            raw_query=query_text,
            answer_mode="insufficient",
            sensitivity_primary="normal",
            risk_flags=[],
            handling="insufficient_evidence",
            preliminary_confidence_tier="YELLOW",
            reframed_query=None,
            reframing_disclosure_required=False,
            classifier_version=_FALLBACK_CLASSIFIER_VERSION,
        )
        plan = RetrievalPlan(
            semantic_query=query_text,
            answer_mode="insufficient",
            tenant_id=principal.tenant_id,
            filters=RetrievalFilters(tenant_id=principal.tenant_id, approved=True),
            k=1,
            boosts=[],
        )
        return classified, plan

    def _log_classified(
        self,
        *,
        classified: ClassifiedQuery,
        principal: Principal,
        run_id: str,
        duration_ms: int,
        source: str,
        model_route_id: str | None,
        safety_rule_id: str | None,
    ) -> None:
        logger.info(
            "query.classified",
            run_id=run_id,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            stage="a1_a2_query_analyzer",
            sensitivity_primary=classified.sensitivity_primary,
            handling=classified.handling,
            preliminary_confidence_tier=classified.preliminary_confidence_tier,
            risk_flags=list(classified.risk_flags),
            answer_mode=classified.answer_mode,
            duration_ms=duration_ms,
            classifier_source=source,
            model_route_id=model_route_id,
            safety_rule_id=safety_rule_id,
            prompt_version=self._prompt_version,
        )


def _ms_since(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _combined_schema() -> dict[str, object]:
    """The JSON schema sent to the provider. Derived from the Pydantic models so it cannot
    drift from what we'll deserialize."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["classifiedQuery", "retrievalPlan"],
        "properties": {
            "classifiedQuery": ClassifiedQuery.model_json_schema(by_alias=True),
            "retrievalPlan": RetrievalPlan.model_json_schema(by_alias=True),
        },
    }


__all__ = ["QueryAnalysis", "QueryAnalyzer"]
