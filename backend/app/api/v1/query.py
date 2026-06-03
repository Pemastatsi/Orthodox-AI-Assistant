"""POST /api/v1/query — A1+A2+A3+A4+A5+A6 pipeline with caching and persistence.

T-004 wired the pipeline and the bounded-fallback fall-through paths.
T-005 adds the surrounding plumbing:

- Cache lookup AFTER A1+A2 (we need `answerMode` from the RetrievalPlan) and BEFORE A3.
  Hits return the cached `VerifiedResponse` with a freshly-minted `runId` and increment
  `served_answer_count` only.
- Cache write AFTER A6 success (fire-and-forget after DB commit) — a Redis failure logs
  `cache.store(outcome=error)` but never breaks the request.
- Every served request — hard-safety, RED, composer refusal, or normal — writes exactly
  one `run_traces` row, increments `billing_usage` (served, plus `fresh` when A5 ran), and
  may add a `flagged_queries` row (+ optional encrypted `raw_sensitive_logs` row).

The hard-safety bypass still short-circuits before A3, but now persists a minimal
`run_traces` row so F-18 ("every served request inspectable in /admin/queries") holds.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import ulid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import Field

from app.adapters.providers.base import LLMProvider
from app.adapters.sparse.bm25_embedder import Bm25SparseEmbedder
from app.adapters.vector_store.base import VectorStore
from app.api.v1._deps import (
    build_composer,
    build_evidence_packager,
    build_query_analyzer,
    build_retriever,
    build_verifier,
    get_composer_provider,
    get_embedding_provider,
    get_pastoral_config,
    get_query_analyzer_provider,
    get_response_cache,
    get_safety_config,
    get_sensitive_log_cipher,
    get_settings_dep,
    get_sparse_embedder,
    get_vector_store,
    get_verifier_provider,
    require_scope,
)
from app.core.config import Settings
from app.core.errors import (
    ApiErrorCode,
    ProviderInvalidResponseError,
    ProviderRateLimitedError,
    ProviderRefusedError,
    ProviderUnavailableError,
    VectorStoreTimeoutError,
    VectorStoreUnavailableError,
)
from app.core.logging import get_logger
from app.core.tenant_context import set_tenant_guc
from app.domain.agents.query_analyzer import QueryAnalysis
from app.domain.models._base import WireModel
from app.domain.models.classified_query import ClassifiedQuery
from app.domain.models.principal import Principal
from app.domain.models.run_trace import RunTrace, RunTraceUsage, Stage
from app.domain.models.verified_response import VerifiedResponse
from app.domain.repositories._base import session_scope
from app.domain.repositories.billing_usage_repository import BillingUsageRepository
from app.domain.repositories.flagged_query_repository import FlaggedQueryRepository
from app.domain.repositories.raw_sensitive_log_repository import (
    RawSensitiveLogRepository,
)
from app.domain.repositories.run_trace_repository import RunTraceRepository
from app.domain.services.bounded_fallback import CaseClass, build_bounded_fallback
from app.domain.services.cache_service import (
    ResponseCache,
    build_cache_fields,
    cache_key,
)
from app.domain.services.encryption_service import SensitiveLogCipher
from app.domain.services.prompt_loader import registry_version
from app.domain.services.redaction_service import (
    redact_query_text,
    should_capture_raw_sensitive,
)
from app.domain.services.safety_config import PastoralConfig, SafetyConfig

router = APIRouter(prefix="/query", tags=["query"])
logger = get_logger(__name__)

_HARD_TRIGGER_CASE_CLASS: dict[str, CaseClass] = {
    "self_harm": "self_harm",
    "medical_emergency": "medical_emergency",
}


class QueryRequest(WireModel):
    query_text: str = Field(min_length=1, max_length=4096)


@router.post(
    "",
    response_model=VerifiedResponse,
    response_model_by_alias=True,
)
async def post_query(
    body: QueryRequest,
    request: Request,
    principal: Principal = Depends(require_scope("query:read")),
    safety_config: SafetyConfig = Depends(get_safety_config),
    pastoral_config: PastoralConfig = Depends(get_pastoral_config),
    analyzer_provider: LLMProvider = Depends(get_query_analyzer_provider),
    composer_provider: LLMProvider = Depends(get_composer_provider),
    verifier_provider: LLMProvider | None = Depends(get_verifier_provider),
    embedding_provider: LLMProvider = Depends(get_embedding_provider),
    vector_store: VectorStore = Depends(get_vector_store),
    sparse_embedder: Bm25SparseEmbedder = Depends(get_sparse_embedder),
    cache: ResponseCache = Depends(get_response_cache),
    cipher: SensitiveLogCipher | None = Depends(get_sensitive_log_cipher),
    settings: Settings = Depends(get_settings_dep),
) -> VerifiedResponse:
    run_id = f"run_{getattr(request.state, 'run_id', None) or ulid.new()!s}"
    started_at = datetime.now(UTC)
    start = time.perf_counter()

    analyzer = build_query_analyzer(
        provider=analyzer_provider, safety_config=safety_config, settings=settings
    )
    retriever = build_retriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        sparse_embedder=sparse_embedder,
        settings=settings,
    )
    packager = build_evidence_packager(settings=settings)
    composer = build_composer(provider=composer_provider, settings=settings)
    verifier = build_verifier(
        pastoral_config=pastoral_config,
        settings=settings,
        judge_provider=verifier_provider,
    )

    # ---- A1 + A2 ---------------------------------------------------------------------
    try:
        analysis = await analyzer.analyze(
            query_text=body.query_text, principal=principal, run_id=run_id
        )
    except HTTPException:
        raise
    except ProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": ApiErrorCode.PROVIDER_UNAVAILABLE.value,
                "message": str(exc),
            },
        ) from exc
    except ProviderRateLimitedError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": ApiErrorCode.RATE_LIMITED.value,
                "message": str(exc),
            },
        ) from exc

    original_query = analysis.classified_query.raw_query
    reframed_query = analysis.classified_query.reframed_query

    # Hard-safety bypass: never touches cache; persists a minimal run trace per F-18.
    if analysis.classified_query.handling == "block_with_redirect":
        case_class = _resolve_hard_trigger_case_class(analysis)
        response = build_bounded_fallback(
            case_class=case_class,
            handling="block_with_redirect",
            run_id=run_id,
            model_route_id=settings.active_model_route_a1a2,
            confidence_tier=analysis.classified_query.preliminary_confidence_tier,
            verifier_version=settings.active_verifier_version,
            verifier_passed=True,
            schema_version=settings.active_schema_version,
            original_query=original_query,
            reframed_query=reframed_query,
        )
        await _persist_run_outcome(
            run_id=run_id,
            started_at=started_at,
            principal=principal,
            classified=analysis.classified_query,
            raw_query=body.query_text,
            response=response,
            cache_hit=False,
            fresh_model_run=False,
            stages=[_stage_a1a2(started_at, settings, outcome="fallback")],
            flag_reason="hard_safety_trigger",
            cipher=cipher,
            sensitive_log_retention_days=settings.sensitive_log_retention_days,
        )
        _log_completed(run_id, principal, response, start, case="hard_safety", cache_hit=False)
        return response

    # ---- Cache lookup (after A1+A2, before A3) ---------------------------------------
    cache_fields = build_cache_fields(
        principal=principal,
        raw_query=body.query_text,
        answer_mode=analysis.retrieval_plan.answer_mode,
        session_hash=None,
        corpus_version=settings.active_schema_version,
        config_version=settings.active_schema_version,
        calendar_version=settings.active_schema_version,
        prompt_version=settings.active_prompt_version_a5,
        model_route_id=settings.active_model_route_a5,
        schema_version=settings.active_schema_version,
    )
    key = cache_key(cache_fields)
    try:
        cached = await cache.get(key)
    except Exception as exc:  # noqa: BLE001 — cache errors must not fail the request
        logger.warning(
            "cache.lookup_error", run_id=run_id, error_type=type(exc).__name__
        )
        cached = None

    if cached is not None:
        logger.info("cache.hit", run_id=run_id, tenant_id=principal.tenant_id)
        response = cached.model_copy(update={"run_id": run_id, "served_from_cache": True})
        await _persist_run_outcome(
            run_id=run_id,
            started_at=started_at,
            principal=principal,
            classified=analysis.classified_query,
            raw_query=body.query_text,
            response=response,
            cache_hit=True,
            fresh_model_run=False,
            stages=[
                _stage_a1a2(started_at, settings, outcome="ok"),
                _stage("cache_lookup", started_at, outcome="ok", notes="cache_hit"),
            ],
            flag_reason=None,
            cipher=cipher,
            sensitive_log_retention_days=settings.sensitive_log_retention_days,
        )
        _log_completed(run_id, principal, response, start, case="cache_hit", cache_hit=True)
        return response

    logger.info("cache.miss", run_id=run_id, tenant_id=principal.tenant_id)

    # ---- A3 retrieval -----------------------------------------------------------------
    try:
        retrieval = await retriever.retrieve(
            plan=analysis.retrieval_plan,
            principal=principal,
            run_id=run_id,
        )
    except (VectorStoreUnavailableError, VectorStoreTimeoutError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": ApiErrorCode.QDRANT_UNAVAILABLE.value,
                "message": str(exc),
            },
        ) from exc

    # ---- A4 evidence packaging --------------------------------------------------------
    packaging = packager.package(
        candidates=retrieval.candidates,
        classified=analysis.classified_query,
        principal=principal,
        run_id=run_id,
    )
    packet = packaging.packet

    if packet.confidence_tier == "RED" or not packet.admitted_chunks:
        response = build_bounded_fallback(
            case_class="out_of_corpus",
            handling="insufficient_evidence",
            run_id=run_id,
            model_route_id=settings.active_model_route_a5,
            verifier_version=settings.active_verifier_version,
            verifier_passed=True,
            schema_version=settings.active_schema_version,
            original_query=original_query,
            reframed_query=reframed_query,
        )
        await _persist_run_outcome(
            run_id=run_id,
            started_at=started_at,
            principal=principal,
            classified=analysis.classified_query,
            raw_query=body.query_text,
            response=response,
            cache_hit=False,
            fresh_model_run=False,
            stages=[
                _stage_a1a2(started_at, settings, outcome="ok"),
                _stage("a4_evidence_packager", started_at, outcome="fallback"),
            ],
            flag_reason="insufficient_evidence",
            cipher=cipher,
            sensitive_log_retention_days=settings.sensitive_log_retention_days,
        )
        _log_completed(run_id, principal, response, start, case="red_evidence", cache_hit=False)
        return response

    # ---- A5 composition + A6 verification --------------------------------------------
    try:
        composer_output = await composer.compose(
            packet=packet,
            classified=analysis.classified_query,
            run_id=run_id,
        )
    except (ProviderRefusedError, ProviderInvalidResponseError) as exc:
        logger.warning(
            "query.composer_fallback",
            run_id=run_id,
            tenant_id=principal.tenant_id,
            reason=type(exc).__name__,
        )
        response = build_bounded_fallback(
            case_class="out_of_corpus",
            handling="insufficient_evidence",
            run_id=run_id,
            model_route_id=settings.active_model_route_a5,
            verifier_version=settings.active_verifier_version,
            verifier_passed=False,
            schema_version=settings.active_schema_version,
            failure_reason=f"composer_{type(exc).__name__}",
            original_query=original_query,
            reframed_query=reframed_query,
        )
        await _persist_run_outcome(
            run_id=run_id,
            started_at=started_at,
            principal=principal,
            classified=analysis.classified_query,
            raw_query=body.query_text,
            response=response,
            cache_hit=False,
            fresh_model_run=False,
            stages=[
                _stage_a1a2(started_at, settings, outcome="ok"),
                _stage_a5(started_at, settings, outcome="error", notes=type(exc).__name__),
            ],
            flag_reason="verifier_failed",
            cipher=cipher,
            sensitive_log_retention_days=settings.sensitive_log_retention_days,
        )
        _log_completed(
            run_id, principal, response, start, case="composer_refusal", cache_hit=False
        )
        return response
    except ProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": ApiErrorCode.PROVIDER_UNAVAILABLE.value,
                "message": str(exc),
            },
        ) from exc

    response = await verifier.verify(
        composer_output=composer_output,
        packet=packet,
        classified=analysis.classified_query,
        run_id=run_id,
        original_query=original_query,
        reframed_query=reframed_query,
    )

    # Successful round-trip: persist + cache + log.
    a6_passed = response.verification.passed
    await _persist_run_outcome(
        run_id=run_id,
        started_at=started_at,
        principal=principal,
        classified=analysis.classified_query,
        raw_query=body.query_text,
        response=response,
        cache_hit=False,
        fresh_model_run=True,
        stages=[
            _stage_a1a2(started_at, settings, outcome="ok"),
            _stage_a5(started_at, settings, outcome="ok"),
            _stage("a6_verifier", started_at, outcome="ok" if a6_passed else "fallback"),
        ],
        flag_reason=None if a6_passed else "verifier_failed",
        cipher=cipher,
        sensitive_log_retention_days=settings.sensitive_log_retention_days,
    )

    if a6_passed and response.handling in ("answer", "answer_with_disclaimer"):
        try:
            await cache.set(key, response, ttl_seconds=settings.response_cache_ttl_seconds)
            logger.info("cache.store", run_id=run_id, outcome="ok")
        except Exception as exc:  # noqa: BLE001 — never break the request on cache failure
            logger.warning(
                "cache.store",
                run_id=run_id,
                outcome="error",
                error_type=type(exc).__name__,
            )

    _log_completed(run_id, principal, response, start, case="normal", cache_hit=False)
    return response


# ---- Helpers ----------------------------------------------------------------------


def _resolve_hard_trigger_case_class(analysis: QueryAnalysis) -> CaseClass:
    risk_flags = set(analysis.classified_query.risk_flags)
    for flag, case_class in _HARD_TRIGGER_CASE_CLASS.items():
        if flag in risk_flags:
            return case_class
    sensitivity = analysis.classified_query.sensitivity_primary
    if sensitivity == "political":
        return "political_voting"
    return "fabrication_attempt"


def _stage(
    name: str,
    started_at: datetime,
    *,
    outcome: str,
    notes: str | None = None,
    model_route_id: str | None = None,
    details: dict[str, str] | None = None,
) -> Stage:
    now = datetime.now(UTC)
    return Stage(
        stage=name,
        started_at=started_at,
        finished_at=now,
        outcome=outcome,
        model_route_id=model_route_id,
        notes=notes,
        details=details or {},
    )


# Registry path identifiers for the model-backed stages (GS-3). The RunTrace promptVersion is
# the full registry path — {promptId}/{version-stem} — so an operator can reconstruct the exact
# template via `git show prompts/<promptVersion>.j2` (docs/contracts/prompt-management.md).
_A1A2_PROMPT_ID = "a1_classifier/en"
_A5_PROMPT_ID = "a5_composer/en"


def _stage_a1a2(started_at: datetime, settings: Settings, *, outcome: str) -> Stage:
    version = registry_version(settings.active_prompt_version_a1a2)
    return _stage(
        "a1_a2_query_analyzer",
        started_at,
        outcome=outcome,
        model_route_id=settings.active_model_route_a1a2,
        details={
            "promptId": _A1A2_PROMPT_ID,
            "promptVersion": f"{_A1A2_PROMPT_ID}/{version}",
        },
    )


def _stage_a5(
    started_at: datetime, settings: Settings, *, outcome: str, notes: str | None = None
) -> Stage:
    version = registry_version(settings.active_prompt_version_a5)
    return _stage(
        "a5_composer",
        started_at,
        outcome=outcome,
        notes=notes,
        model_route_id=settings.active_model_route_a5,
        details={
            "promptId": _A5_PROMPT_ID,
            "promptVersion": f"{_A5_PROMPT_ID}/{version}",
        },
    )


async def _persist_run_outcome(
    *,
    run_id: str,
    started_at: datetime,
    principal: Principal,
    classified: ClassifiedQuery,
    raw_query: str,
    response: VerifiedResponse,
    cache_hit: bool,
    fresh_model_run: bool,
    stages: list[Stage],
    flag_reason: str | None,
    cipher: SensitiveLogCipher | None,
    sensitive_log_retention_days: int,
) -> None:
    """Single durable write-down for every request outcome.

    Writes: run_traces (always), billing_usage (always), flagged_queries + optionally
    raw_sensitive_logs (when `flag_reason` is set OR `should_capture_raw_sensitive`).
    All in one transaction so partial state is impossible.
    """
    finished_at = datetime.now(UTC)
    trace = RunTrace(
        run_id=run_id,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        started_at=started_at,
        finished_at=finished_at,
        cache_hit=cache_hit,
        stages=stages,
        usage=RunTraceUsage(
            served_answer_count=1,
            fresh_model_run_count=1 if fresh_model_run else 0,
        ),
        final_handling=response.handling,
        final_confidence_tier=response.confidence_tier,
        verifier_passed=response.verification.passed,
    )

    capture_raw = cipher is not None and should_capture_raw_sensitive(classified)
    needs_flagged = flag_reason is not None or capture_raw
    effective_flag = flag_reason or ("hard_safety_trigger" if capture_raw else None)

    try:
        async with session_scope() as session:
            await set_tenant_guc(session, principal.tenant_id)

            await RunTraceRepository(session).insert(trace)
            await BillingUsageRepository(session).increment(
                tenant_id=principal.tenant_id,
                served_answer_count=1,
                fresh_model_run_count=1 if fresh_model_run else 0,
                prompt_tokens=response.usage.prompt_tokens or 0,
                completion_tokens=response.usage.completion_tokens or 0,
            )

            if needs_flagged and effective_flag is not None:
                raw_log_id: str | None = None
                if capture_raw and cipher is not None:
                    blob = cipher.encrypt(raw_query)
                    raw_log_id = await RawSensitiveLogRepository(session).insert(
                        tenant_id=principal.tenant_id,
                        user_id=principal.user_id,
                        run_id=run_id,
                        blob=blob,
                        retention_days=sensitive_log_retention_days,
                    )
                await FlaggedQueryRepository(session).insert(
                    tenant_id=principal.tenant_id,
                    user_id=principal.user_id,
                    run_id=run_id,
                    query_text_redacted=redact_query_text(raw_query),
                    flag_reason=effective_flag,
                    raw_sensitive_log_id=raw_log_id,
                    sensitivity_primary=classified.sensitivity_primary,
                    risk_flags=list(classified.risk_flags),
                )
    except Exception as exc:  # noqa: BLE001 — log + swallow so the user still gets the answer
        logger.error(
            "query.persist_failed",
            run_id=run_id,
            code="PERSIST_FAILED",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )


def _log_completed(
    run_id: str,
    principal: Principal,
    response: VerifiedResponse,
    start: float,
    *,
    case: str,
    cache_hit: bool,
) -> None:
    logger.info(
        "query.completed",
        run_id=run_id,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        handling=response.handling,
        confidence_tier=response.confidence_tier,
        verifier_passed=response.verification.passed,
        citation_count=len(response.citations),
        case=case,
        cache_hit=cache_hit,
        duration_ms=int((time.perf_counter() - start) * 1000),
    )


__all__ = ["router"]


# Used by tests to suppress the unused-import lint when query.py is imported standalone.
_ = Any
