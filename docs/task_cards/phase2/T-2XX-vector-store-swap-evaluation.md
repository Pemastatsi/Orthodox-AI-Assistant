# T-2XX: Vector-Store Swap Evaluation (Turbopuffer / pgvector+ParadeDB)

Status: Phase 2 — not scheduled. Card exists so the eventual planning session does not start from zero.

## Trigger conditions (any of)

- Active tenant count exceeds 5.
- Railway-hosted Qdrant operational cost exceeds $100/mo.
- A tenant requires data-residency isolation that the shared Qdrant collection cannot deliver.
- Cross-tenant payload-filter performance degrades measurably under the shared-collection topology.

## Required Reads

- ADR-0010 (`VectorStore` Interface Pattern) — the Protocol seam that makes the swap cheap.
- ADR-0013 (Qdrant Collection Topology) — the topology being replaced.
- `docs/contracts/vector-store-interface.md` §"Concrete Implementations" — the PgvectorStore and TurbopufferStore subsections.
- REC-022 in the 2026-05-22 frontier meta-evaluation.

## Candidates

1. **Turbopuffer** — namespace-per-tenant native; object-storage-backed; BM25 + dense + RRF native. Tenant isolation becomes structural (namespace == tenant). ≈3–10× cheaper than Qdrant Cloud at our scale.
2. **pgvector + ParadeDB** (PG 17, halfvec, BM25 via `pg_search`) — colocates retrieval with the main DB; eliminates the Postgres↔Qdrant hydration join. Useful when the cross-store hydration is the latency bottleneck rather than the vector store itself.

## Acceptance Criteria

- Per `docs/contracts/embedding-upgrade-sop.md`, run the dual-index window against the certified retrieval-eval gold set with each candidate.
- New `<adapter>_cross_tenant.py` integration test passes the existing tenant-isolation contract on the new backend (`tests/integration/vector_store/<adapter>_cross_tenant.py`).
- Cost comparison report (Qdrant Cloud vs Turbopuffer vs pgvector+ParadeDB) at the current corpus + query volume.
- Owner decision on which candidate to certify (or none, deferring further).

## Forbidden Scope

- No swap without ADR-0010 Protocol-surface parity. New adapters MUST implement the existing `VectorStore` Protocol; no caller code changes outside `app/adapters/vector_store/`.
- No regression on tenant-isolation invariant — the new adapter's integration test set must include the same coverage as the existing Qdrant adapter test.
- No silent embedding-dimension mismatch — boot-time check from `vector-store-interface.md` L51 applies to every adapter.
