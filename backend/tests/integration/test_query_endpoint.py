"""Integration tests for `POST /api/v1/query`.

Uses FastAPI's `TestClient` with `app.dependency_overrides` to swap in fakes for the
LLM provider, embedding provider, vector store, and sparse embedder. No real Postgres,
Redis, or Qdrant required.
"""

from __future__ import annotations

import base64
import json
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
from app.api.v1._deps import (
    get_embedding_provider,
    get_query_analyzer_provider,
    get_safety_config,
    get_sparse_embedder,
    get_vector_store,
)
from app.domain.models.chunk import Chunk
from app.domain.services.safety_config import load_sensitivity_keywords
from app.main import app
from fastapi.testclient import TestClient

from tests.fixtures.fakes import (
    FakeStructuredProvider,
    RefusingStructuredProvider,
    default_query_analyzer_responder,
)


@dataclass
class StubVectorStore:
    name: str = "stub-vector-store"
    hits: list[AdapterScoredChunk] = field(default_factory=list)
    seen_filter: VectorFilter | None = None

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
        del query_vector, sparse_query, top_k
        self.seen_filter = filters
        return list(self.hits)

    async def delete_by_filter(self, *, filters: VectorFilter) -> int:  # pragma: no cover
        del filters
        return 0

    @property
    def embedding_dimension(self) -> int:
        return 1536


class StubSparseEmbedder:
    def embed(self, texts):
        return [SparseVector(indices=[1, 2], values=[0.1, 0.2]) for _ in texts]


def _dev_header(*, tenant_id: str = "tn_test", role: str = "member") -> dict[str, str]:
    payload = {"tenantId": tenant_id, "role": role, "userId": "usr_test"}
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return {"x-dev-principal": encoded}


def _hit(*, chunk_id: str, tenant_id: str = "tn_test", visibility: str = "member"):
    chunk = Chunk(
        chunk_id=chunk_id,
        source_id=f"src-{chunk_id}",
        tenant_id=tenant_id,
        text=f"text for {chunk_id}",
        chunk_hash="sha256:" + "0" * 64,
        approved=True,
        visibility=visibility,
        embedding_model="text-embedding-3-small",
        embedding_dimension=1536,
        corpus_version="fixture",
        created_at=datetime.now(UTC),
    )
    return AdapterScoredChunk(chunk=chunk, score=0.85)


@pytest.fixture()
def client():
    safety_config = load_sensitivity_keywords(
        "/home/user/Orthodox-AI-Assistant/config/sensitivity_keywords.yaml"
    )
    embed_and_analyzer = FakeStructuredProvider()
    store = StubVectorStore(hits=[_hit(chunk_id="chunk-test-1")])
    sparse = StubSparseEmbedder()

    app.dependency_overrides[get_safety_config] = lambda: safety_config
    app.dependency_overrides[get_query_analyzer_provider] = lambda: embed_and_analyzer
    app.dependency_overrides[get_embedding_provider] = lambda: embed_and_analyzer
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_sparse_embedder] = lambda: sparse

    yield TestClient(app), store, embed_and_analyzer
    app.dependency_overrides.clear()


def test_query_happy_path_returns_classified_plan_and_chunks(client):
    test_client, store, _ = client
    response = test_client.post(
        "/api/v1/query",
        json={"queryText": "What do the Fathers teach about prayer?"},
        headers=_dev_header(),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["classifiedQuery"]["rawQuery"] == "What do the Fathers teach about prayer?"
    assert body["classifiedQuery"]["handling"] == "answer"
    assert body["retrievalPlan"]["tenantId"] == "tn_test"
    assert body["retrievalPlan"]["filters"]["tenantId"] == "tn_test"
    assert body["retrievalPlan"]["filters"]["approved"] is True
    assert len(body["scoredChunks"]) == 1
    assert body["scoredChunks"][0]["chunk"]["chunkId"] == "chunk-test-1"

    # The retriever forwarded the tenant filter we expect.
    assert store.seen_filter is not None
    assert store.seen_filter.tenant_id == "tn_test"
    assert store.seen_filter.approved is True


def test_hard_trigger_returns_block_with_redirect_and_no_retrieval(client):
    test_client, store, fake_provider = client
    response = test_client.post(
        "/api/v1/query",
        json={"queryText": "I want to kill myself"},
        headers=_dev_header(),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["classifiedQuery"]["handling"] == "block_with_redirect"
    assert body["scoredChunks"] == []
    assert store.seen_filter is None  # retriever never invoked
    assert fake_provider.calls == []  # LLM never invoked


def test_query_read_scope_is_required():
    """A Principal without `query:read` is rejected with 403 by `require_scope`."""
    from app.api.v1._deps import get_principal
    from app.core.auth import make_dev_principal

    safety_config = load_sensitivity_keywords(
        "/home/user/Orthodox-AI-Assistant/config/sensitivity_keywords.yaml"
    )

    def no_scope_principal():
        principal = make_dev_principal(tenant_id="tn_test", role="member")
        # Drop the query:read scope to force a 403.
        return principal.model_copy(update={"scopes": ["corpus:read"]})

    app.dependency_overrides[get_safety_config] = lambda: safety_config
    app.dependency_overrides[get_principal] = no_scope_principal

    try:
        test_client = TestClient(app)
        response = test_client.post(
            "/api/v1/query",
            json={"queryText": "benign"},
            headers=_dev_header(),
        )
        assert response.status_code == 403, response.text
    finally:
        app.dependency_overrides.clear()


def test_validation_error_for_empty_query(client):
    test_client, _, _ = client
    response = test_client.post(
        "/api/v1/query",
        json={"queryText": ""},
        headers=_dev_header(),
    )
    assert response.status_code == 422


def test_provider_refusal_falls_back_to_insufficient_evidence():
    safety_config = load_sensitivity_keywords(
        "/home/user/Orthodox-AI-Assistant/config/sensitivity_keywords.yaml"
    )
    refusing = RefusingStructuredProvider()
    store = StubVectorStore(hits=[_hit(chunk_id="chunk-1")])
    sparse = StubSparseEmbedder()

    app.dependency_overrides[get_safety_config] = lambda: safety_config
    app.dependency_overrides[get_query_analyzer_provider] = lambda: refusing
    app.dependency_overrides[get_embedding_provider] = lambda: FakeStructuredProvider()
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_sparse_embedder] = lambda: sparse

    try:
        test_client = TestClient(app)
        response = test_client.post(
            "/api/v1/query",
            json={"queryText": "a question the LLM will refuse"},
            headers=_dev_header(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["classifiedQuery"]["handling"] == "insufficient_evidence"
    finally:
        app.dependency_overrides.clear()


def test_deferred_provider_returns_503_for_non_hard_trigger():
    """Without overriding `get_query_analyzer_provider`, a non-hard-trigger query hits the
    deferred placeholder which raises HTTP 503 / feature_deferred."""
    safety_config = load_sensitivity_keywords(
        "/home/user/Orthodox-AI-Assistant/config/sensitivity_keywords.yaml"
    )
    store = StubVectorStore(hits=[])
    sparse = StubSparseEmbedder()

    app.dependency_overrides[get_safety_config] = lambda: safety_config
    # Intentionally NOT overriding get_query_analyzer_provider.
    app.dependency_overrides[get_embedding_provider] = lambda: FakeStructuredProvider()
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_sparse_embedder] = lambda: sparse

    try:
        test_client = TestClient(app)
        response = test_client.post(
            "/api/v1/query",
            json={"queryText": "a benign question that needs A1/A2"},
            headers=_dev_header(),
        )
        assert response.status_code == 503
        body = response.json()
        assert body["detail"]["code"] == "feature_deferred"
    finally:
        app.dependency_overrides.clear()


def test_deferred_provider_still_serves_hard_trigger():
    """Hard-trigger queries don't need the LLM, so the deferred provider doesn't fire."""
    safety_config = load_sensitivity_keywords(
        "/home/user/Orthodox-AI-Assistant/config/sensitivity_keywords.yaml"
    )
    store = StubVectorStore(hits=[])
    sparse = StubSparseEmbedder()

    app.dependency_overrides[get_safety_config] = lambda: safety_config
    app.dependency_overrides[get_embedding_provider] = lambda: FakeStructuredProvider()
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_sparse_embedder] = lambda: sparse

    try:
        test_client = TestClient(app)
        response = test_client.post(
            "/api/v1/query",
            json={"queryText": "I want to end my life"},
            headers=_dev_header(),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["classifiedQuery"]["handling"] == "block_with_redirect"
    finally:
        app.dependency_overrides.clear()


def test_responder_can_force_use_bm25_and_sparse_is_computed():
    safety_config = load_sensitivity_keywords(
        "/home/user/Orthodox-AI-Assistant/config/sensitivity_keywords.yaml"
    )

    def responder(query_text, schema):
        classified, plan = default_query_analyzer_responder(query_text, schema)
        plan["retrieval"]["useBM25"] = True
        return classified, plan

    provider = FakeStructuredProvider(responder=responder)
    store = StubVectorStore(hits=[_hit(chunk_id="chunk-x")])

    class TrackingSparse:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def embed(self, texts):
            self.calls.append(list(texts))
            return [SparseVector(indices=[0], values=[0.1]) for _ in texts]

    sparse = TrackingSparse()

    app.dependency_overrides[get_safety_config] = lambda: safety_config
    app.dependency_overrides[get_query_analyzer_provider] = lambda: provider
    app.dependency_overrides[get_embedding_provider] = lambda: provider
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_sparse_embedder] = lambda: sparse

    try:
        test_client = TestClient(app)
        response = test_client.post(
            "/api/v1/query",
            json={"queryText": "specific Greek term ἀγάπη in canon citations"},
            headers=_dev_header(),
        )
        assert response.status_code == 200, response.text
        assert sparse.calls, "sparse embedder should have been invoked"
    finally:
        app.dependency_overrides.clear()
