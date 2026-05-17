# ADR 0011: Hybrid Dense + Sparse Retrieval (Phase 1)

Date: 2026-05-17
Status: Accepted

## Context

ADR-0006 selects Qdrant for Phase 1 retrieval and locks the MVP as "vector-first." It does not forbid sparse retrieval — it defers it. ADR-0006 §Phase 3 even names BM25 as part of the future combined retrieval signal. The question this ADR answers is whether to wait, or to pull the sparse signal forward into Phase 1.

The closed Patristic corpus has a property that pure dense retrieval handles poorly: a large fraction of high-value queries are **lexically specific**. Examples from the existing 20-case safety suite and reasonable extensions:

- Father names with multiple transliterations (Gregory of Nyssa, Γρηγόριος Νύσσης, Gregorios Nysses).
- Conciliar canon citations ("Canon 28 of Chalcedon", "Apostolic Canon 64").
- Greek theological terms (theosis, hypostasis, perichoresis) where the relevant chunk often contains the exact term and the rest is paraphrase.
- Scripture references ("John 6:53", "1 Cor 11:29") where the chunk verbatim contains the verse.
- Work titles in original language (*Περὶ Ἀρχῶν*, *Φιλοκαλία*).

`openai:text-embedding-3-small` (D-MDL-001) handles paraphrase well and exact-term recall poorly. The single empirical RAG study the team has reviewed against a structurally comparable domain (Sialtsis 2026, University of Thessaly e-ce.uth.gr corpus) measures the gap: pure dense retrieval scored Recall@6 = 0.70 and Precision@6 = 0.25; the same corpus with BM25 added scored Recall@6 = 0.90 and Precision@6 = 0.72. The corpora are not identical, but the failure mode is — natural-language queries against a domain corpus where some terms must match exactly.

The deferred-to-Phase-2 position was reasonable when "sparse retrieval" meant "stand up a second index infrastructure (FAISS + `rank_bm25`) and write custom fusion code." That is the architecture in the Sialtsis 2026 reference and was the default in 2023–2024. It is not the architecture available in Qdrant today: since v1.10, sparse vectors live in the same collection as dense vectors, fusion (RRF, DBSF) runs server-side in a single `Query` API call, and the existing tenant payload filters apply uniformly to both signals. The cost of adding hybrid retrieval is no longer "a second backing store"; it is "one optional parameter on `VectorStore.search`."

## Decision

A3 retrieval issues a **hybrid query** combining dense and sparse vector signals through Qdrant's native sparse-vector support, fused server-side with Reciprocal Rank Fusion (RRF). Phase 1 ships this as the default A3 path. Pure-dense retrieval remains the fallback when no sparse model is configured.

**This ADR does not amend ADR-0006.** Qdrant remains the Phase 1 vector store; vector-first remains the policy ("dense + sparse via Qdrant" is still vector-first). The change is purely about which signals A3 combines inside Qdrant.

### Sparse model choice

The Phase 1 sparse signal is **BM25 via Qdrant FastEmbed server-side inference**. BM25 is well-understood, deterministic, requires no per-document model inference time, and produces interpretable inverted-index output. BM42 (Qdrant's IDF-variant) and learned sparse models (SPLADE) are explicitly deferred — both require additional empirical comparison on the Patristic corpus before certification, and SPLADE adds a model dependency in the ingestion path that violates the closed-corpus operational principle (no per-chunk LLM inference at ingest).

### Fusion strategy

Server-side Reciprocal Rank Fusion (RRF) with default `k = 60`. RRF was chosen over Distribution-Based Score Fusion (DBSF) for Phase 1 because:

1. RRF is rank-based and therefore insensitive to score-scale differences between the dense (cosine, [0.0, 1.0]) and sparse (BM25, unbounded) signals.
2. RRF is the de facto standard in production hybrid systems and has a single tunable parameter; DBSF requires per-query score-distribution estimation that is harder to reason about during incident response.
3. RRF is monotonic — adding a candidate to one signal never demotes another candidate's final rank below where it would have been on that signal alone.

The `k=60` default is recorded in `approved-decisions-register.md` row D-RET-001 and is tenant-tunable through safe config (per the same pattern as the 70% quote-overlap threshold from `quote-overlap-algorithm.md`).

### Protocol extension (full spec lives in `vector-store-interface.md`)

`VectorStore.search` gains one optional parameter:

```python
async def search(
    self,
    *,
    query_vector: list[float],
    sparse_query: SparseVector | None = None,
    filters: VectorFilter,
    top_k: int,
) -> list[ScoredChunk]: ...
```

When `sparse_query` is `None`, the call is dense-only (current behavior). When `sparse_query` is present, the adapter issues a single Qdrant `Query` API request with a `prefetch` block for each signal and a `fusion: rrf` resolution step. The tenant filter is applied to both branches identically — there is no path through hybrid retrieval that skips tenant isolation.

`SparseVector` is the standard Qdrant shape (`indices: list[int]`, `values: list[float]`) and is defined in `app/domain/models.py` alongside `ChunkPayload`.

### Tenant-isolation invariant (unchanged)

`VectorFilter.tenant_id` remains required. The adapter MUST apply the filter to both the dense `prefetch` and the sparse `prefetch`. There is no separate "sparse tenant filter" path.

### Forbidden patterns

- Issuing two separate `search` calls (one dense, one sparse) and fusing in application code. The fusion MUST be server-side.
- Constructing a `SparseVector` outside the sparse-vector adapter in `app/adapters/vector_store/sparse_encoder.py`.
- Bypassing the tenant filter on the sparse branch.
- Calling FastEmbed directly from agent or service code.

## Why not separate FAISS + `rank_bm25` (the Sialtsis 2026 / classical pattern)

Two backing stores doubles the corpus-version invalidation surface (a chunk edit must succeed in both before A4 admits it), doubles the upsert-failure recovery story, and forces fusion to happen in application code where the tenant filter has to be re-applied. None of these costs are paid by Qdrant's native sparse support.

## Why not defer to Phase 2 alongside the cross-encoder reranker

The reranker (ADR-0012) and the sparse signal solve different problems. The sparse signal raises **recall** — getting the right candidate into the top-K at all. The reranker raises **precision** — choosing the best candidate from the top-K. Sialtsis 2026 §5.3.1 shows recall climbing 0.70 → 0.90 with sparse added; reranker alone would not have recovered the missing 0.20. Adding only one of the two is a partial fix; adding sparse first (cheaper, no model inference) and reranker second is the correct ordering.

## When to reconsider

- If RRF underperforms DBSF or learned fusion on the retrieval evaluation suite (`retrieval-eval-suite.md`) by a measurable margin on the certified gold set, switch fusion mode. The Protocol does not change; only the adapter call.
- If BM25 underperforms BM42 or SPLADE on Polytonic Greek queries in the Phase 2 multilingual embedding upgrade window (ADR-0006 §Embedding Model Upgrade), revisit the sparse model. Record in a follow-up row to D-RET-001.
- If Qdrant's hybrid-query latency exceeds the per-tenant retrieval SLO (recorded once measured), consider returning to two separate queries fused in application code — but only with measurement.

## Consequences

- **One Protocol extension:** `VectorStore.search` gains `sparse_query: SparseVector | None = None`. Default `None` preserves existing call sites; only A3 passes a non-`None` value.
- **One new adapter module:** `app/adapters/vector_store/sparse_encoder.py` wraps Qdrant FastEmbed for BM25 sparse-vector encoding of queries. Mirrors the pattern of provider/embedding adapters.
- **One new payload field:** `ChunkPayload.sparse_embedding: SparseVector | None`. Filled at ingestion via the same FastEmbed call that encodes the chunk text; `None` for chunks ingested before this ADR is implemented (the dense-only path remains a valid retrieval mode for those).
- **One ingestion backfill:** existing approved chunks must be re-ingested or batch-updated to populate `sparse_embedding`. The corpus is small enough at Phase 1 scale (single tenant) that a one-shot batch is acceptable. The job is tracked through the existing `ingest_jobs` state machine; `corpusVersion` bumps on completion (cache flush).
- **No new dependency on managed services.** FastEmbed runs inside the existing application container; BM25 inference is CPU-bounded and fast (< 5 ms per query at corpus scale).
- **Retrieval evaluation becomes meaningful.** Once `retrieval-eval-suite.md` is wired up, the empirical claim "sparse adds ~0.20 to Recall@6" can be verified or refuted on the actual Patristic corpus, and the decision can be revisited with data rather than analogy.

## Alternatives Considered

- **Separate FAISS + `rank_bm25` indexes with application-side fusion** (Sialtsis 2026 pattern). Rejected for two-backing-store cost and broken tenant-filter symmetry.
- **Dense-only retrieval with cross-encoder reranker carrying all the load.** Rejected per "Why not defer" above — reranking cannot recover candidates that never made the top-K.
- **SPLADE for Phase 1 sparse signal.** Rejected for the per-document inference cost and the model dependency in the ingest path; revisitable in Phase 2.
- **BM42 as Phase 1 sparse default.** Rejected because the published benchmarks against BM25 are contested and the team has no internal measurement on Patristic content; promote it via approved-decisions-register if comparison shows a clear win.
- **Server-side fusion via DBSF.** Rejected for Phase 1 in favor of RRF's score-scale insensitivity; revisitable per "When to reconsider."

## Tests

- `app/adapters/vector_store/qdrant_store.py::search` with both `query_vector` and `sparse_query` set issues exactly one Qdrant `Query` API request (verified by HTTP mock in `tests/integration/qdrant_smoke.py`).
- A lexical-specificity fixture (Father name with rare transliteration; canon citation; scripture verse) returns the matching chunk in the top-3 hybrid result, where it does NOT appear in the top-10 dense-only result for the same corpus.
- `VectorFilter.tenant_id` validation fires identically on the hybrid path and the dense-only path; an A3 test verifies that a cross-tenant chunk never appears in a hybrid result, even when its sparse score is high.
- Backfill smoke test: a chunk ingested before sparse support is queryable with `sparse_query=None` and absent from `sparse_query`-filtered hybrid results until backfilled.
- Retrieval evaluation regression: the certified gold set (`retrieval-eval-suite.md`) shows Recall@6 ≥ the dense-only baseline on every released gold-set version. A measured regression blocks the ADR-0011 implementation merge.

## References

- ADR-0006 (PAG-RAG lineage architecture) — establishes vector-first; not amended.
- ADR-0010 (VectorStore interface) — the Protocol this ADR extends.
- ADR-0012 (Reranker Selection) — the complementary precision step.
- `docs/contracts/vector-store-interface.md` — Protocol definition, updated for `sparse_query`.
- `docs/contracts/retrieval-eval-suite.md` — the empirical gate this ADR's claims will be measured against.
- `docs/contracts/approved-decisions-register.md` row D-RET-001.
- Sialtsis, A. (2026). *Building an AI Chatbot using RAG Architecture*. Diploma Thesis, University of Thessaly. §5.3.1 (retrieval results), §4.3 (hybrid metadata-based strategy) — the empirical anchor for the recall claim.
