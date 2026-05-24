"""End-to-end test for T-002 (tenant data ingestion → tenant-isolated retrieval).

Audit finding: A-14 (rewritten under T-002 per the founder's decision to test against
`VectorStore.search` rather than the `POST /api/v1/query` endpoint that lands in T-003).

Round-trip exercised:
  1. Drive the ingestion pipeline (parser → chunker → fake embedder → repository →
     `QdrantStore.upsert`) for tenant A using `process_ingestion`.
  2. Seed tenant B's pre-baked corpus via the fixture loader so we have something to
     leak-detect against.
  3. Approve the freshly ingested tenant-A chunks through `ChunkRepository.mark_approved`
     (which cascade-approves the parent source per db-schema.md cross-table invariant #3).
  4. Call `QdrantStore.search` with `tenant_id=<tenant A>` → expect at least one of the
     ingested chunks to come back.
  5. Same call with `tenant_id=<tenant B>` → tenant A's chunks MUST NOT appear.

T-003 will add a separate round-trip that exercises the real `/api/v1/query` pipeline.
"""

from __future__ import annotations

import pytest

pytest.importorskip("app", reason="awaits T-001 backend scaffold")

import ulid  # noqa: E402

from app.adapters.providers.openai_provider import embedding_dimension_for  # noqa: E402
from app.adapters.vector_store.base import VectorFilter  # noqa: E402
from app.adapters.vector_store.qdrant_store import QdrantStore  # noqa: E402
from app.domain.repositories._base import get_sessionmaker  # noqa: E402
from app.domain.repositories.chunk_repository import ChunkRepository  # noqa: E402
from app.domain.repositories.ingest_job_repository import (  # noqa: E402
    CreateIngestJobParams,
    IngestJobRepository,
)
from app.domain.repositories.source_repository import (  # noqa: E402
    CreateSourceParams,
    SourceRepository,
    compute_source_hash,
)
from app.domain.services.ingestion_service import (  # noqa: E402
    IngestionContext,
    process_ingestion,
)
from backend.tests.fixtures.corpus_loader import (  # noqa: E402
    TINY_OTHER,
    load_corpus_fixture,
)
from backend.tests.fixtures.fakes import (  # noqa: E402
    FakeEmbeddingProvider,
    FakeParser,
    deterministic_embedding,
)

pytestmark = pytest.mark.asyncio


_TENANT_A = "tn_orthodoxethos"
_FAKE_PDF = (
    b"# On Prayer\n"
    b"\n"
    b"This is the first paragraph teaching about prayer for the Fathers.\n"
    b"\n"
    b"Prayer is a unique gift of God to the saints and ascetics of the Church.\n"
    b"\n"
    b"# A Second Section\n"
    b"\n"
    b"Body of the second section discussing the importance of constant attention.\n"
)


async def test_ingest_then_search_round_trip(
    postgres_available,  # noqa: ARG001
    qdrant_available,    # noqa: ARG001
    clean_tables,        # noqa: ARG001
) -> None:
    sm = get_sessionmaker()

    # --- Seed tenant A (target of ingestion) and tenant B (leak-detect partner) ----
    async with sm() as session:
        from sqlalchemy import text as sql_text

        for tid, org in [
            (_TENANT_A, "clerk_a"),
        ]:
            await session.execute(
                sql_text(
                    "INSERT INTO tenants (tenant_id, name, clerk_org_id, status, data_region) "
                    "VALUES (:t, :t, :o, 'active', 'us')"
                ),
                {"t": tid, "o": org},
            )
            await session.execute(
                sql_text(
                    "INSERT INTO users (user_id, clerk_user_id, tenant_id, role, status) "
                    "VALUES (:u, :ck, :t, 'content_manager', 'active')"
                ),
                {"u": f"usr_{tid}", "ck": f"clerk_{tid}", "t": tid},
            )
        await session.commit()

    store = QdrantStore(embedding_dimension=embedding_dimension_for("text-embedding-3-small"))
    try:
        # --- Tenant B comes from the pre-baked fixture ------------------------------
        loaded_b = await load_corpus_fixture(fixture_path=TINY_OTHER, vector_store=store)

        # --- Tenant A: drive the real pipeline with the fake parser/embedder --------
        source_hash = compute_source_hash(_FAKE_PDF)
        async with sm() as session:
            src = await SourceRepository(session).create(
                CreateSourceParams(
                    tenant_id=_TENANT_A,
                    title="Round-trip Source",
                    source_type="pdf",
                    extraction_method="fake-pdfplumber@1",
                    corpus_version="v_test",
                    source_hash=source_hash,
                )
            )
            job = await IngestJobRepository(session).create(
                CreateIngestJobParams(
                    tenant_id=_TENANT_A,
                    user_id=f"usr_{_TENANT_A}",
                    source_id=src.source_id,
                )
            )
            await session.commit()

        provider = FakeEmbeddingProvider(dimension=1536)
        ctx = IngestionContext(
            job_id=job.job_id,
            tenant_id=_TENANT_A,
            source_id=src.source_id,
            file_bytes=_FAKE_PDF,
            mime_type="application/pdf",
            embedding_model="text-embedding-3-small",
            corpus_version="v_test",
            embedding_dimension=1536,
            run_id=f"run_{ulid.new()!s}",
        )
        result = await process_ingestion(
            ctx,
            embedding_provider=provider,
            vector_store=store,
            sparse_embedder=None,
            primary_parser=FakeParser(),
            fallback_parser=FakeParser(name="fake-tesseract"),
        )
        assert result.chunk_ids, "ingestion produced no chunks"

        # --- Verify the job landed in awaiting_review -------------------------------
        async with sm() as session:
            refreshed = await IngestJobRepository(session).get(
                tenant_id=_TENANT_A, job_id=job.job_id
            )
        assert refreshed is not None
        assert refreshed.status == "awaiting_review"

        # --- Approve the chunks (cascade-approves the source) -----------------------
        async with sm() as session:
            repo = ChunkRepository(session)
            for chunk_id in result.chunk_ids:
                await repo.mark_approved(
                    tenant_id=_TENANT_A,
                    chunk_id=chunk_id,
                    approved_by_user_id=f"usr_{_TENANT_A}",
                    approval_note="approved by test",
                )
            await session.commit()

        # --- Re-index the now-approved chunks via direct upsert ---------------------
        # (T-003 will move this into the approval handler; for T-002 we keep it explicit.)
        async with sm() as session:
            chunks, _ = await ChunkRepository(session).list_by_tenant(
                tenant_id=_TENANT_A, approved=True, source_id=src.source_id
            )
        from app.adapters.vector_store.base import ChunkPayload

        await store.upsert(
            payloads=[
                ChunkPayload(
                    chunk_id=c.chunk_id,
                    tenant_id=c.tenant_id,
                    source_id=c.source_id,
                    source_hash=source_hash,
                    chunk_hash=c.chunk_hash,
                    text=c.text,
                    section_path=c.section_path,
                    page_start=c.page_start,
                    page_end=c.page_end,
                    parent_chunk_id=c.parent_chunk_id,
                    approved=True,
                    visibility=c.visibility,
                    embedding_model=c.embedding_model,
                    embedding_dimension=c.embedding_dimension,
                    corpus_version=c.corpus_version,
                    embedding=deterministic_embedding(c.text, 1536),
                )
                for c in chunks
            ]
        )

        # --- Tenant-A search returns at least one of the ingested chunks ------------
        query_vec = deterministic_embedding(chunks[0].text, 1536)
        results_a = await store.search(
            query_vector=query_vec,
            sparse_query=None,
            filters=VectorFilter(tenant_id=_TENANT_A, approved=True),
            top_k=5,
        )
        returned_a = {r.chunk.chunk_id for r in results_a}
        assert returned_a, "tenant A search returned no hits"
        assert returned_a & {c.chunk_id for c in chunks}, (
            "tenant A search did not include any freshly ingested chunk"
        )

        # --- Tenant-B search must NOT include any tenant-A chunk --------------------
        results_b = await store.search(
            query_vector=query_vec,
            sparse_query=None,
            filters=VectorFilter(tenant_id=loaded_b.tenant_id, approved=True),
            top_k=5,
        )
        returned_b = {r.chunk.chunk_id for r in results_b}
        assert not (returned_b & {c.chunk_id for c in chunks}), (
            "cross-tenant leak: tenant A chunk appeared in tenant B search results"
        )
    finally:
        try:
            await store.delete_by_filter(filters=VectorFilter(tenant_id=_TENANT_A))
            await store.delete_by_filter(filters=VectorFilter(tenant_id=loaded_b.tenant_id))
        except Exception:
            pass
        await store.close()
