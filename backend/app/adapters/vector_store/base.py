"""VectorStore Protocol per docs/contracts/vector-store-interface.md (ADR-0010).

T-001 ships the Protocol, the strict tenant-isolation invariants in `VectorFilter`, the runtime
guards on `search`/`delete_by_filter`/`upsert`, and a QdrantStore stub. Real Qdrant calls land in
T-002 (indexing) and T-003 (retrieval)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.domain.models.chunk import Chunk


@dataclass(frozen=True)
class SparseVector:
    indices: list[int]
    values: list[float]


@dataclass(frozen=True)
class ChunkPayload:
    chunk_id: str
    tenant_id: str
    source_id: str
    source_hash: str
    chunk_hash: str
    text: str
    section_path: list[str]
    page_start: int | None
    page_end: int | None
    parent_chunk_id: str | None
    approved: bool
    visibility: str
    embedding_model: str
    embedding_dimension: int
    corpus_version: str
    embedding: list[float]
    sparse_embedding: SparseVector | None = None


@dataclass(frozen=True)
class VectorFilter:
    """Tenant-isolation invariant per ADR-0010: `tenant_id` is required and must be non-empty."""

    tenant_id: str
    approved: bool | None = None
    visibility: str | None = None
    source_id: str | None = None

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.tenant_id.strip():
            raise ValueError("tenant_id required")


@dataclass(frozen=True)
class ScoredChunk:
    chunk: Chunk
    score: float
    rerank_score: float | None = None


@runtime_checkable
class VectorStore(Protocol):
    name: str

    async def upsert(self, *, payloads: list[ChunkPayload]) -> None: ...

    async def search(
        self,
        *,
        query_vector: list[float],
        sparse_query: SparseVector | None,
        filters: VectorFilter,
        top_k: int,
    ) -> list[ScoredChunk]: ...

    async def delete_by_filter(self, *, filters: VectorFilter) -> int: ...

    @property
    def embedding_dimension(self) -> int: ...


def assert_tenant_filter(filters: VectorFilter) -> None:
    """Runtime guard used by every VectorStore concrete impl before issuing I/O."""
    if not filters.tenant_id or not filters.tenant_id.strip():
        raise ValueError("tenant_id required")


def assert_single_tenant_batch(payloads: list[ChunkPayload]) -> None:
    """Reject mixed-tenant upsert batches per ADR-0010."""
    tenant_ids = {p.tenant_id for p in payloads if p.tenant_id and p.tenant_id.strip()}
    if not tenant_ids and payloads:
        raise ValueError("tenant_id required")
    if len(tenant_ids) > 1:
        raise ValueError("mixed-tenant upsert batch")
