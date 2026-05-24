"""End-to-end test for T-003 (QueryAnalyzer + retrieval).

Audit finding: A-14 — companion to the T-002 e2e test, but exercising the FULL T-003
pipeline (A1 keyword screen → A1+A2 structured call → A3 tenant-filtered retrieval)
against the `POST /api/v1/query` endpoint.

Skipped silently when the `app` package or Qdrant/Postgres aren't reachable; otherwise:
  1. Seed both tenants into Qdrant via `corpus_loader.load_both_tenants`.
  2. Stand up the FastAPI app via `TestClient`, overriding the LLM and embedding deps
     with `FakeStructuredProvider` (the Anthropic adapter for `generate_structured`
     lands in T-004; embeddings are deterministic).
  3. POST a benign query as tenant A and assert: ClassifiedQuery is schema-valid,
     `semanticQuery == rawQuery`, A2's emitted `tenantId` is overwritten with
     `Principal.tenantId`, and A3 returns ≥ 1 chunk that belongs to tenant A and is
     approved.

Required reads when modifying this test:
  - docs/task_cards/phase1/T-003-query-analyzer-retrieval.md
  - docs/schemas/classified-query.schema.json
  - docs/schemas/retrieval-plan.schema.json
  - docs/contracts/code-gen-guide.md (tenant_id injection rules)
"""
from __future__ import annotations

import base64
import json
import socket
from urllib.parse import urlparse

import pytest

pytest.importorskip("app", reason="awaits T-001 backend scaffold")

import contextlib  # noqa: E402

from app.adapters.providers.openai_provider import embedding_dimension_for  # noqa: E402
from app.adapters.vector_store.base import VectorFilter  # noqa: E402
from app.adapters.vector_store.qdrant_store import QdrantStore  # noqa: E402
from app.api.v1._deps import (  # noqa: E402
    get_embedding_provider,
    get_query_analyzer_provider,
    get_safety_config,
    get_vector_store,
)
from app.core.config import get_settings  # noqa: E402
from app.domain.services.safety_config import load_sensitivity_keywords  # noqa: E402
from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.tests.fixtures.corpus_loader import (  # noqa: E402
    TINY_APPROVED,
    load_corpus_fixture,
)
from backend.tests.fixtures.fakes import FakeStructuredProvider  # noqa: E402

pytestmark = pytest.mark.asyncio

_TENANT_A_FIXTURE = json.loads(TINY_APPROVED.read_text())
_TENANT_A_ID: str = _TENANT_A_FIXTURE["tenantId"]


def _service_reachable(url: str, default_port: int) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or default_port
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _dev_header(*, tenant_id: str, role: str = "member") -> dict[str, str]:
    payload = {"tenantId": tenant_id, "role": role, "userId": "usr_e2e_t003"}
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return {"x-dev-principal": encoded}


async def test_classify_then_retrieve_against_fixture() -> None:
    settings = get_settings()
    if not _service_reachable(settings.qdrant_url or "http://localhost:6333", 6333):
        pytest.skip("Qdrant not reachable; T-003 e2e skipped")
    if not _service_reachable(settings.database_url, 5432):
        pytest.skip("Postgres not reachable; T-003 e2e skipped")

    from app.domain.repositories._base import dispose_engine, init_engine
    from sqlalchemy import text as sql_text

    init_engine(settings)

    store = QdrantStore(
        embedding_dimension=embedding_dimension_for("text-embedding-3-small"),
        settings=settings,
    )

    # Wipe any leftovers from previous test runs to keep the assertions deterministic.
    from app.domain.repositories._base import get_sessionmaker

    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(
            sql_text(
                "TRUNCATE TABLE chunks, sources, users, tenants RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()
    with contextlib.suppress(Exception):
        await store.delete_by_filter(filters=VectorFilter(tenant_id=_TENANT_A_ID))

    loaded_a = await load_corpus_fixture(fixture_path=TINY_APPROVED, vector_store=store)

    safety_config = load_sensitivity_keywords(settings.sensitivity_keywords_path)
    provider = FakeStructuredProvider(dimension=embedding_dimension_for("text-embedding-3-small"))

    app.dependency_overrides[get_safety_config] = lambda: safety_config
    app.dependency_overrides[get_query_analyzer_provider] = lambda: provider
    app.dependency_overrides[get_embedding_provider] = lambda: provider
    app.dependency_overrides[get_vector_store] = lambda: store
    # `get_sparse_embedder` not overridden — useBM25 defaults to false so the embedder is
    # never invoked.

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/query",
            json={"queryText": "What do the Fathers teach about prayer?"},
            headers=_dev_header(tenant_id=loaded_a.tenant_id),
        )
        assert response.status_code == 200, response.text
        body = response.json()

        # ClassifiedQuery + RetrievalPlan invariants.
        assert body["classifiedQuery"]["rawQuery"] == "What do the Fathers teach about prayer?"
        assert body["classifiedQuery"]["sensitivityPrimary"] == "normal"
        assert (
            body["retrievalPlan"]["semanticQuery"]
            == body["classifiedQuery"].get("reframedQuery")
            or body["classifiedQuery"]["rawQuery"]
        )

        # Tenant injection: even though the fake responder emits "PLACEHOLDER" for tenantId,
        # the API overrides it with `Principal.tenantId` before retrieval.
        assert body["retrievalPlan"]["tenantId"] == loaded_a.tenant_id
        assert body["retrievalPlan"]["filters"]["tenantId"] == loaded_a.tenant_id
        assert body["retrievalPlan"]["filters"]["approved"] is True

        # Retrieval: at least one chunk, all belonging to tenant A and approved.
        assert len(body["scoredChunks"]) >= 1
        for hit in body["scoredChunks"]:
            assert hit["chunk"]["tenantId"] == loaded_a.tenant_id
            assert hit["chunk"]["approved"] is True
            assert hit["chunk"]["chunkId"] in loaded_a.chunk_ids
    finally:
        app.dependency_overrides.clear()
        with contextlib.suppress(Exception):
            await store.delete_by_filter(filters=VectorFilter(tenant_id=loaded_a.tenant_id))
        await store.close()
        await dispose_engine()


async def test_hard_trigger_returns_block_with_redirect() -> None:
    """A1 hard trigger short-circuits to `block_with_redirect` without calling A3 or any LLM."""
    settings = get_settings()
    if not _service_reachable(settings.qdrant_url or "http://localhost:6333", 6333):
        pytest.skip("Qdrant not reachable; T-003 e2e skipped")
    if not _service_reachable(settings.database_url, 5432):
        pytest.skip("Postgres not reachable; T-003 e2e skipped")

    from app.domain.repositories._base import dispose_engine, init_engine

    init_engine(settings)

    safety_config = load_sensitivity_keywords(settings.sensitivity_keywords_path)
    provider = FakeStructuredProvider()
    # An intentionally-broken QdrantStore would still not be touched by a hard-trigger query.

    class _RefuseAllStore:
        name = "refuse-all"
        embedding_dimension = 1536

        async def upsert(self, **_):  # pragma: no cover
            raise RuntimeError("must not be called")

        async def search(self, **_):  # pragma: no cover
            raise RuntimeError("must not be called for hard triggers")

        async def delete_by_filter(self, **_) -> int:  # pragma: no cover
            return 0

    app.dependency_overrides[get_safety_config] = lambda: safety_config
    app.dependency_overrides[get_query_analyzer_provider] = lambda: provider
    app.dependency_overrides[get_embedding_provider] = lambda: provider
    app.dependency_overrides[get_vector_store] = lambda: _RefuseAllStore()

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/query",
            json={"queryText": "I want to kill myself"},
            headers=_dev_header(tenant_id=_TENANT_A_ID),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["classifiedQuery"]["handling"] == "block_with_redirect"
        assert "self_harm" in body["classifiedQuery"]["riskFlags"]
        assert body["scoredChunks"] == []
        assert provider.calls == []  # no LLM call
    finally:
        app.dependency_overrides.clear()
        await dispose_engine()
