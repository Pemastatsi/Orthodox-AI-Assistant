# ADR 0010: VectorStore Interface Pattern

Date: 2026-05-11
Status: Accepted

## Context

ADR-0006 (PAG-RAG lineage architecture) selects Qdrant as the Phase 1 vector store. That decision is sound and is not revisited here. What ADR-0006 does *not* specify is the seam between application code and the vector store — and during planning it became clear that the codebase had begun to import the Qdrant client directly inside agent and service code (`A3`, `chunking_service`, `flagged_embedding`). That direct coupling has three concrete costs:

1. **It pre-commits Phase 2.** When the question of "should we move to pgvector in Phase 2?" comes up — and at the size of the corpus and the operational simplicity story, it will — every direct Qdrant import is a place that has to change. The scope of the change becomes a refactor instead of an adapter swap.
2. **It pre-commits the test story.** Integration tests either spin up Qdrant in CI (slow, flaky, cross-platform-painful) or each test mocks the Qdrant client surface (fragile, easy to drift from real behavior). A Protocol seam admits a fake implementation that the integration tests share, the way `LLMProvider` tests share `FakeAnthropicAdapter`.
3. **It muddies the tenant-isolation invariant.** ADR-0003 (multi-tenant day one) requires `WHERE tenant_id = :tenant_id` on every read and write of tenant data. Spread across many call sites, this invariant is easy to drop. Concentrating it inside a single adapter is the only way to make it auditable.

The pattern already exists in this codebase for LLMs: `LLMProvider` is the Protocol; `AnthropicAdapter` and `OpenAIAdapter` implement it; orchestrator code never imports `anthropic` or `openai` directly (see `provider-interface.md` and `code-gen-guide.md` Forbidden Patterns). Doing the same thing for the vector store is a small, well-understood move that pays back immediately in test ergonomics and locks down the tenant filter at a single chokepoint.

## Decision

All agent code, orchestrator code, ingestion workers, and services access the vector store **only** through a `VectorStore` Protocol, defined in `docs/contracts/vector-store-interface.md` and modeled on the `LLMProvider` Protocol in `docs/contracts/provider-interface.md`.

Phase 1 ships one concrete implementation: `QdrantStore`. A `PgvectorStore` can be added in Phase 2 as a drop-in replacement without touching any agent, orchestrator, or service code.

**This ADR does not amend ADR-0006.** Qdrant remains the Phase 1 vector store. The change is purely about how application code reaches it.

### Protocol surface (full spec lives in `vector-store-interface.md`)

```python
class VectorStore(Protocol):
    async def upsert(self, payloads: list[ChunkPayload]) -> None: ...
    async def search(
        self, *, query_vector: list[float], filters: VectorFilter, top_k: int
    ) -> list[ScoredChunk]: ...
    async def delete_by_filter(self, *, filters: VectorFilter) -> int: ...
```

The minimal surface is intentional. Phase 1 has only three vector-store call sites: ingestion's `upsert`, A3's `search`, and corpus-management's `delete_by_filter`. Adding a method to the Protocol later is cheap; removing one is expensive.

### Tenant-isolation invariant

`VectorFilter.tenant_id` is **required, not optional**. Every implementation of `VectorStore.search` and `VectorStore.delete_by_filter` MUST raise `ValueError` if `filters.tenant_id` is missing or empty. This mirrors the DB-layer tenant invariant from ADR-0003 — and it means that "did we forget the tenant filter on this call?" is a question that fails fast rather than silently returning another tenant's data.

The `chunks_{tenant_id}` collection-per-tenant pattern vs. a single shared collection with a `tenant_id` payload filter is left to the T-002 implementer; the Protocol accommodates either. The choice is recorded in `approved-decisions-register.md` once made.

### Forbidden patterns

- Importing `qdrant_client` outside `app/adapters/vector_store/qdrant_store.py`.
- Calling Qdrant via raw HTTP from anywhere in the application code.
- Constructing a `VectorFilter` without a `tenant_id`.

These are enforced by the same import-rule lint that `code-gen-guide.md` already runs against `anthropic`/`openai` direct imports.

## Why not amend ADR-0006 to switch to pgvector now

A reasonable counter-argument: at Phase 1 scale (one tenant, low thousands of chunks), pgvector inside the existing Postgres database would eliminate a backing service, eliminate a backup target, and eliminate the class of bugs where a chunk is approved in Postgres but stale in Qdrant. That argument is real, and it might win in Phase 2. But changing the vector store mid-build would:

- Invalidate ADR-0006 and force a fresh ADR.
- Invalidate the `embedding_dimension` and Qdrant-payload references in `db-schema.md` and `chunk.schema.json`.
- Restart the embedding-model-route certification clock under `safety_suite_runs`.
- Add a multi-week schema-migration step in the middle of build.

The cost of the change is high; the cost of preserving the seam is low. Take the seam now, defer the switch.

## When to reconsider

Promote a `PgvectorStore` to Phase 1 default if any of the following becomes true after T-005 completes:

- Operational cost of running Qdrant alongside Postgres exceeds the marginal cost of pgvector ops by a meaningful factor.
- Approval-status sync lag between Postgres `chunks.approved` and Qdrant payload causes a reproducible correctness bug.
- A Phase 2 multi-region requirement makes the dual-backing-store backup story untenable.

In any of those cases, write a new ADR that amends both this ADR and ADR-0006 together. The Protocol means the implementation change is bounded; the ADR pair preserves the audit trail.

## Consequences

- **One new module:** `app/adapters/vector_store/` with `base.py` (Protocol), `qdrant_store.py` (concrete), and `__init__.py` (factory). Mirrors `app/adapters/providers/`.
- **One file moves:** the existing `app/adapters/qdrant_adapter.py` (referenced in `scaffold-contract.md`) moves into the new module. Scaffold contract amended in Step 9 to reflect this.
- **One existing schema gains a payload field reference:** `chunk.schema.json` is the source of truth for chunk shape; `vector-store-interface.md` defines `ChunkPayload` as a strict subset of `Chunk` plus the few fields the vector store needs at search time. The Protocol is the only place that mirrors the schema.
- **One new schema:** `docs/schemas/scored-chunk.schema.json`, defined as `Chunk` plus a `score` field (per planning recommendation #1 — composition, not duplication).
- **Test ergonomics improve.** Integration tests under `tests/integration/` use an in-memory `FakeVectorStore` that implements the Protocol; Qdrant is required only for the dedicated `tests/integration/qdrant_smoke.py` test.

## Alternatives Considered

- **Direct Qdrant client imports everywhere.** Current trajectory; rejected for the reasons in §Context.
- **A thicker repository abstraction** that wraps both Postgres and Qdrant behind a single "chunk repository" Protocol. Tempting because the two stores share the chunk concept, but conflates two operational concerns (transactional metadata vs. vector search) and produces a Protocol with twice the surface area. Rejected as premature.
- **A pluggable provider registry** like `LLMProvider`'s route registry. Rejected as overkill — there is exactly one active vector store at a time; a registry pattern would just be a one-entry dict.

## Tests

- `app/adapters/vector_store/base.py` defines `VectorStore`, `ChunkPayload`, `VectorFilter`, and `ScoredChunk` exactly as specified in `vector-store-interface.md`.
- `VectorStore.search(filters=VectorFilter(tenant_id=""))` raises `ValueError`.
- `VectorStore.search(filters=VectorFilter())` (no `tenant_id` at all) is a static-type error AND raises `ValueError` at runtime.
- Import-rule lint: any import of `qdrant_client` outside `app/adapters/vector_store/` fails CI.
- An A3 retrieval test using `FakeVectorStore` returns deterministic `ScoredChunk` results with the right `score` ordering.
- A `QdrantStore` smoke test (in `tests/integration/qdrant_smoke.py`) round-trips an `upsert` → `search` → `delete_by_filter` cycle against a real Qdrant instance.

## References

- ADR-0003 (multi-tenant day one) — the tenant-isolation invariant.
- ADR-0006 (PAG-RAG lineage architecture) — selects Qdrant; not amended by this ADR.
- `docs/contracts/provider-interface.md` — the `LLMProvider` Protocol this ADR mirrors.
- `docs/contracts/vector-store-interface.md` — full Protocol specification.
- `docs/contracts/code-gen-guide.md` — the layering and forbidden-import rules this ADR extends to Qdrant.
- `docs/contracts/approved-decisions-register.md` row D-VS-001.
