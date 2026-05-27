# T-009: Embedding Upgrade Benchmark + Late Chunking + ColBERT + A5 Peer Certification

## Goal

Open the dual-index window described in `docs/contracts/embedding-upgrade-sop.md` to compare BGE-M3 and `text-embedding-3-large` against the certified Phase-1 baseline `openai:text-embedding-3-small`. Sequence the dependent items (REC-014 late chunking, REC-015 ColBERT 3rd retrieval signal) that gate on the embedding winner. Concurrently, certify a Modal-hosted Llama-3-70B route as the A5-purpose peer named in ADR-0014 (GS-4).

The card is **planning + execution** — execution code is scaffolded under the existing `embedding-upgrade-sop.md` SOP and the existing ADR-0004 certification protocol. T-009 does not introduce new infrastructure beyond what the SOP, the retrieval-eval suite, and Modal already provide.

## Required Reads

- [`docs/contracts/embedding-upgrade-sop.md`](../../contracts/embedding-upgrade-sop.md) — the dual-index → backfill → certify → cutover → rollback → decommission pipeline.
- [`docs/contracts/retrieval-eval-suite.md`](../../contracts/retrieval-eval-suite.md) — the gating gold-set protocol for embedding and rerank routes.
- [`docs/adr/0006-pag-rag-lineage-architecture.md`](../../adr/0006-pag-rag-lineage-architecture.md) §"Phase 2 Embedding Upgrade: Recommended Candidates" — the original deferred decision now opened.
- [`docs/adr/0009-chunking-strategy.md`](../../adr/0009-chunking-strategy.md) §"Late Chunking" — REC-014 gating.
- [`docs/adr/0011-hybrid-retrieval.md`](../../adr/0011-hybrid-retrieval.md) §"Optional 3rd signal — late-interaction / ColBERT" — REC-015 gating.
- [`docs/adr/0014-cross-provider-failover.md`](../../adr/0014-cross-provider-failover.md) — A5-peer certification target (GS-4).
- [`docs/adr/0004-model-provider-routing.md`](../../adr/0004-model-provider-routing.md) — route certification protocol every route in this card flows through.

## Files In Scope

### Phase-A: embedding benchmark

- New `model_routes` rows (seed): `openai:text-embedding-3-large` and `bge:bge-m3`, both `certification_status='experiment'`.
- Two new Qdrant collections (or named vectors) per the SOP §Stage 1.
- Backfill runs through the existing `app/workers/tasks/ingestion.py` re-embed path with `--embedding-route` flag (T-002 amendment in T-008).
- Retrieval-eval suite runs Stage 3 per the SOP.

### Phase-B: late chunking (REC-014, gated on Phase-A winner being long-context capable)

- Amend `app/services/embedding/embed_chunk.py` to issue document-level embedding then segment per the late-chunking algorithm (Jina arXiv:2409.04701) — gated by `RetrievalPlan.lateChunking: bool` flag added in Phase-B.
- `corpusVersion` bump and full re-embed under the SOP §Stage 4.

### Phase-C: ColBERT 3rd retrieval signal (REC-015)

- If BGE-M3 wins Phase-A, the ColBERT head ships with the model — only the multi-vector Qdrant collection (or pgvector multi-column) needs provisioning.
- If `text-embedding-3-large` wins Phase-A, add `jinaai/jina-colbert-v2` as a separate `ModelRoute` with `purpose='colbert'`; the ScoredChunk contract is unchanged (score updates in place).
- `RetrievalPlan.useLateInteraction: bool` flag added to the retrieval-plan schema; default `False`.

### Phase-D: Modal Llama-3-70B A5 peer (GS-4)

- Provision a Modal endpoint hosting Llama-3-70B (Modal A100 or H100 per the per-second-billed pricing in REC-018).
- New `model_routes` row `modal:llama-3-70b` with `purpose='compose'`, `certification_status='experiment'`.
- Add `failover_peer_route_id` reference from the certified A5 Opus route to the Llama-3-70B route (per ADR-0014 §Interface Contract).
- Run the safety-suite (`backend/tests/safety/test_20_queries_harness.py`) AND retrieval-eval through the Llama-3-70B route. Both must pass before route promotion to `certified`.
- Set ADR-0014's latency-breaker thresholds on the Opus route (default A5: 12000ms p95 over a 60s window, 120s cooldown). Verified via load test before merge.

## Acceptance Criteria

### Phase-A (embedding benchmark)

- BGE-M3 and `text-embedding-3-large` both back-filled into separate Qdrant collections; row count parity with the production collection verified per SOP §Step 2.2.
- Retrieval-eval suite run for each candidate; report attached to the PR shows Recall@K, Precision@K, MRR, nDCG@K at K∈{6,12,20} and the four answer-quality metrics, each compared against the certified baseline.
- Owner certifies exactly one candidate per ADR-0004 protocol. Sonnet 4.6 — wait, this is the embedding card, not the LLM card; the certifying owner certifies one of the embedding candidates, not a model swap.
- Pass gate per `retrieval-eval-suite.md`: new score ≥ baseline − 0.02 on every metric. If no candidate clears, the baseline remains; T-009 closes Phase-A with a documented "no winner" outcome and the dual-index collections decommission per SOP §Stage 6.

### Phase-B (late chunking, only if Phase-A winner is long-context capable)

- `RetrievalPlan.lateChunking: bool` field added to the retrieval-plan schema; default `False`.
- A `RetrievalPlan` with `lateChunking=True` produces measurably different chunk-vector embeddings vs the per-chunk path on a fixture document containing a multi-page Patristic argument; the test asserts the difference is non-trivial AND that A6 quote-overlap still passes on the same fixture.
- corpusVersion bumps; full re-embed under SOP.

### Phase-C (ColBERT)

- `RetrievalPlan.useLateInteraction: bool` field added; default `False`.
- Retrieval-eval shows late-interaction lifts Polytonic-Greek Recall@6 by ≥ 2 points on the certified gold set; otherwise the feature flag stays `False` by default and the work parks pending more data.
- ScoredChunk contract unchanged (regression test asserts schema parity).

### Phase-D (Modal Llama-3-70B A5 peer)

- Modal endpoint provisioned with the bge-reranker GPU sharing (REC-018) where possible; egress documented in ADR-0005 §"Reranker / Managed-Inference Egress" extended for the composer route too.
- Safety-suite passes 20/20 on the Llama-3-70B route. Retrieval-eval passes per the gate.
- Route promoted from `experiment` to `certified` by `role='owner'` PATCH.
- `failover_peer_route_id` set on the certified Opus 4.7 route.
- Load test triggers the latency-breaker threshold; the failover fires; the response is composed by Llama-3-70B; A6 quote-overlap still passes (closed-corpus invariant preserved). Test artifacts attached to the PR.

## Forbidden Scope

- No embedding-route swap without passing Stage 3 gates per the SOP.
- No late chunking without a Phase-A winner whose context window can hold typical Patristic chapters.
- No Llama-3-70B promotion to `certified` without both safety-suite and retrieval-eval green.
- No silent failover during the certification window — `failover_peer_route_id` is set only after the peer is `certified`.
- Modal egress for the composer route requires the same per-tenant opt-in pattern documented in ADR-0005; chunk text leaving to Modal-hosted Llama-3-70B is Confidential, not Sensitive, and the tenant-facing setting MUST be explicit.

## Notes for Future Sessions

- The card is split into four phases so each can be opened and merged independently. Phase-A is the foundation; Phase-B and Phase-C gate on it; Phase-D is independent (uses Modal infrastructure already proposed by REC-018).
- The "no winner" outcome in Phase-A is a valid completion state. The dual-index window is reversible by design — see SOP §Stage 5 rollback.
- The Modal Llama-3-70B route is named in ADR-0014 as a candidate; if a stronger A5 peer emerges before T-009 lands (e.g., another Anthropic model family, or a Bedrock Claude route), the certification work is the same — ADR-0014 does not hard-code Llama-3-70B.
