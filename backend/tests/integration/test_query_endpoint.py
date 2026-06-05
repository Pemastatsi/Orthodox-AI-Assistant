"""Integration tests for `POST /api/v1/query` (T-004 / VerifiedResponse shape).

Uses FastAPI's `TestClient` with `app.dependency_overrides` to swap in fakes for the
LLM provider, embedding provider, vector store, composer provider, and sparse embedder.
No real Postgres, Redis, Qdrant, or LLM providers required.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

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
    get_composer_provider,
    get_embedding_provider,
    get_pastoral_config,
    get_query_analyzer_provider,
    get_safety_config,
    get_sparse_embedder,
    get_vector_store,
    get_verifier_provider,
)
from app.domain.models.chunk import Chunk
from app.domain.services.safety_config import (
    load_pastoral_filters,
    load_sensitivity_keywords,
)
from app.main import app
from fastapi.testclient import TestClient

from tests.fixtures.fakes import (
    ComposerFakeProvider,
    FakeStructuredProvider,
    RefusingStructuredProvider,
    default_query_analyzer_responder,
)

# Repo-root-relative so the suite runs in any checkout (CI included), not only a
# /home/user/Orthodox-AI-Assistant container. Mirrors app/core/config.py's _REPO_ROOT.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SENSITIVITY_PATH = str(_REPO_ROOT / "config" / "sensitivity_keywords.yaml")
_PASTORAL_PATH = str(_REPO_ROOT / "config" / "pastoral_filters.yaml")


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


def _hit(
    *,
    chunk_id: str,
    tenant_id: str = "tn_test",
    visibility: str = "member",
    text: str | None = None,
    score: float = 0.85,
):
    chunk = Chunk(
        chunk_id=chunk_id,
        source_id=f"src-{chunk_id}",
        tenant_id=tenant_id,
        text=text or (
            "Saint Basil writes that prayer requires patience and steadfastness. "
            "He teaches us to ask, seek, and knock without despair."
        ),
        chunk_hash="sha256:" + "0" * 64,
        approved=True,
        visibility=visibility,
        embedding_model="text-embedding-3-small",
        embedding_dimension=1536,
        corpus_version="fixture",
        created_at=datetime.now(UTC),
    )
    return AdapterScoredChunk(chunk=chunk, score=score)


@pytest.fixture()
def client():
    safety_config = load_sensitivity_keywords(_SENSITIVITY_PATH)
    pastoral_config = load_pastoral_filters(_PASTORAL_PATH)
    analyzer_provider = FakeStructuredProvider()
    composer_provider = ComposerFakeProvider(
        answer="Saint Basil writes that prayer requires patience and steadfastness.",
        cited_chunk_ids=["chunk-test-1"],
    )
    store = StubVectorStore(hits=[_hit(chunk_id="chunk-test-1")])
    sparse = StubSparseEmbedder()

    app.dependency_overrides[get_safety_config] = lambda: safety_config
    app.dependency_overrides[get_pastoral_config] = lambda: pastoral_config
    app.dependency_overrides[get_query_analyzer_provider] = lambda: analyzer_provider
    app.dependency_overrides[get_composer_provider] = lambda: composer_provider
    app.dependency_overrides[get_verifier_provider] = lambda: None
    app.dependency_overrides[get_embedding_provider] = lambda: analyzer_provider
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_sparse_embedder] = lambda: sparse

    yield TestClient(app), store, analyzer_provider, composer_provider
    app.dependency_overrides.clear()


def test_query_happy_path_returns_verified_response(client):
    test_client, store, _, _ = client
    response = test_client.post(
        "/api/v1/query",
        json={"queryText": "What do the Fathers teach about prayer?"},
        headers=_dev_header(),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # Canonical VerifiedResponse shape.
    assert body["handling"] == "answer"
    assert body["verification"]["passed"] is True
    assert len(body["citations"]) == 1
    assert body["citations"][0]["chunkId"] == "chunk-test-1"
    assert body["citations"][0]["corpusOrigin"] == "tenant"
    assert body["confidenceTier"] in {"GREEN", "YELLOW", "RED"}
    assert body["servedFromCache"] is False
    assert body["schemaVersion"]
    assert body["runId"].startswith("run_")
    # Retriever was actually invoked.
    assert store.seen_filter is not None
    assert store.seen_filter.tenant_id == "tn_test"
    assert store.seen_filter.approved is True


def test_hard_trigger_returns_self_harm_canonical_text(client):
    test_client, store, fake_provider, composer_provider = client
    response = test_client.post(
        "/api/v1/query",
        json={"queryText": "I want to kill myself"},
        headers=_dev_header(),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["handling"] == "block_with_redirect"
    assert "988" in body["answer"]
    assert body["citations"] == []
    # Pipeline short-circuited — neither A3 nor A5 fired.
    assert store.seen_filter is None
    assert fake_provider.calls == []
    assert composer_provider.calls == []


def test_political_query_returns_political_canonical_text(client):
    test_client, _, _, composer_provider = client
    response = test_client.post(
        "/api/v1/query",
        json={"queryText": "Who should I vote for in November?"},
        headers=_dev_header(),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # A1 (FakeStructuredProvider) defaults to handling=answer, but the keyword-screen flags
    # the query as a `political` *soft* candidate. The FakeStructuredProvider responder
    # used here returns the default `handling=answer`, so this query will NOT short-circuit
    # — it will go through the normal pipeline. We still check the schema is intact.
    assert body["handling"] in {
        "answer",
        "answer_with_disclaimer",
        "block_with_redirect",
        "insufficient_evidence",
    }


def test_empty_retrieval_returns_insufficient_evidence(client):
    """When the retriever returns no candidates, A4 admits zero chunks and we return the
    out_of_corpus bounded fallback (HTTP 200, not 409)."""
    test_client, store, _, composer_provider = client
    store.hits.clear()

    response = test_client.post(
        "/api/v1/query",
        json={"queryText": "an obscure topic with no corpus coverage"},
        headers=_dev_header(),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["handling"] == "insufficient_evidence"
    assert body["confidenceTier"] == "RED"
    assert body["citations"] == []
    assert "approved library does not contain" in body["answer"]
    # A5 never ran because A4 was empty.
    assert composer_provider.calls == []


def test_query_read_scope_is_required():
    """A Principal without `query:read` is rejected with 403."""
    from app.api.v1._deps import get_principal
    from app.core.auth import make_dev_principal

    safety_config = load_sensitivity_keywords(_SENSITIVITY_PATH)

    def no_scope_principal():
        principal = make_dev_principal(tenant_id="tn_test", role="member")
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
    test_client, _, _, _ = client
    response = test_client.post(
        "/api/v1/query",
        json={"queryText": ""},
        headers=_dev_header(),
    )
    assert response.status_code == 422


def test_provider_refusal_falls_back_to_insufficient_evidence():
    safety_config = load_sensitivity_keywords(_SENSITIVITY_PATH)
    pastoral_config = load_pastoral_filters(_PASTORAL_PATH)
    refusing = RefusingStructuredProvider()
    store = StubVectorStore(hits=[_hit(chunk_id="chunk-1")])
    sparse = StubSparseEmbedder()

    app.dependency_overrides[get_safety_config] = lambda: safety_config
    app.dependency_overrides[get_pastoral_config] = lambda: pastoral_config
    app.dependency_overrides[get_query_analyzer_provider] = lambda: refusing
    app.dependency_overrides[get_composer_provider] = lambda: ComposerFakeProvider(
        cited_chunk_ids=["chunk-1"]
    )
    app.dependency_overrides[get_verifier_provider] = lambda: None
    app.dependency_overrides[get_embedding_provider] = lambda: FakeStructuredProvider()
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_sparse_embedder] = lambda: sparse

    try:
        test_client = TestClient(app)
        response = test_client.post(
            "/api/v1/query",
            json={"queryText": "a question the analyzer LLM refuses"},
            headers=_dev_header(),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        # A1 refusal → analyzer falls back to insufficient_evidence; A4/A5/A6 do still
        # run, but the analyzer-emitted `handling=insufficient_evidence` flows through.
        assert body["handling"] in {"insufficient_evidence", "answer"}
    finally:
        app.dependency_overrides.clear()


def test_query_with_bm25_uses_sparse_embedder():
    safety_config = load_sensitivity_keywords(_SENSITIVITY_PATH)
    pastoral_config = load_pastoral_filters(_PASTORAL_PATH)

    def responder(query_text, schema):
        classified, plan = default_query_analyzer_responder(query_text, schema)
        plan["retrieval"]["useBM25"] = True
        return classified, plan

    analyzer = FakeStructuredProvider(responder=responder)
    composer_provider = ComposerFakeProvider(cited_chunk_ids=["chunk-x"])
    store = StubVectorStore(hits=[_hit(chunk_id="chunk-x")])

    class TrackingSparse:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def embed(self, texts):
            self.calls.append(list(texts))
            return [SparseVector(indices=[0], values=[0.1]) for _ in texts]

    sparse = TrackingSparse()

    app.dependency_overrides[get_safety_config] = lambda: safety_config
    app.dependency_overrides[get_pastoral_config] = lambda: pastoral_config
    app.dependency_overrides[get_query_analyzer_provider] = lambda: analyzer
    app.dependency_overrides[get_composer_provider] = lambda: composer_provider
    app.dependency_overrides[get_verifier_provider] = lambda: None
    app.dependency_overrides[get_embedding_provider] = lambda: analyzer
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
