"""Integration tests for tenant isolation invariants.

Audit finding: F-13
Context citations:
  - docs/contracts/phase1-implementation-contract.md — Phase 1 → Phase 2 Exit Criteria #5
  - tests/fixtures/corpus/tiny_other_tenant_corpus.json — isolationCases block
  - docs/contracts/cache-key.md — tenantId is a required cache-key field
  - docs/contracts/observability.md — run_traces.stages[] must not leak cross-tenant data
  - docs/task_cards/phase1/T-005-cache-logs-billing.md — Acceptance Tests

This file is the NAMED OWNER of the tenant-isolation invariant per
phase1-implementation-contract.md exit criterion #5. It carries the end-to-end A3-retrieval
cross-tenant check below. The A4/A5, cache-key, run-trace, and /admin/queries isolation concerns
(originally stubbed here for T-004..T-006) are now covered by the backend suite: RLS checks in
backend/tests/integration/test_tenant_isolation.py, plus backend/tests/unit/
test_vector_store_isolation.py, test_cache_key.py, and test_evidence_packager.py.

Fixture reference — isolationCases from tiny_other_tenant_corpus.json:
  tenant_a_query_about_prayer:
    submittingTenant: tn_orthodoxethos
    query: "What do the Fathers teach about prayer?"
    mustNotReturnChunkIds: ["chunk-other-prayer-001"]
  tenant_a_query_about_eucharist:
    submittingTenant: tn_orthodoxethos
    query: "What is the Orthodox view of the Eucharist?"
    mustNotReturnChunkIds: ["chunk-other-eucharist-001"]
  tenant_a_query_about_philokalia:
    submittingTenant: tn_orthodoxethos
    query: "Tell me about the Philokalia."
    mustNotReturnChunkIds: ["chunk-other-philokalia-001"]

Zero cross-tenant leaks are required for Phase 1 → 2 gate.
"""
import base64
import json
import socket
from pathlib import Path
from urllib.parse import urlparse

import pytest

pytest.importorskip("app", reason="awaits T-001 backend scaffold")

# ---------------------------------------------------------------------------
# Fixture data — sourced directly from the canonical JSON fixture.
# ---------------------------------------------------------------------------

_FIXTURE_PATH = (
    Path(__file__).parent.parent
    / "fixtures"
    / "corpus"
    / "tiny_other_tenant_corpus.json"
)

with open(_FIXTURE_PATH, encoding="utf-8") as _f:
    _OTHER_TENANT_FIXTURE = json.load(_f)

_ISOLATION_CASES = _OTHER_TENANT_FIXTURE["isolationCases"]

# Derived constants for assertion bodies
_TENANT_A_ID = "tn_orthodoxethos"
_TENANT_B_ID = _OTHER_TENANT_FIXTURE["tenantId"]  # "tn_other"

# All chunk IDs that must NEVER appear in Tenant A results
_ALL_MUST_NOT_CHUNK_IDS: set[str] = set()
for _case in _ISOLATION_CASES.values():
    _ALL_MUST_NOT_CHUNK_IDS.update(_case["mustNotReturnChunkIds"])

# Query list for parametrized tests
_ISOLATION_QUERY_PARAMS = [
    (case_id, case["query"], set(case["mustNotReturnChunkIds"]))
    for case_id, case in _ISOLATION_CASES.items()
]


# ---------------------------------------------------------------------------
# Tenant-isolation test (A3 retrieval, end-to-end)
# ---------------------------------------------------------------------------


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
    payload = {"tenantId": tenant_id, "role": role, "userId": "usr_iso_test"}
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return {"x-dev-principal": encoded}


@pytest.mark.asyncio
async def test_a3_retrieval_excludes_other_tenant_chunks() -> None:
    """For each isolation case in tiny_other_tenant_corpus.json, submit the query as Tenant A
    and assert no chunk from Tenant B appears in the A3 retrieval response."""
    import contextlib

    from app.adapters.providers.openai_provider import embedding_dimension_for
    from app.adapters.vector_store.base import VectorFilter
    from app.adapters.vector_store.qdrant_store import QdrantStore
    from app.api.v1._deps import (
        get_embedding_provider,
        get_query_analyzer_provider,
        get_safety_config,
        get_sparse_embedder,
        get_vector_store,
    )
    from app.core.config import get_settings
    from app.domain.repositories._base import dispose_engine, get_sessionmaker, init_engine
    from app.domain.services.safety_config import load_sensitivity_keywords
    from app.main import app
    from fastapi.testclient import TestClient
    from sqlalchemy import text as sql_text

    from backend.tests.fixtures.corpus_loader import (
        TINY_APPROVED,
        TINY_OTHER,
        load_corpus_fixture,
    )
    from backend.tests.fixtures.fakes import FakeStructuredProvider

    settings = get_settings()
    if not _service_reachable(settings.qdrant_url or "http://localhost:6333", 6333):
        pytest.skip("Qdrant not reachable; tenant-isolation test skipped")
    if not _service_reachable(settings.database_url, 5432):
        pytest.skip("Postgres not reachable; tenant-isolation test skipped")

    init_engine(settings)
    store = QdrantStore(
        embedding_dimension=embedding_dimension_for("text-embedding-3-small"),
        settings=settings,
    )

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
        await store.delete_by_filter(filters=VectorFilter(tenant_id=_TENANT_B_ID))

    # Seed BOTH tenants so the cross-tenant leak surface is populated.
    loaded_a = await load_corpus_fixture(fixture_path=TINY_APPROVED, vector_store=store)
    loaded_b = await load_corpus_fixture(fixture_path=TINY_OTHER, vector_store=store)
    assert loaded_a.tenant_id == _TENANT_A_ID
    assert loaded_b.tenant_id == _TENANT_B_ID

    safety_config = load_sensitivity_keywords(settings.sensitivity_keywords_path)
    provider = FakeStructuredProvider(
        dimension=embedding_dimension_for("text-embedding-3-small")
    )

    app.dependency_overrides[get_safety_config] = lambda: safety_config
    app.dependency_overrides[get_query_analyzer_provider] = lambda: provider
    app.dependency_overrides[get_embedding_provider] = lambda: provider
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_sparse_embedder] = lambda: None  # not used; useBM25=false

    try:
        client = TestClient(app)
        for case_id, query, must_not_ids in _ISOLATION_QUERY_PARAMS:
            response = client.post(
                "/api/v1/query",
                json={"queryText": query},
                headers=_dev_header(tenant_id=_TENANT_A_ID),
            )
            assert response.status_code == 200, (
                f"[{case_id}] query failed: {response.status_code} {response.text}"
            )
            body = response.json()
            returned_ids = {hit["chunk"]["chunkId"] for hit in body["scoredChunks"]}
            assert returned_ids.isdisjoint(must_not_ids), (
                f"[{case_id}] A3 returned cross-tenant chunk(s): "
                f"{returned_ids & must_not_ids}"
            )
            # Defense in depth: every returned chunk belongs to tenant A.
            for hit in body["scoredChunks"]:
                assert hit["chunk"]["tenantId"] == _TENANT_A_ID, (
                    f"[{case_id}] returned chunk with foreign tenantId: {hit['chunk']}"
                )
    finally:
        app.dependency_overrides.clear()
        with contextlib.suppress(Exception):
            await store.delete_by_filter(filters=VectorFilter(tenant_id=_TENANT_A_ID))
            await store.delete_by_filter(filters=VectorFilter(tenant_id=_TENANT_B_ID))
        await store.close()
        await dispose_engine()
