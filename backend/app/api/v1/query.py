"""POST /api/v1/query — full A1+A2+A3+A4+A5+A6 pipeline (Phase 1).

Returns a canonical `VerifiedResponse` for every code path:
- Hard-safety triggers and political/fabrication blocks → bounded fallback with the
  case-specific canonical text (see `bounded_fallback.CANONICAL_TEXTS`).
- A4 admits no chunks (corpus_empty by tenant) → `corpus_empty` 409 if the tenant has zero
  approved chunks at all; otherwise `insufficient_evidence` bounded fallback with HTTP 200.
- A5 refusal or A6 reject → `insufficient_evidence` bounded fallback.

Per `phase1-implementation-contract.md` §Run-trace persistence is unconditional, every
served request must be inspectable in `/admin/queries`. The run trace itself is persisted
in T-005; T-004 just emits structured logs and the canonical response shape.
"""

from __future__ import annotations

import time

import ulid
from fastapi import APIRouter, Depends, HTTPException, status
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
    get_safety_config,
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
from app.domain.agents.query_analyzer import QueryAnalysis
from app.domain.models._base import WireModel
from app.domain.models.principal import Principal
from app.domain.models.verified_response import VerifiedResponse
from app.domain.services.bounded_fallback import CaseClass, build_bounded_fallback
from app.domain.services.safety_config import PastoralConfig, SafetyConfig

router = APIRouter(prefix="/query", tags=["query"])
logger = get_logger(__name__)

# Map hard-trigger risk flags to the canonical bounded-fallback case_class.
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
    principal: Principal = Depends(require_scope("query:read")),
    safety_config: SafetyConfig = Depends(get_safety_config),
    pastoral_config: PastoralConfig = Depends(get_pastoral_config),
    analyzer_provider: LLMProvider = Depends(get_query_analyzer_provider),
    composer_provider: LLMProvider = Depends(get_composer_provider),
    verifier_provider: LLMProvider | None = Depends(get_verifier_provider),
    embedding_provider: LLMProvider = Depends(get_embedding_provider),
    vector_store: VectorStore = Depends(get_vector_store),
    sparse_embedder: Bm25SparseEmbedder = Depends(get_sparse_embedder),
    settings: Settings = Depends(get_settings_dep),
) -> VerifiedResponse:
    run_id = f"run_{ulid.new()!s}"
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

    # Hard-safety bypass: short-circuit before retrieval, A4, A5, A6.
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
        _log_completed(run_id, principal, response, start, case="hard_safety")
        return response

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

    # RED tier (or no admitted chunks) → bounded `insufficient_evidence`.
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
        _log_completed(run_id, principal, response, start, case="red_evidence")
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
        _log_completed(run_id, principal, response, start, case="composer_refusal")
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
    _log_completed(run_id, principal, response, start, case="normal")
    return response


def _resolve_hard_trigger_case_class(analysis: QueryAnalysis) -> CaseClass:
    """Map an analysis with `handling=block_with_redirect` to the canonical case_class.

    Order of precedence:
    1. Hard-trigger risk flag (`self_harm`, `medical_emergency`) — those map directly.
    2. Soft-handled blocks (e.g. political voting, fabrication) — match by safety_match
       rule_id or sensitivityPrimary.
    """
    risk_flags = set(analysis.classified_query.risk_flags)
    for flag, case_class in _HARD_TRIGGER_CASE_CLASS.items():
        if flag in risk_flags:
            return case_class
    sensitivity = analysis.classified_query.sensitivity_primary
    if sensitivity == "political":
        return "political_voting"
    return "fabrication_attempt"


def _log_completed(
    run_id: str,
    principal: Principal,
    response: VerifiedResponse,
    start: float,
    *,
    case: str,
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
        duration_ms=int((time.perf_counter() - start) * 1000),
    )


__all__ = ["router"]
