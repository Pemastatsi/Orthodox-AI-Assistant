"""End-to-end integration test stub for T-002 (tenant data ingestion).

Audit finding: A-14
Context citations:
  - docs/task_cards/phase1/T-002-tenant-data-ingestion.md (Acceptance Tests
    references this exact test path).
  - docs/contracts/db-schema.md sources/chunks tables and cross-table invariants.
  - docs/contracts/phase1-implementation-contract.md "Data Contracts".

Skipped until T-001 (backend scaffold) and T-002 (ingestion pipeline) land.
The skip preserves CI test collection so the missing path no longer counts as
a referenced-but-undefined test, while the assertions remain a contract for
the implementer to satisfy.
"""
import pytest

pytest.importorskip("app", reason="awaits T-001 backend scaffold")


def test_ingest_then_query_round_trip():
    """A document uploaded through the ingestion pipeline becomes retrievable
    by the query path within a single tenant scope.

    Steps the implementation MUST satisfy when T-002 lands:
      1. POST a small approved document via the ingestion endpoint as
         tenant=tn_orthodoxethos.
      2. Wait for ingest job completion (sources.approved=true,
         chunks.approved=true, embeddings indexed in Qdrant).
      3. POST a query via /api/v1/query that should match the ingested chunk.
      4. Assert the verified response cites a chunk whose chunkHash matches
         one of the freshly ingested chunks.
      5. Assert the ingested chunk does NOT appear when querying as a
         different tenant (uses tests/fixtures/corpus/tiny_other_tenant_corpus.json
         for the second tenant).
    """
    pytest.skip(
        "pending T-002 implementation: ingest_then_query_round_trip "
        "requires the ingestion pipeline and /api/v1/query handler"
    )
