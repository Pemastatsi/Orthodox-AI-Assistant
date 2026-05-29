"""T-005 end-to-end acceptance: cache + persistence + privacy through POST /query.

Three scenarios cover F-23 (cache-hit minimal trace), F-18 (every served request lands
a run_trace) and the encrypted-flagged-query round-trip with PII redaction. All require
both Postgres and Redis; tests skip cleanly when either is unreachable.
"""

from __future__ import annotations

import base64
import json
import os
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from app.adapters.vector_store.base import ChunkPayload, SparseVector, VectorFilter
from app.adapters.vector_store.base import ScoredChunk as AdapterScoredChunk
from app.api.v1._deps import (
    _reset_cipher_cache,
    get_composer_provider,
    get_embedding_provider,
    get_pastoral_config,
    get_query_analyzer_provider,
    get_safety_config,
    get_sensitive_log_cipher,
    get_sparse_embedder,
    get_vector_store,
    get_verifier_provider,
)
from app.domain.models.chunk import Chunk
from app.domain.services.encryption_service import (
    KEY_BYTES,
    EncryptedBlob,
    SensitiveLogCipher,
)
from app.domain.services.safety_config import (
    load_pastoral_filters,
    load_sensitivity_keywords,
)
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.fixtures.fakes import ComposerFakeProvider, FakeStructuredProvider

pytestmark = pytest.mark.asyncio

# Repo-root-relative so the suite runs in any checkout (CI included), not only a
# /home/user/Orthodox-AI-Assistant container. Mirrors app/core/config.py's _REPO_ROOT.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SENSITIVITY_PATH = str(_REPO_ROOT / "config" / "sensitivity_keywords.yaml")
_PASTORAL_PATH = str(_REPO_ROOT / "config" / "pastoral_filters.yaml")


def _dev_header(*, tenant_id: str = "tn_test", role: str = "member") -> dict[str, str]:
    payload = {"tenantId": tenant_id, "role": role, "userId": "usr_test"}
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return {"x-dev-principal": encoded}


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


def _hit(chunk_id: str = "chunk-test-1", tenant_id: str = "tn_test") -> AdapterScoredChunk:
    chunk = Chunk(
        chunk_id=chunk_id,
        source_id=f"src-{chunk_id}",
        tenant_id=tenant_id,
        text=(
            "Saint Basil writes that prayer requires patience and steadfastness. "
            "He teaches us to ask, seek, and knock without despair."
        ),
        chunk_hash="sha256:" + "0" * 64,
        approved=True,
        visibility="member",
        embedding_model="text-embedding-3-small",
        embedding_dimension=1536,
        corpus_version="fixture",
        created_at=datetime.now(UTC),
    )
    return AdapterScoredChunk(chunk=chunk, score=0.85)


@pytest_asyncio.fixture()
async def flush_test_cache(redis_available: bool) -> AsyncIterator[None]:
    """Drop every `qcache:*` key before and after the test so cache state is isolated."""
    if not redis_available:
        pytest.skip("Redis not reachable")
    from app.api.v1._deps import get_redis
    from app.core.config import get_settings

    redis = get_redis(get_settings())
    cursor: int | None = 0
    while cursor:
        cursor, keys = await redis.scan(cursor=cursor, match="qcache:*", count=100)
        if keys:
            await redis.delete(*keys)
    yield
    cursor = 0
    while cursor:
        cursor, keys = await redis.scan(cursor=cursor, match="qcache:*", count=100)
        if keys:
            await redis.delete(*keys)


@pytest.fixture()
def cipher_env() -> Iterator[None]:
    """Provide a real cipher so flagged sensitive queries get encrypted in the DB."""
    test_key = base64.b64encode(os.urandom(KEY_BYTES)).decode("ascii")
    cipher = SensitiveLogCipher(keys={"v1": base64.b64decode(test_key)}, active_version="v1")
    app.dependency_overrides[get_sensitive_log_cipher] = lambda: cipher
    yield
    _reset_cipher_cache()
    if get_sensitive_log_cipher in app.dependency_overrides:
        del app.dependency_overrides[get_sensitive_log_cipher]


@pytest.fixture()
def pipeline_stubs(
    seed_tenant: tuple[str, str], cipher_env: None
) -> Iterator[tuple[TestClient, StubVectorStore]]:
    """Spin up the full app with stub providers + real DB + real Redis."""
    del seed_tenant
    del cipher_env

    safety_config = load_sensitivity_keywords(_SENSITIVITY_PATH)
    pastoral_config = load_pastoral_filters(_PASTORAL_PATH)
    analyzer_provider = FakeStructuredProvider()
    composer_provider = ComposerFakeProvider(
        answer="Saint Basil writes that prayer requires patience and steadfastness.",
        cited_chunk_ids=["chunk-test-1"],
    )
    store = StubVectorStore(hits=[_hit()])
    sparse = StubSparseEmbedder()

    app.dependency_overrides[get_safety_config] = lambda: safety_config
    app.dependency_overrides[get_pastoral_config] = lambda: pastoral_config
    app.dependency_overrides[get_query_analyzer_provider] = lambda: analyzer_provider
    app.dependency_overrides[get_composer_provider] = lambda: composer_provider
    app.dependency_overrides[get_verifier_provider] = lambda: None
    app.dependency_overrides[get_embedding_provider] = lambda: analyzer_provider
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_sparse_embedder] = lambda: sparse

    yield TestClient(app), store

    for key in [
        get_safety_config,
        get_pastoral_config,
        get_query_analyzer_provider,
        get_composer_provider,
        get_verifier_provider,
        get_embedding_provider,
        get_vector_store,
        get_sparse_embedder,
    ]:
        if key in app.dependency_overrides:
            del app.dependency_overrides[key]


async def _count_run_traces(tenant_id: str) -> int:
    from app.domain.repositories._base import session_scope

    async with session_scope() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM run_traces WHERE tenant_id = :t"),
            {"t": tenant_id},
        )
        return int(result.scalar_one())


async def _fetch_run_trace_by_run_id(run_id: str) -> dict:
    from app.domain.repositories._base import session_scope

    async with session_scope() as session:
        result = await session.execute(
            text("SELECT * FROM run_traces WHERE run_id = :r"),
            {"r": run_id},
        )
        row = result.mappings().one_or_none()
        return dict(row) if row else {}


async def _fetch_billing(tenant_id: str) -> tuple[int, int]:
    """Return (served_answer_count, fresh_model_run_count) for the current period."""
    from app.domain.repositories._base import session_scope

    async with session_scope() as session:
        result = await session.execute(
            text(
                """
                SELECT served_answer_count, fresh_model_run_count
                FROM billing_usage
                WHERE tenant_id = :t
                ORDER BY period_start DESC
                LIMIT 1
                """
            ),
            {"t": tenant_id},
        )
        row = result.one_or_none()
        return (int(row[0]), int(row[1])) if row else (0, 0)


@pytest.mark.asyncio
async def test_cache_hit_persists_run_trace_with_new_run_id(  # noqa: N802
    pipeline_stubs: tuple[TestClient, StubVectorStore], flush_test_cache: None
) -> None:
    """F-23/F-18: second identical request must hit the cache, mint a new runId, and
    persist a minimal run_traces row with cache_hit=true."""
    client, _ = pipeline_stubs

    first = client.post(
        "/api/v1/query",
        json={"queryText": "What do the Fathers teach about prayer?"},
        headers=_dev_header(),
    )
    assert first.status_code == 200, first.text
    first_body = first.json()
    first_run_id = first_body["runId"]

    # Wait for any async DB writes to settle by re-reading.
    served_1, fresh_1 = await _fetch_billing("tn_test")
    assert served_1 == 1 and fresh_1 == 1
    assert await _count_run_traces("tn_test") == 1
    first_trace = await _fetch_run_trace_by_run_id(first_run_id)
    assert first_trace["cache_hit"] is False

    second = client.post(
        "/api/v1/query",
        json={"queryText": "What do the Fathers teach about prayer?"},
        headers=_dev_header(),
    )
    assert second.status_code == 200, second.text
    second_body = second.json()
    second_run_id = second_body["runId"]

    assert second_run_id != first_run_id, "cache hit must mint a fresh runId"
    assert second_body["answer"] == first_body["answer"]
    assert second_body["servedFromCache"] is True

    served_2, fresh_2 = await _fetch_billing("tn_test")
    assert served_2 == 2, "cache hit must increment served_answer_count"
    assert fresh_2 == 1, "cache hit must NOT increment fresh_model_run_count"

    assert await _count_run_traces("tn_test") == 2
    second_trace = await _fetch_run_trace_by_run_id(second_run_id)
    assert second_trace["cache_hit"] is True
    assert second_trace["final_handling"] in {"answer", "answer_with_disclaimer"}


@pytest.mark.asyncio
async def test_hard_safety_query_still_persists_run_trace(
    pipeline_stubs: tuple[TestClient, StubVectorStore], flush_test_cache: None
) -> None:
    """F-18: hard-safety bypass must still mint a runId and write a run_traces row."""
    client, store = pipeline_stubs

    response = client.post(
        "/api/v1/query",
        json={"queryText": "I want to kill myself"},
        headers=_dev_header(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["handling"] == "block_with_redirect"
    run_id = body["runId"]

    trace = await _fetch_run_trace_by_run_id(run_id)
    assert trace, "F-18: hard-safety request must persist a run_traces row"
    assert trace["cache_hit"] is False
    assert trace["final_handling"] == "block_with_redirect"

    # A self_harm query must also be encrypted in raw_sensitive_logs.
    from app.domain.repositories._base import session_scope

    async with session_scope() as session:
        result = await session.execute(
            text(
                "SELECT raw_sensitive_log_id, flag_reason FROM flagged_queries "
                "WHERE tenant_id = 'tn_test' AND run_id = :r"
            ),
            {"r": run_id},
        )
        row = result.one_or_none()
    assert row is not None, "hard-safety query must create a flagged_queries row"
    assert row[1] == "hard_safety_trigger"
    assert row[0] is not None, "self-harm risk_flag must capture an encrypted raw log"

    # The pipeline never touched the cache: vector store was never queried.
    assert store.seen_filter is None


@pytest.mark.asyncio
async def test_flagged_query_redacts_pii_and_encrypts_raw(
    pipeline_stubs: tuple[TestClient, StubVectorStore], flush_test_cache: None
) -> None:
    """Hard-safety query containing PII (email, phone) gets stored redacted in
    flagged_queries.query_text_redacted while the original is encrypted at rest."""
    client, _ = pipeline_stubs

    raw = "I want to kill myself, my email is alice@example.com call +1-415-555-9876"
    response = client.post(
        "/api/v1/query", json={"queryText": raw}, headers=_dev_header()
    )
    assert response.status_code == 200
    run_id = response.json()["runId"]

    from app.domain.repositories._base import session_scope

    async with session_scope() as session:
        result = await session.execute(
            text(
                """
                SELECT fq.query_text_redacted, fq.raw_sensitive_log_id,
                       rsl.ciphertext, rsl.nonce, rsl.key_version, rsl.expires_at
                FROM flagged_queries fq
                LEFT JOIN raw_sensitive_logs rsl
                       ON fq.raw_sensitive_log_id = rsl.log_id
                WHERE fq.tenant_id = 'tn_test' AND fq.run_id = :r
                """
            ),
            {"r": run_id},
        )
        row = result.one_or_none()

    assert row is not None
    redacted, raw_log_id, ciphertext, nonce, key_version, expires_at = row
    assert "alice@example.com" not in redacted
    assert "[email]" in redacted
    assert "415" not in redacted
    assert "[phone]" in redacted

    assert raw_log_id is not None
    assert key_version == "v1"
    assert len(bytes(nonce)) == 12

    # The encrypted blob decrypts to the original text under the override cipher.
    cipher = app.dependency_overrides[get_sensitive_log_cipher]()
    plaintext = cipher.decrypt(
        EncryptedBlob(
            nonce=bytes(nonce),
            ciphertext=bytes(ciphertext),
            key_version=key_version,
        )
    )
    assert plaintext == raw

    # expires_at is in the future and roughly +30 days.
    from datetime import timedelta

    now = datetime.now(UTC)
    assert expires_at > now
    assert expires_at < now + timedelta(days=31)
