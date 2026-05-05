# T-002: Tenant Data Model And Ingestion

## Goal

Implement tenant-aware persistence and manual corpus ingestion with approval workflow foundations.

## Required Reads

- [`AGENTS.md`](../../../AGENTS.md) — "Tenant And Role Rules" + "Required Tests" sections.
- [`docs/contracts/db-schema.md`](../../contracts/db-schema.md) — full DDL for `tenants`, `users`, `sources`, `chunks`, `ingest_jobs`; cross-table invariants.
- [`docs/contracts/auth-context.md`](../../contracts/auth-context.md) — Principal shape; how `tenant_id` is resolved (never from request body).
- [`docs/contracts/provider-interface.md`](../../contracts/provider-interface.md) — `embed_texts` Protocol method (the only allowed embedding entry-point for ingestion workers).
- [`docs/contracts/observability.md`](../../contracts/observability.md) — `ingest.*` and `worker.embedding.*` event shapes.
- [`docs/schemas/source.schema.json`](../../schemas/source.schema.json), [`chunk.schema.json`](../../schemas/chunk.schema.json), [`ingest-job.schema.json`](../../schemas/ingest-job.schema.json), [`tenant.schema.json`](../../schemas/tenant.schema.json) — pydantic targets.
- [`docs/api/openapi.yaml`](../../api/openapi.yaml) — `/ingest`, `/ingest/jobs/{jobId}`, `/corpus`, `/corpus/{chunkId}` operations and their `x-required-scope` values.
- [`docs/adr/0001-closed-corpus-contract.md`](../../adr/0001-closed-corpus-contract.md), [`0003-multi-tenant-day-one.md`](../../adr/0003-multi-tenant-day-one.md), [`0006-pag-rag-lineage-architecture.md`](../../adr/0006-pag-rag-lineage-architecture.md).
- [`docs/contracts/approved-decisions-register.md`](../../contracts/approved-decisions-register.md) row J (source_hash format) and rows 3, 4, 7 (attestation, flagged embeddings, starter corpus).
- Fixtures: [`tests/fixtures/corpus/tiny_approved_corpus.json`](../../../tests/fixtures/corpus/tiny_approved_corpus.json) and [`tiny_other_tenant_corpus.json`](../../../tests/fixtures/corpus/tiny_other_tenant_corpus.json) — both must load without leaking across tenants.

## Files In Scope

- PostgreSQL models and Alembic migrations
- ingestion service
- chunking service
- source and chunk repositories
- corpus fixture tests

## Acceptance Tests

- Tenant-scoped tables include `tenant_id`.
- Uploaded sources receive `source_hash`.
- Chunks receive `chunk_hash`, `approved = false`, and corpus version metadata.
- Approved chunks can be listed by tenant.
- Rejected or unapproved chunks are excluded from retrieval fixtures.

## Forbidden Scope

- Do not implement YouTube ingestion.
- Do not implement graph-driven retrieval.
- Do not let any query omit tenant context.
- Do not auto-approve uploaded chunks.

## Acceptance — Wave 4 Additions

- **F-12:** `tests/integration/test_corpus.py::test_chunk_approval_requires_source_approval` and `test_source_un_approval_cascades_or_rejects` PASS — encoding the chunks⇒sources approval invariant from db-schema.md cross-table invariant #1.
- **F-23 E2E:** `tests/integration/test_t002_e2e.py::test_ingest_then_query_round_trip` PASSES — uploads a small fixture, runs ingestion, confirms approved chunks appear in retrieval and unapproved chunks do not.

---

## ⚠ Open Engineering Decisions (resolve before implementation begins)

### Layout-Aware PDF Parsing

Standard page-order PDF extraction misreads footnotes, scriptural citations, chapter headings, and marginalia common in Patristic PDF sources. The ingestion pipeline must use layout-aware parsing.

Evaluate in this order before committing to a library:

1. `unstructured.io` — best for mixed document types (PDF, DOCX, HTML); handles multi-column and footnote detection
2. `pdfplumber` — good for structured PDFs with consistent layout; reliable page/table extraction
3. `pymupdf` (block-level layout API) — fastest; suitable for clean scanned PDFs

Requirements for whichever library is chosen:

- Footnotes must be linked back to the body paragraph they annotate, not appended at page end as orphaned text.
- Scriptural citations embedded in footnotes must be preserved as chunk metadata, not discarded.
- Chapter and section headings must produce a `section_path` metadata field on each chunk (e.g., `"Book II > Chapter 4"`).
- Page number must be preserved as `page_start` / `page_end` for citation accuracy in A6.

**This decision must be made and reflected in the `chunking_service.py` contract before T-002 implementation begins.**

### Chunking Strategy

Fixed-size chunking (e.g., 512 tokens with 50-token overlap) frequently splits a theological argument mid-sentence or separates a patristic claim from the citation immediately following it. A6's 70% quote-overlap threshold will fail on incoherent fragment chunks.

Recommended approach:

- **Primary:** Semantic/hierarchical chunking by natural section boundaries (heading → paragraph → sentence fallback).
- **Fallback:** Sentence-boundary chunking with a 400-token soft cap and 100-token overlap.
- Each chunk must carry: `section_path`, `page_start`, `page_end`, and `parent_chunk_id` to support context-window expansion in Phase 2.

**This decision must be specified in `chunking_service.py` before T-002 implementation begins.**
