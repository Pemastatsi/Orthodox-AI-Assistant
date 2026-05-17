# Vector Store Interface

Status: Canonical
Date: 2026-05-11

This document defines the abstract interface every vector-store adapter implements. Implemented in `app/adapters/vector_store/base.py`. The Phase 1 concrete adapter is `qdrant_store.py`. A Phase 2 `pgvector_store.py` can be added as a drop-in replacement without touching any agent, orchestrator, or service code. The decision to introduce this Protocol seam without amending ADR-0006 is recorded in ADR-0010.

## Goals

- A single typed surface so no agent or service code imports `qdrant_client` directly.
- A hard, runtime-enforced tenant-isolation invariant: every `search` and `delete_by_filter` call requires `tenantId`.
- Symmetry with `LLMProvider` (`provider-interface.md`) so the test ergonomics, error mapping, and forbidden-import rules transfer 1:1.
- Minimal surface area — only the three methods Phase 1 actually uses.

## Protocol

```python
from typing import Protocol, runtime_checkable
from dataclasses import dataclass
from app.domain.models import ChunkPayload, VectorFilter, ScoredChunk, SparseVector

@runtime_checkable
class VectorStore(Protocol):
    name: str               # 'qdrant' | 'pgvector'

    async def upsert(self, *, payloads: list[ChunkPayload]) -> None: ...

    async def search(
        self,
        *,
        query_vector: list[float],
        sparse_query: SparseVector | None = None,
        filters: VectorFilter,
        top_k: int,
    ) -> list[ScoredChunk]: ...

    async def delete_by_filter(
        self,
        *,
        filters: VectorFilter,
    ) -> int: ...                       # returns count deleted

    @property
    def embedding_dimension(self) -> int: ...
                                         # the dimension this store was initialized with;
                                         # must match every payload's embedding length
```

`sparse_query` is `None` for dense-only retrieval (the original behavior). When passed, the adapter issues a single Qdrant `Query` API request with both dense and sparse prefetch branches, fused server-side via Reciprocal Rank Fusion (RRF). The tenant filter applies to both branches identically. See ADR-0011 for the architectural rationale and ADR-0012 for the complementary reranker step that consumes the hybrid result.

`embedding_dimension` is read at startup to validate that the configured vector store matches the active embedding `ModelRoute` (per ADR-0006). A mismatch fails the startup boot check.

## `ChunkPayload`

What gets stored alongside the vector. This is a strict subset of `Chunk` (per `chunk.schema.json`) plus the embedding itself. Defined in `app/domain/models.py`:

```python
@dataclass(frozen=True)
class SparseVector:
    indices: list[int]        # term-id positions in the sparse index
    values: list[float]       # corresponding weights

@dataclass(frozen=True)
class ChunkPayload:
    chunk_id: str
    tenant_id: str
    source_id: str
    source_hash: str          # 'sha256:<hex>'
    text: str
    section_path: list[str]   # may be empty
    page_start: int | None
    page_end: int | None
    parent_chunk_id: str | None
    approved: bool
    visibility: str           # 'member' | 'scholar' | 'admin_only' | 'suppressed'
    embedding_model: str      # certified ModelRoute.routeId for purpose='embedding'
    embedding: list[float]    # length == VectorStore.embedding_dimension
    sparse_embedding: SparseVector | None  # BM25-style sparse vector; None for legacy chunks pre-ADR-0011
```

`ChunkPayload` mirrors the fields the vector store needs to (a) filter on (`tenant_id`, `approved`, `visibility`), (b) return for citation display (`source_id`, `source_hash`, `section_path`, `page_start`, `page_end`), and (c) reconstruct as a `ScoredChunk` (`text`, `chunk_id`, `parent_chunk_id`). The exhaustive `Chunk` shape (categories, language, father, work, reviewNote, createdAt) is NOT stored in the vector payload; it stays in Postgres and is joined back when A4 builds the evidence packet.

The fields-stored-in-payload list is intentionally minimal: every field carried in the vector store is a field that must be invalidated and re-upserted on every chunk edit, and the cost compounds at corpus scale.

## `VectorFilter`

```python
@dataclass(frozen=True)
class VectorFilter:
    tenant_id: str            # REQUIRED — see Tenant Isolation Invariant below
    approved: bool | None = None
    visibility: str | None = None       # if set, exact match
    source_id: str | None = None        # for delete_by_filter only; ignored by search
```

A non-`None` field means "filter to rows where this field equals this value." A `None` field means "no filter on this field."

## `ScoredChunk`

```python
@dataclass(frozen=True)
class ScoredChunk:
    chunk: Chunk              # the full chunk shape per chunk.schema.json
    score: float              # cosine similarity, range [0.0, 1.0]
```

`ScoredChunk` is intentionally a composition of `Chunk` plus `score`, not a re-listing of chunk fields. This is the planning-recommendation #1 design: one source of truth for chunk shape, two consumers. The on-disk JSON form is `docs/schemas/scored-chunk.schema.json`, which `$ref`s `chunk.schema.json`.

The `chunk` field is populated by the adapter from the vector payload (the fields stored in `ChunkPayload`) plus the fields joined from Postgres (`father`, `work`, `language`, `categories`, `createdAt`, etc.). The join happens inside the adapter's `search` implementation so callers receive a fully-hydrated `Chunk` shape without a second roundtrip.

## Tenant Isolation Invariant

This is the contract's reason for existence.

- `VectorFilter.tenant_id` is a required dataclass field — constructing `VectorFilter()` without it is a static type error.
- `VectorStore.search` and `VectorStore.delete_by_filter` MUST raise `ValueError("tenant_id required")` when `filters.tenant_id` is empty string, whitespace-only, or otherwise falsy. Implementations MUST check this BEFORE issuing any I/O to the underlying store.
- `VectorStore.upsert` validates that every `ChunkPayload.tenant_id` is non-empty; mixed-tenant batches are NOT permitted (raise `ValueError("mixed-tenant upsert batch")`).

These checks are tested directly in `tests/unit/test_vector_store_isolation.py`. The Phase 1 implementation will surface a `TenantIsolationViolation` log event (per `observability.md`) for any rejected call — these should be rare in production and indicate a caller bug.

## Concrete Implementations

### `QdrantStore` (Phase 1)

- Wraps the `qdrant-client` Python SDK.
- The choice between **one collection per tenant** (`chunks_{tenant_id}`) and **one shared collection** with a tenant payload filter is left to T-002. The Protocol accommodates either; the chosen pattern is recorded in `approved-decisions-register.md` as a follow-up to D-VS-001 once measured.
- Issues a single Qdrant `points/search` request per `search` call with payload filters expanded from `VectorFilter`.
- Hydrates `ScoredChunk.chunk` by joining the Postgres `chunks` table on `chunk_id` (the join is a single `SELECT ... WHERE chunk_id = ANY(:ids)` query, batched once per `search` call).

### `PgvectorStore` (Phase 2)

- Not implemented in Phase 1.
- The Protocol surface is unchanged; the implementation issues a single SQL query against a `chunk_embeddings` table with a `vector` column and `tenant_id`/`approved`/`visibility` predicates, eliminating the cross-store hydration round-trip.

## Error Mapping

Each adapter catches its library's exceptions and raises one of these typed exceptions:

| Adapter exception | API code | HTTP | Retryable |
|---|---|---|---|
| `VectorStoreTimeoutError` | `vector_store_unavailable` | 503 | yes |
| `VectorStoreUnavailableError` | `vector_store_unavailable` | 503 | yes |
| `VectorStoreInvalidDimensionError` | `internal_error` | 500 | no (boot-time validation should prevent this) |
| `VectorStoreTenantIsolationError` | `internal_error` | 500 | no (caller bug) |

Adapters MUST NOT leak `qdrant_client` exception types upward. The `vector_store_unavailable` code is added to `docs/contracts/error-taxonomy.md` if not already present (track as a follow-up).

## Configuration

Adapters read their configuration only via `app/core/config.py`, which reads from `.env`. Required env vars for `QdrantStore`:

- `QDRANT_URL` — Qdrant endpoint URL.
- `QDRANT_API_KEY` — credential, treated as Sensitive per CLAUDE.md §2.
- `QDRANT_COLLECTION_PREFIX` — defaults to `chunks` (when per-tenant collections are used, this is the prefix before `_{tenant_id}`).

The adapter constructor is injected with a config object and an `httpx.AsyncClient`; the constructor validates that all required env vars are set and that `embedding_dimension` matches the active embedding `ModelRoute`, and raises at startup if not.

## Forbidden

- Importing `qdrant_client` outside `app/adapters/vector_store/`.
- Calling Qdrant via raw HTTP from anywhere in the application code.
- Constructing a `VectorFilter` without a `tenant_id` (static type error AND runtime error).
- Mixed-tenant upsert batches.
- Reading `os.environ` directly inside a vector-store adapter.
- Any `# noqa` or `# type: ignore` in vector-store adapter code without a linked issue.

## Caller boundaries

| Allowed callers | Forbidden callers |
|---|---|
| `app/workers/tasks/ingestion.py` (upsert on chunk creation) | Any A1/A5/A6 agent |
| `app/workers/tasks/corpus_admin.py` (delete_by_filter on source removal) | The HTTP layer in `app/api/` |
| `app/agents/a3_retrieval.py` (search) | Anything outside `app/workers/` and `app/agents/a3_retrieval.py` |

Searching for vectors is exclusively an A3 retrieval concern. A4, A5, and A6 receive already-retrieved evidence packets; they never read the vector store.

## References

- ADR-0010 — rationale for the Protocol seam and the tenant-isolation invariant.
- ADR-0006 — selects Qdrant; not amended by this contract.
- ADR-0003 — DB-layer tenant invariant this Protocol mirrors.
- `docs/contracts/provider-interface.md` — the `LLMProvider` pattern this contract follows.
- `docs/contracts/code-gen-guide.md` — Forbidden Patterns; the import-rule lint extends to `qdrant_client`.
- `docs/schemas/chunk.schema.json` — the `Chunk` shape that `ScoredChunk` composes.
- `docs/schemas/scored-chunk.schema.json` — the on-disk JSON shape, `$ref`s `chunk.schema.json`.
- `docs/contracts/approved-decisions-register.md` row D-VS-001.
