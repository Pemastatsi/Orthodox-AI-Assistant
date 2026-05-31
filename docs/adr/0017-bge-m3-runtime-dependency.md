# ADR 0017: BGE-M3 Runtime Dependency — Local Weights vs Hosted Route

Date: 2026-05-30
Status: Proposed (decision deferred to owner — see §Decision)

## Context

T-009 Phase-A opened the dual-index embedding benchmark (REC-008, `embedding-upgrade-sop.md`
§REC-008) comparing two candidates against the certified Phase-1 baseline
`openai:text-embedding-3-small`:

- **`openai:text-embedding-3-large`** — managed API, 3072d Matryoshka. Already runnable: the
  `OpenAIProvider` embedding seam handles it today, and the operationalized retrieval-eval runner
  (`tests/retrieval_eval/runner.py::build_live_harness`) constructs a live harness for it with no
  new dependency.
- **`bge:bge-m3`** — BAAI BGE-M3 (Apache-2.0, open-weight): unifies dense + sparse + ColBERT
  multi-vector in one model, 8192-token context (which would unlock REC-014 late chunking and
  REC-015 ColBERT as a third retrieval signal). Migration `0004_embedding_candidates` seeds the
  `bge:bge-m3` route as `experiment` and widens the provider CHECK to include `bge`, but **nothing
  instantiates a bge provider** — `build_live_harness` raises `NotImplementedError` for it, and the
  backfill driver refuses it, both pointing here.

The blocker is a **runtime dependency decision** that this ADR exists to frame and the owner exists
to make. BGE-M3 is not reachable from the current dependency set; making it reachable is a
non-trivial, partly irreversible commitment (image size, egress posture, ops surface). Per
`CLAUDE.md` §5, adding a heavy dependency is High-risk and installing it is gated — so the decision
is recorded *before* any dependency lands, mirroring ADR-0012's "cheapest moment to commit is before
the seam is consumed."

This ADR does **not** pick the embedding winner — that is the retrieval-eval gate's job
(`retrieval-eval-suite.md`), run per candidate once each is runnable. It decides only *how BGE-M3
becomes runnable at all*, so the benchmark can include it.

## Options

### Option A — Local weights (`FlagEmbedding` / `sentence-transformers`)

Run BGE-M3 in-process in the ingestion worker (and in a live retrieval-eval harness), loading the
~2.3GB model weights.

- **Pros:** No third-party egress — chunk text never leaves the deployment, the strongest
  closed-corpus posture (matches the `BgeRerankerLocal` precedent in ADR-0012, which already chose
  local weights for the reranker). No per-call API cost. Unlocks the dense + sparse + ColBERT
  unification natively (one model retires three routes; REC-008's upside).
- **Cons:** ~2.3GB added to the image / a model cache volume; meaningful cold-start and memory
  footprint in the ingestion worker; realistically wants a GPU (or a slow CPU path) for backfill at
  corpus scale; adds `FlagEmbedding`/`sentence-transformers` (heavy, torch-transitive) to the
  dependency tree. This is the largest single dependency the project would carry.

### Option B — Hosted route (managed BGE-M3 inference)

Reach BGE-M3 through a hosted inference API (e.g. a managed embeddings endpoint or a self-hosted
Modal/Replicate-style deployment), behind the same provider seam as OpenAI.

- **Pros:** Keeps the application image light; no in-process torch; no GPU in the app tier. Same
  adapter shape as the existing `OpenAIProvider` embedding seam, so wiring is small. Scales backfill
  without local compute.
- **Cons:** Adds a third-party egress boundary — chunk text traverses an external API, which is the
  same closed-corpus-egress review any managed provider gets (ADR-0005 §egress; ADR-0012 already
  flags this for `CohereRerankerAdapter`). Per-call cost + an external availability dependency
  (ADR-0014 failover thinking applies). A self-hosted endpoint moves the 2.3GB/GPU problem to infra
  rather than removing it.

## Decision

**Deferred to the owner.** Both options are viable and the trade-off is a genuine
posture-vs-operability judgment the owner owns, not one this ADR should force. The recommendation is
intentionally left open per the founder's instruction; this ADR records the options, their
trade-offs, and the mechanics so that either choice is a small, well-scoped follow-up rather than an
open-ended research task.

Until the owner ratifies one option:

- `bge:bge-m3` stays an `experiment` route (seeded, inert). The provider CHECK already admits `bge`.
- `build_live_harness` and `run_embedding_backfill.py` raise a clear, this-ADR-referencing error for
  the bge candidate. **No bge dependency is added** to `pyproject.toml`.
- The **openai** candidate runs the full benchmark today (backfill → retrieval-eval → certify),
  so T-009 Phase-A is not blocked on this decision — only the bge arm of the comparison is.

### What ratifying a choice entails (so it's a small follow-up either way)

- **If Option A (local):** add `FlagEmbedding` (or `sentence-transformers`) to the `embedding`
  dependency group; add a `BgeM3Provider` implementing the embedding seam (`embed_texts`,
  `embedding_dimension`); wire it into `build_live_harness`/the backfill driver's provider switch;
  document the model-cache volume + GPU expectation in the SOP. ~1 adapter + 1 dep + a worker note.
- **If Option B (hosted):** add a `BgeM3HostedProvider` over the chosen endpoint (httpx, same error
  taxonomy as `OpenAIProvider`); add the endpoint URL/key to `Settings`; record the egress decision
  per ADR-0005 and the per-tenant opt-in pattern; no torch dependency. ~1 adapter + config + an
  egress note.

Either way the embedding-winner decision remains the retrieval-eval gate's, run identically for both
candidates; this ADR only removes the "bge can't run at all" blocker.

## Consequences

- The benchmark can proceed for OpenAI immediately and for BGE-M3 the moment the owner ratifies an
  option — neither requires re-litigating this decision.
- ColBERT (REC-015) and late chunking (REC-014) remain gated on a BGE-M3 win, which is itself gated
  on this dependency decision; that dependency chain is now explicit rather than implicit in code.
- No dependency, egress, or infra change happens without owner action — the safe default.

## References

- ADR-0006 §"Phase 2 Embedding Upgrade: Recommended Candidates" — the deferred decision T-009 opens.
- ADR-0011 — hybrid retrieval; BGE-M3's unified sparse signal would touch this.
- ADR-0012 — reranker selection; chose **local** BGE weights for the reranker (the Option-A
  precedent) and flags managed-API egress for the Cohere alternative (the Option-B precedent).
- ADR-0005 — managed-inference egress review that Option B triggers.
- ADR-0014 — cross-provider failover; an external embedding endpoint is subject to it.
- `docs/contracts/embedding-upgrade-sop.md` §REC-008 — the dual-index benchmark this unblocks.
- `docs/task_cards/phase1/T-009-embedding-upgrade.md` — Phase-A/B/C sequencing that gates on the
  winner.
- `backend/app/alembic/versions/0004_embedding_candidates.py` — seeds the inert `bge:bge-m3` route.
- `docs/contracts/approved-decisions-register.md` row D-EMB-001.
