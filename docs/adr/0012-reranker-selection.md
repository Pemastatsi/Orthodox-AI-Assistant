# ADR 0012: Reranker Selection — Cross-Encoder, Not LLM-Pointwise

Date: 2026-05-17
Status: Accepted

## Context

`AGENTS.md` §Known Architecture Gaps #4 records the reranker as "deferred to Phase 2" while requiring that `a3_retrieval.py` return `ScoredChunk` objects in Phase 1 specifically so a reranker can be wired in later without breaking A4's input contract. That is a deferred-implementation decision, not a deferred-architecture decision. The architecture choice — what kind of reranker — has never been recorded. This ADR records it now, before any code is written, because the cheapest moment to commit to a reranker shape is before the seam is consumed.

There are two architectural families to choose between:

1. **LLM-as-reranker (pointwise).** Send each candidate passage to a generative LLM with a prompt of the form "score relevance 0–5, return only the number." Parse the number. Sort by score. This is the pattern used in the Sialtsis 2026 reference and in many early RAG tutorials. It is conceptually simple and runs against any model the team already has a provider adapter for.

2. **Cross-encoder reranker.** Use a model purpose-built for query-passage relevance scoring (the input is the (query, passage) pair, the output is a single continuous score). These models are smaller than generative LLMs, faster per call, listwise-batchable, and cheaper. Examples in production use in 2026: `BAAI/bge-reranker-v2-m3` (open-source, multilingual including Greek, Apache-2.0), Cohere Rerank v3 multilingual (managed API), Jina Reranker v2 (managed API).

Sialtsis 2026 §7.3.3 measured the LLM-pointwise approach empirically on a structurally comparable corpus: it consumed ~90% of per-query token cost (~$0.019 per query, ~$1,900 per 100k queries) and produced a faithfulness lift from 3.00 to 4.80. The lift is real and meaningful; the cost shape is wrong for this project. Cross-encoders achieve the same family of quality gain at roughly two orders of magnitude lower cost and with sub-100ms latency.

There is also an architectural argument independent of cost. The project's pipeline (ADR-0006, AGENTS.md §Query Pipeline) keeps A5 composition as the single generative LLM call in the answer path. Every other stage is either a low-cost structured call (A1/A2 QueryAnalyzer), a deterministic service (A4 evidence admission, A6 verification), or a retrieval operation. Inserting another generative LLM call as A3.5 — and one that calls the model N times per query — breaks that discipline for no architectural gain over a purpose-built model.

## Decision

A3 retrieval is followed by an optional reranking step, implemented behind a **`Reranker` Protocol** mirroring `LLMProvider` (ADR-0004) and `VectorStore` (ADR-0010). Concrete implementations are cross-encoder rerankers, not generative LLMs invoked pointwise.

Phase 1 ships one concrete implementation: `BgeRerankerLocal`, wrapping `BAAI/bge-reranker-v2-m3` via `sentence-transformers`. A second implementation, `CohereRerankerAdapter`, is planned but is not the Phase 1 default — managed API rerankers add a corpus-egress consideration (each query and the candidate passages traverse a third-party API boundary) and require the same closed-corpus-egress review that any managed provider gets through the route certification protocol.

The reranker is a `ModelRoute` with `purpose='rerank'` and is subject to the certification protocol from ADR-0004: it may not serve user traffic until the route's `certification_status` reaches `certified` via a passing safety-suite run plus a passing retrieval evaluation run (the second gate is added in this ADR — see Tests).

### Protocol surface (full spec lives in `reranker-interface.md`, to be written alongside implementation)

```python
@runtime_checkable
class Reranker(Protocol):
    name: str               # 'bge_v2_m3' | 'cohere_rerank_v3_multilingual' | ...

    async def rerank(
        self,
        *,
        query: str,
        candidates: list[ScoredChunk],
        top_k: int,
        tenant_id: str,         # for logging + per-tenant routing, NOT for filtering
    ) -> list[ScoredChunk]: ...
```

The reranker receives candidates that A3 already filtered by tenant — `tenant_id` is passed for run-trace tagging and per-tenant model routing, never as a re-filtering opportunity. Returning fewer than `top_k` candidates is allowed (some rerankers drop candidates below a relevance floor). Returning candidates not present in the input is forbidden.

The output `ScoredChunk.score` field is preserved from the dense-retrieval call. A new optional field `rerankScore: float | None` carries the reranker's output (added to `docs/schemas/scored-chunk.schema.json`). A4 sorts by `rerankScore` when present, falling back to `score`.

### When the reranker is invoked

A3 invokes the reranker if and only if all three are true:

1. The active `model_routes` row for `purpose='rerank'` has `certification_status='certified'`.
2. The retrieval call returned more than `top_k` candidates from the hybrid retrieval (ADR-0011). If fewer candidates than `top_k`, reranking adds no value and is skipped.
3. The query is not `confidenceTier=RED` (RED early-exits per AGENTS.md §Query Pipeline; the reranker is never reached).

When no certified rerank route exists, A3 returns dense-or-hybrid scores directly. This mirrors the A6 verifier-judge pattern from D-MDL-001: the system is correct without the optional stage, and the stage activates only when certified.

### Forbidden patterns

- Importing `sentence_transformers` or any reranker SDK outside `app/adapters/reranker/`.
- Calling a generative-LLM provider adapter (`LLMProvider.generate_text` or `generate_structured`) from anywhere in the reranking path. The `Reranker` Protocol's concrete implementations are not allowed to call a generative LLM; if a future requirement demands LLM-based reranking, it must take a new ADR that addresses the cost shape and the answer-path-LLM-count principle head-on.
- Modifying `ScoredChunk.score` (the dense score). Rerankers write to `rerankScore` only.
- Routing reranking through a managed API without that route appearing in `model_routes` with `certification_status='certified'`.

## Why not LLM-pointwise (the Sialtsis 2026 pattern)

Four reasons, in descending order of importance:

1. **Cost shape.** Sialtsis §7.3.3 measured 20 LLM calls per query at gpt-4o-mini rates consuming ~90% of per-query token spend. At the project's Phase 1 metering (`served_answer_count`), this would make reranking the dominant variable cost per served answer — a brittle position for a metered-billing product whose unit economics depend on bounded per-answer cost. Cross-encoders run in the application container at zero marginal API cost.
2. **Pipeline discipline.** A5 is the only generative LLM call in the answer path. Adding a second generative call (or 20) is a regression of an existing architectural invariant.
3. **Latency.** Twenty sequential LLM calls (or even a batched listwise call) at API rates is at minimum hundreds of milliseconds; a local cross-encoder is sub-100ms for the same candidate count.
4. **Brittleness of pointwise parsing.** LLM-pointwise scoring depends on the model returning a parseable integer; failures degrade silently into ranking noise. Cross-encoders return floats directly and never fail this way.

The faithfulness lift Sialtsis measured is the right outcome to pursue; the implementation is not the one to copy.

## Why not Cohere Rerank v3 as Phase 1 default

Cohere Rerank v3 multilingual is a strong reranker with documented Greek-language support and a clean managed API. It is not the Phase 1 default for two reasons specific to this project:

1. **Corpus egress.** Every reranked query sends the user's query and ~20 candidate passages to a third-party API. The candidate passages include approved Patristic content, which is not Sensitive per CLAUDE.md §1 but is Confidential. Egressing it requires the same closed-corpus-egress review as any managed provider — easier to schedule once a measured baseline is in place.
2. **Offline reproducibility of the eval suite.** `retrieval-eval-suite.md` runs in CI. CI environments without outbound network access can run `BgeRerankerLocal` deterministically; they cannot run a managed reranker without secrets and external dependencies.

`CohereRerankerAdapter` is recorded as the Phase 1 managed-API alternative and is expected to be certified alongside the local implementation. The Protocol accommodates both with no implementation change.

### Greek-stress fallback path (REC-016)

`CohereRerankerAdapter` is the canonical Greek-stress fallback. Tenants whose retrieval-eval scores show measurably worse Polytonic-Greek rerank quality on `BgeRerankerLocal` get routed to Cohere Rerank v3.5 instead. The routing decision is per-tenant: a `tenant.config.rerankerRoutePreference: 'bge_local' | 'cohere'` field selects between two certified `ModelRoute` rows with `purpose='rerank'`. Certification of each route is gated independently on the retrieval-eval suite per `retrieval-eval-suite.md`; promoting a route to `certified` requires `role='owner'` per ADR-0004. The Cohere egress posture is documented in ADR-0005 §"Reranker egress" — reranker input is Confidential, not Sensitive, and the tenant-facing setting makes the egress choice explicit per tenant.

## When to reconsider

- **Cross-encoder underperforms on the eval suite.** If `BgeRerankerLocal` fails to lift Recall@6 / Precision@6 / faithfulness above the hybrid-no-rerank baseline by a meaningful margin on the certified gold set, the reranker is removed from the active path (set the rerank `ModelRoute` to `deprecated`). Reranking with no measurable benefit is dead weight.
- **Explainable reranking is required.** A reviewer-facing feature requesting natural-language rationales for ranking decisions is a real driver for LLM-based reranking. That work takes a new ADR.
- **Multilingual Greek-content reranking is poor.** If BGE-reranker-v2-m3's Polytonic Greek performance is measurably weak (the eval suite contains Polytonic Greek queries), `CohereRerankerAdapter` becomes the certified default. Recorded as a follow-up to D-RNK-001.

## Consequences

- **AGENTS.md Known Architecture Gap #4 is resolved** — the reranker is no longer architecturally undecided; the seam definition (Phase 1) and the active implementation (Phase 1 once eval-suite gates pass) are both specified. The gap-list entry is updated in this work.
- **One new adapter module:** `app/adapters/reranker/` with `base.py` (Protocol), `bge_reranker_local.py` (concrete), and `__init__.py` (factory). Mirrors `app/adapters/vector_store/`.
- **One new `ModelRoute` purpose:** `'rerank'`. Seeded as `certification_status='draft'` until the eval suite produces a passing run. The certification protocol from ADR-0004 applies unchanged.
- **One schema additive change:** `scored-chunk.schema.json` gains optional `rerankScore`. No breaking change — readers without rerank support ignore the field.
- **One new dependency:** `sentence-transformers` (for `BgeRerankerLocal`). Apache-2.0 licensed. Adds ~500 MB to the container image because of the bundled model weights; acceptable for Phase 1 single-tenant deployment.
- **Eval-suite gate becomes binding.** Reranker certification requires both a passing safety suite (ADR-0004) and a passing retrieval evaluation (`retrieval-eval-suite.md`). This is the first time a non-handling metric gates certification; the precedent is intentional.

## Alternatives Considered

- **LLM-as-pointwise-reranker (Sialtsis 2026 pattern).** Rejected for the four reasons in §Why not.
- **LLM-as-listwise-reranker (single call ranking the whole candidate list — RankGPT-style).** Closer to acceptable on cost grounds (one call instead of N), but still adds a generative LLM call to the answer path and still requires structured-output parsing of a ranked list. Rejected; reconsidered if cross-encoders empirically underperform.
- **ColBERT / late-interaction reranking.** Higher quality ceiling, but requires storing per-token embeddings (10–50× the storage cost of dense vectors) and a more complex serving stack. Disproportionate for Phase 1 corpus scale.
- **No reranker at all (hybrid retrieval only).** The hybrid signal from ADR-0011 is expected to handle most of the recall problem; reranking is precision. Decided to commit the architecture choice now and let the eval suite gate activation — the seam costs nothing if the route never gets certified.
- **Cohere Rerank v3 multilingual as Phase 1 default.** Rejected for §Why not Cohere reasons; retained as a certified alternative.

## Tests

- `app/adapters/reranker/base.py` defines `Reranker` exactly as specified above.
- `BgeRerankerLocal.rerank` with N candidates returns at most `top_k` candidates, all of which were in the input.
- Reranker MUST NOT return candidates with a different `chunk.chunk_id` than any input candidate (no fabrication).
- An A3 retrieval test with a `FakeReranker` that reverses input order produces an A4 evidence packet in the reversed order, proving `rerankScore` is what A4 sorts by when present.
- The `model_routes` certification gate: A3 with `certification_status='draft'` on the rerank route does NOT invoke the reranker. A3 with `certification_status='certified'` DOES invoke it.
- Retrieval evaluation regression: the eval suite's reranked variant scores Recall@6 ≥ hybrid-no-rerank baseline AND faithfulness ≥ hybrid-no-rerank baseline on the certified gold set. Failure to clear both gates blocks the rerank route's certification.
- Reranker failure path: a `RerankerTimeoutError` or `RerankerUnavailableError` from the adapter returns dense-or-hybrid candidates as-is, with an `a3.rerank_skipped` event in the run trace. The query does NOT fail.

## References

- ADR-0004 (Model Provider Routing) — the certification protocol this ADR's `purpose='rerank'` routes inherit.
- ADR-0006 (PAG-RAG lineage architecture) — the answer-path-LLM-count principle this ADR preserves.
- ADR-0010 (VectorStore interface) — the Protocol pattern this ADR mirrors.
- ADR-0011 (Hybrid Retrieval) — the complementary recall step. Hybrid raises recall; reranker raises precision; they compose.
- `AGENTS.md` §Known Architecture Gaps #4 — resolved by this ADR.
- `docs/contracts/retrieval-eval-suite.md` — the empirical gate for reranker certification.
- `docs/contracts/approved-decisions-register.md` row D-RNK-001.
- `docs/schemas/scored-chunk.schema.json` — extended with optional `rerankScore`.
- Sialtsis, A. (2026). *Building an AI Chatbot using RAG Architecture*. §3.4 (LLM-based reranking), §7.3.3 (cost analysis) — the empirical anchor for the cost-shape argument.
