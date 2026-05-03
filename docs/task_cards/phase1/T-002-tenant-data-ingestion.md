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
