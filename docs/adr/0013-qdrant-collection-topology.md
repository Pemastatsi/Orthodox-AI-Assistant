# ADR 0013: Qdrant Collection Topology — Shared Collection With Tenant Payload Filter

Date: 2026-05-19
Status: Accepted

## Context

ADR-0010 (`VectorStore` interface) and `docs/contracts/vector-store-interface.md` §Concrete
Implementations both record the same open question:

> The choice between **one collection per tenant** (`chunks_{tenant_id}`) and **one shared
> collection** with a tenant payload filter is left to T-002. The Protocol accommodates
> either; the chosen pattern is recorded in `approved-decisions-register.md` once made.

That deferral was correct when ADR-0010 was written — the Protocol seam was the
architectural decision, and the topology was an implementation detail of `QdrantStore`.
But T-002 (Tenant Data Ingestion) needs to call `upsert` against a concrete collection
on day one, and `T-001-scaffold-contracts.md` needs to pin `.env.example` and the
docker-compose Qdrant initialization. The cheapest moment to commit to a topology is
**before** any chunk is upserted; afterwards it becomes a migration with backfill cost
proportional to corpus size.

The two candidate topologies are:

1. **Shared collection with `tenant_id` payload filter.** One Qdrant collection (e.g.
   `chunks`) holds every chunk for every tenant. Every `upsert` writes the payload with
   `tenant_id` set; every `search` and `delete_by_filter` adds `must: [{ key: tenant_id,
   match: { value: <tid> } }]` to the Qdrant filter.

2. **One collection per tenant (`chunks_{tenant_id}`).** The adapter selects the
   collection by tenant. Tenant isolation is enforced by the **absence** of any
   cross-collection query path, not by a runtime filter predicate.

The choice has three real consequences worth pricing:

- **Operational cost on Railway.** Railway-managed Qdrant prices a baseline per instance,
  not per collection — additional collections inside the same instance are free. But each
  per-tenant collection requires its own index build, its own snapshot, and its own
  payload-schema configuration. At Phase 1 scale (1 active tenant, 1 starter-corpus
  virtual tenant deferred per ADR-0003 follow-up) this is a wash; at 50–100 tenants it
  becomes operationally meaningful.

- **Blast radius of a misconfigured query.** With a shared collection, a single forgotten
  `tenant_id` filter on a `search` call returns another tenant's chunks. With per-tenant
  collections, the same bug returns no rows (the collection is wrong). The shared-collection
  failure mode is worse — but `VectorStore.search` already requires a non-empty
  `VectorFilter.tenant_id` at the Protocol level (ADR-0010 §Tenant Isolation Invariant)
  and tests it directly (`tests/unit/test_vector_store_isolation.py`). The Protocol
  invariant is the primary defence in depth, regardless of topology.

- **Data residency and tenant-export ergonomics.** A bishop or seminary that asks "give
  us our corpus" or "delete our corpus" is significantly cheaper to serve with per-tenant
  collections (one snapshot, one drop). With shared collections, it is a payload-filtered
  scroll + reupload, which is slower and uses more egress.

ADR-0010 anticipated this question: the Protocol abstracts the difference, so the choice
is reversible at adapter level without touching any agent, service, or worker code.

## Decision

**Phase 1 ships one shared Qdrant collection named `chunks` with `tenant_id` as a payload
field. Every `search`, `upsert`, and `delete_by_filter` predicate-filters on `tenant_id`.**

The decision is recorded in `docs/contracts/approved-decisions-register.md` as the
follow-up to D-VS-001 that ADR-0010 promised.

### Rationale

1. **Right-sized for Phase 1 scale.** One active tenant (Orthodox Ethos) plus a deferred
   virtual starter-corpus tenant. Per-tenant collections at this scale is operationally
   premature.

2. **The Protocol invariant is the primary tenant defence.** `VectorFilter.tenant_id` is
   a required, runtime-enforced, statically-typed contract (ADR-0010). It is tested at
   the adapter boundary in `tests/unit/test_vector_store_isolation.py`. Adding a second
   defence-in-depth layer via collection-per-tenant is valuable but not necessary to
   meet ADR-0003's multi-tenant invariant.

3. **Hybrid retrieval (ADR-0011) is uniform across tenants.** Dense + sparse RRF fusion
   parameters (`k=60` default) live at the collection level. With one shared collection
   we tune one set of RRF parameters; with per-tenant collections we either accept the
   default per collection (and lose per-tenant tunability) or maintain N copies of the
   tuning (and lose the consolidated A/B story).

4. **Reranker certification (ADR-0012) reads from the collection.** A certified reranker
   route validates against a sample of admitted evidence. One shared collection means
   one sample distribution; per-tenant collections means N sample distributions, none
   of them statistically powerful at Phase 1 tenant counts.

5. **Reversibility is cheap at the Protocol level.** If the failure modes in the next
   section trigger, the adapter swaps to per-tenant collections by changing the
   collection-name resolution inside `QdrantStore` only. No agent, service, or worker
   code changes.

### Required collection configuration

The Phase 1 `chunks` collection is initialized once (at scaffold time, per T-001
`docker-compose.yml` or a one-shot init script — implementer's choice, recorded in T-002
when finalized) with:

- **Dense vector params:** size = `embedding_dimension` (read from active embedding
  `ModelRoute`, see ADR-0011), distance = cosine.
- **Sparse vector params:** a single named sparse vector `text_bm25`, populated server-side
  via Qdrant FastEmbed at ingest (per ADR-0011 §Implementation).
- **Payload indexes (required for filter performance):**
  - `tenant_id` (keyword) — required; filtered on every call.
  - `approved` (bool) — filtered on every search.
  - `visibility` (keyword) — filtered when role-restricted retrieval is in effect.
  - `source_id` (keyword) — filtered on `delete_by_filter(source_id=...)`.
- **HNSW params:** Qdrant defaults are acceptable for Phase 1; tuning is deferred to the
  retrieval-eval baseline established under `docs/contracts/retrieval-eval-suite.md`.

These configuration values are codified in `app/adapters/vector_store/qdrant_store.py`
in a single `ensure_collection()` helper called at adapter startup; the helper is
idempotent and safe to call against an existing collection (verifies parameters match;
fails closed on mismatch rather than mutating an existing collection).

### Forbidden patterns under this topology

In addition to ADR-0010's forbidden patterns, this topology adds:

- **No code path may issue a Qdrant `search` or `scroll` without a `tenant_id` filter
  in the `must` clause.** This is the same invariant ADR-0010 already enforces at the
  `VectorStore.search` Protocol boundary; this ADR makes the consequence explicit at the
  topology level (the price of forgetting the filter is cross-tenant data leak).
- **No code path may construct a collection name from request-scope data.** The shared
  collection name is a config constant (`QDRANT_COLLECTION_PREFIX` defaults to `chunks`).
  No tenant-id-in-collection-name string interpolation.

## When to reconsider — promotion criteria to per-tenant collections

Promote `QdrantStore` to per-tenant collections (and re-amend this ADR) if **any** of the
following becomes true after T-005 completes:

- A tenant contractually requires data-residency isolation that a payload filter cannot
  satisfy (i.e. the underlying collection-level storage must be tenant-scoped).
- The retrieval-eval suite shows cross-tenant payload-filter performance degrading
  meaningfully at scale (e.g. P95 search latency rises above the SLO defined in
  `phase1-implementation-contract.md`).
- A tenant-export or tenant-deletion legal requirement makes per-tenant snapshot
  semantics the only acceptable implementation.
- Tenant count exceeds 50 and operational cost of per-collection management is now lower
  than the cost of running a shared collection at that scale.

In any of those cases, the migration is bounded by ADR-0010's Protocol: the adapter
changes its collection-name resolution and its `ensure_collection()` to iterate over
tenants. No upstream caller changes. The backfill is a `scroll` + `upsert` per tenant.

## Consequences

- **`docs/contracts/vector-store-interface.md` is amended** to reference this ADR in
  the `QdrantStore` §Concrete Implementations subsection, replacing the deferral language
  with the decision and the configuration block.
- **`docs/contracts/approved-decisions-register.md`** records a follow-up row to D-VS-001
  citing this ADR.
- **`docs/contracts/scaffold-contract.md` and `T-001`/`T-002`** consume this decision when
  pinning `.env.example` and initializing the collection. No new fields in either
  document — `QDRANT_COLLECTION_PREFIX` was already pinned to `chunks` in
  `vector-store-interface.md` §Configuration.
- **No schema changes.** `chunk.schema.json` and `db-schema.md` are unchanged by this
  ADR; the topology decision affects only the adapter and the Qdrant collection
  configuration.
- **No test changes beyond the existing isolation tests.** `tests/unit/test_vector_store_isolation.py`
  already covers the Protocol invariant that defends this topology.

## Alternatives Considered

- **Per-tenant collections (`chunks_{tenant_id}`).** Rejected for Phase 1 per the
  rationale in §Decision. May be promoted later under the criteria in §When to
  reconsider.
- **Hybrid topology: shared collection for the `member` visibility tier, per-tenant
  collection for `admin_only` content.** Rejected as premature — the visibility tier
  is already a payload field with an indexed filter; collection sharding by visibility
  adds a second axis of split state for no measured benefit at Phase 1 scale.
- **Sharded shared collection (one collection per N tenants).** Rejected as an
  intermediate option that combines the operational complexity of per-tenant with the
  cross-tenant leak failure mode of shared. The Protocol invariant solves the leak; the
  intermediate split adds no value.

## Tests

- `tests/unit/test_vector_store_isolation.py` — already exists per ADR-0010; covers the
  Protocol invariant that is this topology's primary defence.
- `tests/integration/qdrant_smoke.py` — exercises the `ensure_collection()` helper
  against a real Qdrant instance, asserting:
  - The collection is created with the expected dense + sparse vector params and the
    four required payload indexes.
  - A second call against the same collection succeeds (idempotent).
  - A call with a mismatched `embedding_dimension` raises
    `VectorStoreInvalidDimensionError` and does not mutate the collection.
- `tests/integration/retrieval_cross_tenant.py` — new test (to be added during T-002):
  upsert chunks under `tenant_a` and `tenant_b` into the shared collection; assert that
  a `search` with `VectorFilter(tenant_id="tenant_a")` returns only `tenant_a` chunks,
  and that a `search` with an empty `tenant_id` raises `ValueError` before issuing any
  Qdrant call.

## References

- ADR-0003 (multi-tenant day one) — the tenant-isolation invariant this topology serves.
- ADR-0006 (PAG-RAG lineage architecture) — selects Qdrant; not amended.
- ADR-0010 (VectorStore Interface Pattern) — the Protocol seam that makes this topology
  decision reversible.
- ADR-0011 (Hybrid Retrieval) — defines the sparse vector configuration the shared
  collection must provision.
- ADR-0012 (Reranker Selection) — defines the certified-rerank route the collection
  serves.
- `docs/contracts/vector-store-interface.md` — full Protocol and configuration spec.
- `docs/contracts/approved-decisions-register.md` row D-VS-001 follow-up.
- `docs/contracts/scaffold-contract.md` — `.env.example` pins for `QDRANT_*`.
