"""Qdrant-backed VectorStore. Real indexing and retrieval land in T-002 and T-003 (ADR-0013).

T-001 ships the class shape and the runtime tenant-isolation guards."""

from __future__ import annotations

from app.adapters.vector_store.base import (
    ChunkPayload,
    ScoredChunk,
    SparseVector,
    VectorFilter,
    assert_single_tenant_batch,
    assert_tenant_filter,
)


class QdrantStore:
    name = "qdrant"

    def __init__(self, *, embedding_dimension: int) -> None:
        self._embedding_dimension = embedding_dimension

    @property
    def embedding_dimension(self) -> int:
        return self._embedding_dimension

    async def upsert(self, *, payloads: list[ChunkPayload]) -> None:
        assert_single_tenant_batch(payloads)
        raise NotImplementedError("QdrantStore.upsert lands in T-002")

    async def search(
        self,
        *,
        query_vector: list[float],
        sparse_query: SparseVector | None,
        filters: VectorFilter,
        top_k: int,
    ) -> list[ScoredChunk]:
        assert_tenant_filter(filters)
        del query_vector, sparse_query, top_k
        raise NotImplementedError("QdrantStore.search lands in T-003")

    async def delete_by_filter(self, *, filters: VectorFilter) -> int:
        assert_tenant_filter(filters)
        raise NotImplementedError("QdrantStore.delete_by_filter lands in T-002")
