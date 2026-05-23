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

## Engineering Decisions (resolved — pointer only)

Earlier drafts of this card carried open decisions for the PDF parser and the chunking algorithm. Both are now resolved; this section is retained as a pointer so implementers do not re-litigate.

### Layout-Aware PDF Parsing — resolved by ADR-0008

- Decision: two concrete parsers behind a `Parser` Protocol. `PdfplumberParser` is the first attempt for every file. `TesseractParser` (wrapping `pytesseract` with `tesseract-ocr-grc` and `tesseract-ocr-ell` language packs) is used when `avg_chars_per_page < 50` on the digital path.
- Dispatch is owned by `app/domain/services/chunking_service.py`, not the parsers themselves.
- The `unstructured.io` and `pymupdf` (AGPL) options previously listed here were both rejected; rationale is recorded in ADR-0008.
- Required reads:
  - [`docs/adr/0008-pdf-parser-strategy.md`](../../adr/0008-pdf-parser-strategy.md) — status: Accepted.
  - [`docs/contracts/parser-interface.md`](../../contracts/parser-interface.md) — `Parser` Protocol and `ParsedBlock` shape.

### Chunking Strategy — resolved by ADR-0009

- Decision: heading-boundary hierarchical chunking with sentence-boundary fallback. Soft cap 800–1200 tokens, hard cap 1500 tokens, counted via `tiktoken.get_encoding("cl100k_base")`.
- Required chunk metadata: `sectionPath`, `pageStart`, `pageEnd`, `parentChunkId` (camelCase wire / snake_case DB per `code-gen-guide.md`).
- Heading detection: typography rule on the digital path; ALL-CAPS fallback on the OCR path. Footnotes are folded into the nearest preceding paragraph chunk, not emitted as standalone chunks.
- The "400-token soft cap with 100-token overlap" fallback previously suggested here was superseded by ADR-0009's 800–1200 / 1500 caps; do not use the earlier numbers.
- Required reads:
  - [`docs/adr/0009-chunking-strategy.md`](../../adr/0009-chunking-strategy.md) — status: Accepted.
  - [`docs/contracts/chunking-contract.md`](../../contracts/chunking-contract.md) — status: Canonical; full algorithm, invariants, and observability events.

### Tunable thresholds

Implementers MAY tune heuristic constants (50-char OCR dispatch threshold; 1.3× font-size multiplier; 120-char heading length cap; 8-word ALL-CAPS heading cap; the 800/1200/1500 token caps) per the tuning rules in ADR-0008, ADR-0009, and `chunking-contract.md`, provided new values are recorded in `approved-decisions-register.md` as a follow-up row to D-PDF-001 / D-CHK-001. Tuning does not require an ADR amendment.
