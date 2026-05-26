"""Tests for `app.domain.services.retriever.Retriever`."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest
from app.adapters.vector_store.base import (
    ChunkPayload,
    SparseVector,
    VectorFilter,
)
from app.adapters.vector_store.base import (
    ScoredChunk as AdapterScoredChunk,
)
from app.core.auth import make_dev_principal
from app.domain.models.chunk import Chunk
from app.domain.models.retrieval_plan import (
    RetrievalConfig,
    RetrievalFilters,
    RetrievalPlan,
)
from app.domain.services.retriever import Retriever

from tests.fixtures.fakes import FakeStructuredProvider


@dataclass
class FakeVectorStore:
    name: str = "fake-vector-store"
    hits: list[AdapterScoredChunk] = field(default_factory=list)
    seen_filter: VectorFilter | None = None
    seen_sparse: SparseVector | None = None
    seen_query_vector: list[float] | None = None
    seen_top_k: int | None = None

    async def upsert(self, *, payloads: list[ChunkPayload]) -> None:  # pragma: no cover
        raise NotImplementedError

    async def search(
        self,
        *,
        query_vector: list[float],
        sparse_query: SparseVector | None,
        filters: VectorFilter,
        top_k: int,
    ) -> list[AdapterScoredChunk]:
        self.seen_query_vector = query_vector
        self.seen_sparse = sparse_query
        self.seen_filter = filters
        self.seen_top_k = top_k
        return list(self.hits)

    async def delete_by_filter(self, *, filters: VectorFilter) -> int:  # pragma: no cover
        del filters
        return 0

    @property
    def embedding_dimension(self) -> int:
        return 1536


class FakeSparseEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts):
        self.calls.append(list(texts))
        return [SparseVector(indices=[0, 1, 2], values=[0.1, 0.2, 0.3]) for _ in texts]


def _make_chunk(
    *,
    chunk_id: str,
    tenant_id: str = "tn_test",
    visibility: str = "member",
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        source_id=f"src-{chunk_id}",
        tenant_id=tenant_id,
        text="fixture text",
        chunk_hash=("sha256:" + "0" * 64),
        approved=True,
        visibility=visibility,
        embedding_model="text-embedding-3-small",
        embedding_dimension=1536,
        corpus_version="fixture-2026-05-01",
        created_at=datetime.now(UTC),
    )


def _plan(
    *,
    tenant_id: str = "tn_test",
    semantic_query: str = "test query",
    k: int = 5,
    retrieval: RetrievalConfig | None = None,
) -> RetrievalPlan:
    return RetrievalPlan(
        semantic_query=semantic_query,
        answer_mode="consensus",
        tenant_id=tenant_id,
        filters=RetrievalFilters(tenant_id=tenant_id, approved=True),
        k=k,
        retrieval=retrieval,
    )


@pytest.fixture()
def principal():
    return make_dev_principal(tenant_id="tn_test", role="member", user_id="usr_test")


async def test_vector_filter_carries_tenant_and_approved(principal):
    store = FakeVectorStore(hits=[
        AdapterScoredChunk(chunk=_make_chunk(chunk_id="c-1"), score=0.9),
    ])
    retriever = Retriever(
        embedding_provider=FakeStructuredProvider(),
        vector_store=store,
        embedding_route_id="embedding_openai@1",
    )

    await retriever.retrieve(plan=_plan(), principal=principal, run_id="r1")

    assert store.seen_filter is not None
    assert store.seen_filter.tenant_id == "tn_test"
    assert store.seen_filter.approved is True
    assert store.seen_top_k == 5


async def test_dense_only_search_when_sparse_not_requested(principal):
    store = FakeVectorStore()
    sparse = FakeSparseEmbedder()
    retriever = Retriever(
        embedding_provider=FakeStructuredProvider(),
        vector_store=store,
        sparse_embedder=sparse,
        embedding_route_id="embedding_openai@1",
    )

    await retriever.retrieve(plan=_plan(), principal=principal, run_id="r1")

    assert store.seen_sparse is None
    assert sparse.calls == []


async def test_sparse_vector_computed_when_use_bm25(principal):
    store = FakeVectorStore()
    sparse = FakeSparseEmbedder()
    retriever = Retriever(
        embedding_provider=FakeStructuredProvider(),
        vector_store=store,
        sparse_embedder=sparse,
        embedding_route_id="embedding_openai@1",
    )

    await retriever.retrieve(
        plan=_plan(retrieval=RetrievalConfig(use_bm25=True)),
        principal=principal,
        run_id="r1",
    )

    assert store.seen_sparse is not None
    assert sparse.calls == [["test query"]]


async def test_sparse_skipped_when_no_embedder_configured(principal):
    store = FakeVectorStore()
    retriever = Retriever(
        embedding_provider=FakeStructuredProvider(),
        vector_store=store,
        sparse_embedder=None,
        embedding_route_id="embedding_openai@1",
    )

    outcome = await retriever.retrieve(
        plan=_plan(retrieval=RetrievalConfig(use_hybrid=True)),
        principal=principal,
        run_id="r1",
    )

    # Search still runs (dense-only); sparse just isn't attached.
    assert store.seen_sparse is None
    assert outcome.raw_count == 0


async def test_visibility_filter_drops_scholar_chunk_for_member():
    store = FakeVectorStore(hits=[
        AdapterScoredChunk(
            chunk=_make_chunk(chunk_id="c-member", visibility="member"), score=0.9
        ),
        AdapterScoredChunk(
            chunk=_make_chunk(chunk_id="c-scholar", visibility="scholar"), score=0.8
        ),
        AdapterScoredChunk(
            chunk=_make_chunk(chunk_id="c-admin", visibility="admin_only"), score=0.7
        ),
    ])
    retriever = Retriever(
        embedding_provider=FakeStructuredProvider(),
        vector_store=store,
        embedding_route_id="embedding_openai@1",
    )

    outcome = await retriever.retrieve(
        plan=_plan(),
        principal=make_dev_principal(tenant_id="tn_test", role="member"),
        run_id="r1",
    )

    chunk_ids = [c.chunk.chunk_id for c in outcome.candidates]
    assert chunk_ids == ["c-member"]
    assert outcome.raw_count == 3
    assert outcome.visibility_filtered_count == 2


async def test_visibility_filter_lets_scholar_see_member_and_scholar():
    store = FakeVectorStore(hits=[
        AdapterScoredChunk(
            chunk=_make_chunk(chunk_id="c-member", visibility="member"), score=0.9
        ),
        AdapterScoredChunk(
            chunk=_make_chunk(chunk_id="c-scholar", visibility="scholar"), score=0.8
        ),
        AdapterScoredChunk(
            chunk=_make_chunk(chunk_id="c-admin", visibility="admin_only"), score=0.7
        ),
    ])
    retriever = Retriever(
        embedding_provider=FakeStructuredProvider(),
        vector_store=store,
        embedding_route_id="embedding_openai@1",
    )

    outcome = await retriever.retrieve(
        plan=_plan(),
        principal=make_dev_principal(tenant_id="tn_test", role="scholar"),
        run_id="r1",
    )

    chunk_ids = {c.chunk.chunk_id for c in outcome.candidates}
    assert chunk_ids == {"c-member", "c-scholar"}


async def test_cross_tenant_hit_is_dropped():
    """Defense-in-depth: foreign-tenant hits from the adapter are dropped by the retriever."""
    store = FakeVectorStore(hits=[
        AdapterScoredChunk(
            chunk=_make_chunk(chunk_id="c-foreign", tenant_id="tn_other"),
            score=0.99,
        ),
        AdapterScoredChunk(
            chunk=_make_chunk(chunk_id="c-mine", tenant_id="tn_test"),
            score=0.5,
        ),
    ])
    retriever = Retriever(
        embedding_provider=FakeStructuredProvider(),
        vector_store=store,
        embedding_route_id="embedding_openai@1",
    )

    outcome = await retriever.retrieve(
        plan=_plan(),
        principal=make_dev_principal(tenant_id="tn_test", role="member"),
        run_id="r1",
    )

    chunk_ids = [c.chunk.chunk_id for c in outcome.candidates]
    assert chunk_ids == ["c-mine"]


async def test_plan_tenant_mismatch_raises():
    store = FakeVectorStore()
    retriever = Retriever(
        embedding_provider=FakeStructuredProvider(),
        vector_store=store,
        embedding_route_id="embedding_openai@1",
    )

    with pytest.raises(ValueError, match="tenant_id"):
        await retriever.retrieve(
            plan=_plan(tenant_id="tn_wrong"),
            principal=make_dev_principal(tenant_id="tn_test"),
            run_id="r1",
        )


async def test_empty_hits_returns_empty_outcome(principal):
    store = FakeVectorStore(hits=[])
    retriever = Retriever(
        embedding_provider=FakeStructuredProvider(),
        vector_store=store,
        embedding_route_id="embedding_openai@1",
    )

    outcome = await retriever.retrieve(plan=_plan(), principal=principal, run_id="r1")

    assert outcome.candidates == []
    assert outcome.raw_count == 0
