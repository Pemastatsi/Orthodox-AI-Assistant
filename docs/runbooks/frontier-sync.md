# Runbook: Quarterly Frontier Sync

Status: Canonical
Date: 2026-05-22
Cadence: Quarterly (next: 2026-08-22)
Owner: Maintainer + Owner sign-off on resulting ADR amendments.

This runbook keeps the model / embedding / reranker / vector-store / observability stack from drifting behind frontier between major Phase-2 planning windows. The 2024-frozen `openai:text-embedding-3-small` is the cautionary example: a route that is correct at decision time can quietly become inferior 12 months later without a process to notice.

The runbook is **cheap by design**: a fixed checklist, a fixed report shape, and at most one ADR amendment per quarter.

## Trigger

- Calendar-scheduled, quarterly. The maintainer schedules the next iteration on the day the previous one closes.
- Out-of-cycle triggers (a major model release, a new vendor incident pattern, a competitor launch) may pull a sync forward. Out-of-cycle runs follow the same checklist.

## Inputs

- The currently certified `ModelRoute` rows for every `purpose` (`query_analyzer`, `compose`, `verifier_judge`, `embedding`, `rerank`, `context_prefix`, `edge_extraction`, `retrieval_eval_judge`).
- The active retrieval-eval gold sets per tenant (`tests/retrieval_eval/gold_sets/<tenant_id>/<version>.json`).
- The Phase-2 frontier candidate list from the most recent meta-evaluation (or from this runbook's prior iteration).

## Procedure

### Step 1 — Re-run the retrieval-eval suite against current routes (baseline)

```
cd backend
uv run pytest tests/retrieval_eval/ -v --report=frontier-sync-baseline.json
```

This is the unchanged retrieval-eval suite per `docs/contracts/retrieval-eval-suite.md`. The output baseline becomes the floor for any candidate evaluated this quarter.

### Step 2 — Check 2026/2027 frontier benchmarks for each layer

Verify each layer of the stack against published 2026/2027 benchmarks. For each layer, answer:

- Has a new model / library / service entered the field since the last sync that would clear the certified baseline by ≥ ε on the retrieval-eval metrics?
- Has the currently certified route been deprecated, repriced, or had its license posture change?
- Has the underlying vendor had a sustained-incident pattern that should trip ADR-0014's certified-peer requirement?

Sources of truth this quarter (rotate as the field evolves):

- **LLM models:** Artificial Analysis (TTFT, throughput, quality leaderboards), CometAPI (hallucination benchmarks), the model providers' own release pages.
- **Embeddings:** MIRACL, MTEB, the BEIR leaderboard.
- **Rerankers:** the BAAI BGE blog, Cohere's release notes, the Hugging Face cross-encoder leaderboard.
- **Vector store:** the vendors' own release notes; Particula, LeanOps, jxnl.co for empirical cost comparisons.
- **Observability:** OpenTelemetry GenAI semconv release notes, Langfuse changelog, OTel adoption among the candidate backends.

### Step 3 — Run candidates through the embedding-upgrade SOP

Any candidate that clears the screening from Step 2 enters the dual-index window per `docs/contracts/embedding-upgrade-sop.md`. Embeddings and rerankers both follow the SOP (the rerank route reads `ScoredChunk` only, so the dual-index step is per-route rather than per-corpus). LLM candidates run through the safety-suite + retrieval-eval gates per ADR-0004 §Route Certification Protocol.

### Step 4 — Produce a one-page diff

The output of the quarterly sync is a one-page Markdown report committed to `docs/runbooks/history/frontier-sync-<YYYY-Qn>.md`. The shape:

```markdown
# Frontier Sync — YYYY-Qn

## Currently certified routes (baseline)
- query_analyzer: <route_id>
- compose: <route_id>
- verifier_judge: <route_id>
- embedding: <route_id>
- rerank: <route_id>
- context_prefix: <route_id>
- edge_extraction: <route_id>
- retrieval_eval_judge: <route_id>

## Frontier candidates surveyed
- LLM: <list>
- Embedding: <list>
- Reranker: <list>
- VectorStore: <list>
- Observability backend: <list>

## Action this quarter
[ ] No action — current routes remain optimal.
[ ] Single ADR amendment: <ADR-NNNN> updating <route> from <old> to <new>.
    Rationale: <one paragraph>.
    Evidence: <link to retrieval-eval report>.

## Deferred
<list of candidates considered but not adopted; one-line reason each>
```

### Step 5 — At most one ADR amendment per quarter

The runbook constrains the output to at most one ADR amendment per cycle. The constraint is deliberate: cumulative drift is the failure mode, not absence of change. If multiple amendments seem warranted, pick the highest-impact one and defer the rest. Multiple amendments in a single cycle imply the prior cycle missed something — investigate that gap before issuing two amendments.

The amendment lands on a branch named `frontier-sync/YYYY-Qn`, goes through normal review, and references this runbook in the PR body.

## Anti-patterns to avoid

- **Treating every benchmark release as actionable.** Most do not change the certified-route decision. The retrieval-eval gold set is the only arbiter.
- **Running the sync before the retrieval-eval suite stabilizes.** If retrieval-eval is still red on the baseline, fix that first; the sync is a stability operation, not a debugging operation.
- **Letting the report file rot.** If a quarter is skipped, the next iteration starts from scratch. The maintainer is responsible for scheduling.
- **Coupling the sync to the Phase-2 platform bundle (REC-025).** The platform bundle is a Phase-2-launch event; the frontier sync runs continuously. They share inputs but the cadences are different.

## References

- `docs/contracts/retrieval-eval-suite.md` — the gating mechanism for every candidate.
- `docs/contracts/embedding-upgrade-sop.md` — the dual-index protocol candidates run through.
- ADR-0004 — the route certification protocol any LLM/reranker candidate must pass.
- ADR-0014 — the cross-provider failover ADR, which itself is subject to quarterly review (e.g., circuit-breaker thresholds may need retuning).
- 2026-05-22 frontier meta-evaluation — REC-024.
