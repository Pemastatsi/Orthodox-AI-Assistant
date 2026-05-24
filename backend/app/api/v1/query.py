"""POST /api/v1/query — A1 + A2 + A3 only (Phase 1 / T-003 surface).

The response shape returned here is a T-003-shaped envelope that exposes the intermediate
`classifiedQuery`, `retrievalPlan`, and `scoredChunks`. T-004 will replace this endpoint
with the canonical `VerifiedResponse` once A4/A5/A6 land; until then the envelope lets
front-end code wire against a stable contract.
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
    build_query_analyzer,
    build_retriever,
    get_embedding_provider,
    get_query_analyzer_provider,
    get_safety_config,
    get_settings_dep,
    get_sparse_embedder,
    get_vector_store,
    require_scope,
)
from app.core.config import Settings
from app.core.errors import (
    ApiErrorCode,
    ProviderUnavailableError,
    VectorStoreTimeoutError,
    VectorStoreUnavailableError,
)
from app.core.logging import get_logger
from app.domain.models._base import WireModel
from app.domain.models.classified_query import ClassifiedQuery
from app.domain.models.principal import Principal
from app.domain.models.retrieval_plan import RetrievalPlan
from app.domain.models.scored_chunk import ScoredChunk
from app.domain.services.retriever import RetrievalOutcome
from app.domain.services.safety_config import SafetyConfig

router = APIRouter(prefix="/query", tags=["query"])
logger = get_logger(__name__)


class QueryRequest(WireModel):
    query_text: str = Field(min_length=1, max_length=4096)


class QueryResponse(WireModel):
    run_id: str
    classified_query: ClassifiedQuery
    retrieval_plan: RetrievalPlan
    scored_chunks: list[ScoredChunk]


@router.post(
    "",
    response_model=QueryResponse,
    response_model_by_alias=True,
)
async def post_query(
    body: QueryRequest,
    principal: Principal = Depends(require_scope("query:read")),
    safety_config: SafetyConfig = Depends(get_safety_config),
    provider: LLMProvider = Depends(get_query_analyzer_provider),
    embedding_provider: LLMProvider = Depends(get_embedding_provider),
    vector_store: VectorStore = Depends(get_vector_store),
    sparse_embedder: Bm25SparseEmbedder = Depends(get_sparse_embedder),
    settings: Settings = Depends(get_settings_dep),
) -> QueryResponse:
    run_id = f"run_{ulid.new()!s}"
    start = time.perf_counter()

    analyzer = build_query_analyzer(
        provider=provider, safety_config=safety_config, settings=settings
    )
    retriever = build_retriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        sparse_embedder=sparse_embedder,
        settings=settings,
    )

    try:
        analysis = await analyzer.analyze(
            query_text=body.query_text, principal=principal, run_id=run_id
        )
    except HTTPException:
        # Re-raise HTTPExceptions raised by the deferred provider, etc.
        raise
    except ProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": ApiErrorCode.PROVIDER_UNAVAILABLE.value,
                "message": str(exc),
            },
        ) from exc

    outcome: RetrievalOutcome | None = None
    if analysis.classified_query.handling == "block_with_redirect":
        # Safety short-circuit: no retrieval performed.
        scored_chunks: list[ScoredChunk] = []
    else:
        try:
            outcome = await retriever.retrieve(
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
        scored_chunks = outcome.candidates

    logger.info(
        "query.completed",
        run_id=run_id,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        handling=analysis.classified_query.handling,
        candidate_count=len(scored_chunks),
        duration_ms=int((time.perf_counter() - start) * 1000),
    )

    return QueryResponse(
        run_id=run_id,
        classified_query=analysis.classified_query,
        retrieval_plan=analysis.retrieval_plan,
        scored_chunks=scored_chunks,
    )


__all__ = ["router"]
