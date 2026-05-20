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

## Resolved Engineering Decisions (read these before implementation)

Both decisions previously open on this card are now locked. The pointers below are the authoritative source — do not re-derive the choice from this card.

### PDF Parsing

- Decision: `pdfplumber` primary, `pytesseract` (Tesseract OCR with `grc` + `ell` language packs) fallback. Dispatch heuristic owned by the chunking service, not the parsers.
- Authoritative source: **ADR-0008 (`docs/adr/0008-pdf-parser-strategy.md`)** + the **`Parser` Protocol in `docs/contracts/parser-interface.md`**. The `ParsedBlock` shape — including `font_size`, `bold`, `bbox`, `block_type`, `page_num` — is the input to the chunking service.
- Implementation note: T-001 ships `pdfplumber_parser.py`, `tesseract_parser.py`, and a `vision_parser.py` stub (Phase 2) as `NotImplementedError` bodies whose class shapes match the Protocol; T-002 fills in `pdfplumber_parser.py` and `tesseract_parser.py`.

### Chunking Strategy

- Decision: hierarchical chunking by heading boundary with a sentence-boundary fallback; soft cap 800–1200 tokens (`cl100k_base`), hard cap 1500. Every chunk carries `sectionPath`, `pageStart`, `pageEnd`, and `parentChunkId`.
- Authoritative source: **ADR-0009 (`docs/adr/0009-chunking-strategy.md`)** + the **algorithm spec in `docs/contracts/chunking-contract.md`**. Heading detection rules and the ALL-CAPS fallback for OCR-derived blocks are specified there.
- Phase 2 hook: `parentChunkId` is the join key for the graph traversal layer described in ADR-0006. Setting it correctly during the sentence-boundary split is a one-line change with multi-quarter consequences if missed.
