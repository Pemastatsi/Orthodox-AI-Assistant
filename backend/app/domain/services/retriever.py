"""A3 retrieval service.

Embeds the `RetrievalPlan.semantic_query`, builds a tenant-filtered `VectorFilter`, and calls
`VectorStore.search`. Role-based visibility is enforced **post-retrieval** in Python — the
adapter's `VectorFilter` only carries a single optional visibility value, while a user's
allow-list usually has multiple tiers (e.g. a scholar sees both `member` and `scholar`
chunks). Tenant isolation and approval filtering happen at the adapter boundary per
ADR-0010 / ADR-0013.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.adapters.providers.base import LLMProvider
from app.adapters.sparse.bm25_embedder import Bm25SparseEmbedder
from app.adapters.vector_store.base import (
    ScoredChunk as AdapterScoredChunk,
)
from app.adapters.vector_store.base import (
    SparseVector,
    VectorFilter,
    VectorStore,
)
from app.core.logging import get_logger
from app.domain.models.principal import Principal
from app.domain.models.retrieval_plan import RetrievalPlan
from app.domain.models.scored_chunk import ScoredChunk

logger = get_logger(__name__)

# Role → visibility allow-list. Members see only `member` chunks; scholars also see
# `scholar`-tier; content_manager / admin / owner additionally see `admin_only`. `suppressed`
# is never returned to anyone.
_VISIBILITY_BY_ROLE: dict[str, frozenset[str]] = {
    "member": frozenset({"member"}),
    "scholar": frozenset({"member", "scholar"}),
    "content_manager": frozenset({"member", "scholar", "admin_only"}),
    "admin": frozenset({"member", "scholar", "admin_only"}),
    "owner": frozenset({"member", "scholar", "admin_only"}),
}


@dataclass(frozen=True)
class RetrievalOutcome:
    candidates: list[ScoredChunk]
    raw_count: int
    visibility_filtered_count: int


class Retriever:
    def __init__(
        self,
        *,
        embedding_provider: LLMProvider,
        vector_store: VectorStore,
        sparse_embedder: Bm25SparseEmbedder | None = None,
        embedding_route_id: str,
    ) -> None:
        self._embedder = embedding_provider
        self._store = vector_store
        self._sparse = sparse_embedder
        self._embedding_route_id = embedding_route_id

    def visibility_allow_list(self, role: str) -> frozenset[str]:
        return _VISIBILITY_BY_ROLE.get(role, _VISIBILITY_BY_ROLE["member"])

    async def retrieve(
        self,
        *,
        plan: RetrievalPlan,
        principal: Principal,
        run_id: str,
    ) -> RetrievalOutcome:
        start = time.perf_counter()
        # Defense-in-depth: tenant injection should have happened in QueryAnalyzer, but we
        # re-enforce here so any code path that builds a plan independently is still safe.
        if plan.filters.tenant_id != principal.tenant_id:
            raise ValueError(
                "RetrievalPlan.filters.tenant_id must equal Principal.tenant_id"
            )

        dense = await self._embed_dense(
            query_text=plan.semantic_query, principal=principal, run_id=run_id
        )
        sparse = self._embed_sparse(plan=plan)

        adapter_filter = VectorFilter(
            tenant_id=principal.tenant_id,
            approved=True,
        )

        adapter_hits: list[AdapterScoredChunk] = await self._store.search(
            query_vector=dense,
            sparse_query=sparse,
            filters=adapter_filter,
            top_k=plan.k,
        )

        allow_list = self.visibility_allow_list(principal.role)
        kept: list[ScoredChunk] = []
        for hit in adapter_hits:
            if hit.chunk.visibility not in allow_list:
                continue
            # Re-validate tenant — defense in depth against an adapter bug.
            if hit.chunk.tenant_id != principal.tenant_id:
                logger.error(
                    "retriever.cross_tenant_hit_dropped",
                    run_id=run_id,
                    expected=principal.tenant_id,
                    seen=hit.chunk.tenant_id,
                    chunk_id=hit.chunk.chunk_id,
                )
                continue
            kept.append(
                ScoredChunk(
                    chunk=hit.chunk,
                    score=hit.score,
                    rerank_score=hit.rerank_score,
                )
            )

        outcome = RetrievalOutcome(
            candidates=kept,
            raw_count=len(adapter_hits),
            visibility_filtered_count=len(adapter_hits) - len(kept),
        )
        logger.info(
            "query.retrieved",
            run_id=run_id,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            stage="a3_retrieval",
            candidate_count=len(kept),
            raw_candidate_count=outcome.raw_count,
            visibility_filtered=outcome.visibility_filtered_count,
            top_k=plan.k,
            sparse_used=sparse is not None,
            duration_ms=int((time.perf_counter() - start) * 1000),
        )
        return outcome

    async def _embed_dense(
        self, *, query_text: str, principal: Principal, run_id: str
    ) -> list[float]:
        vectors = await self._embedder.embed_texts(
            texts=[query_text],
            route_id=self._embedding_route_id,
            tenant_id=principal.tenant_id,
            run_id=run_id,
        )
        if not vectors:
            raise ValueError("embedding provider returned no vector for query")
        return vectors[0]

    def _embed_sparse(self, *, plan: RetrievalPlan) -> SparseVector | None:
        if plan.retrieval is None:
            return None
        if not (plan.retrieval.use_bm25 or plan.retrieval.use_hybrid):
            return None
        if self._sparse is None:
            logger.warning(
                "retriever.sparse_requested_no_embedder",
                semantic_query_len=len(plan.semantic_query),
            )
            return None
        return self._sparse.embed([plan.semantic_query])[0]


__all__ = ["Retriever", "RetrievalOutcome"]
