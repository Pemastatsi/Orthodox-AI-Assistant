# Embedding Model Upgrade SOP

Status: Canonical
Date: 2026-05-19

This document is the operating procedure for upgrading the active embedding model. It
satisfies approved-decisions-register row 17 ("Document and test embedding model upgrade
procedure") and is the runbook ADR-0006 §Phase 2 Embedding Upgrade promises. ADR-0011
(hybrid retrieval) and ADR-0013 (collection topology) constrain it; the route
certification protocol in ADR-0004 gates it.

## Why this exists as a separate doc

The naive answer to "upgrade the embedding model" is "re-embed and switch." That answer
loses tenant data, breaks `idx_chunks_tenant_approved` lookups during the migration, can
silently degrade retrieval quality below the previous baseline, and gives the founder
no audit trail. None of those failure modes are acceptable for a closed-corpus
theological system whose primary product promise is traceability.

The SOP is **dual-index + backfill + certify + cutover**. Every step is reversible up
to the cutover; the cutover itself is a single atomic config change with a documented
rollback.

## Pre-conditions (must all hold before starting)

1. **Schema fields already exist.** `chunks.embedding_model` (text, NOT NULL),
   `chunks.embedding_dimension` (integer, NOT NULL), and the `ChunkPayload.embedding_model`
   field in `vector-store-interface.md`. (Phase 1 ships these — verify, don't add.)
2. **`embeddingModel` value format is `<provider>:<model>@<snapshot>`.** Examples:
   `openai:text-embedding-3-small@2024-03`, `openai:text-embedding-3-large@2024-03`,
   `voyage:voyage-multilingual-2@2024-09`. The snapshot suffix is **mandatory**, even
   when the provider does not currently publish dated snapshots — record the date the
   route was certified.
3. **A `ModelRoute` row exists for the target model** with `purpose='embedding'` and
   `certification_status='draft'`. Seed via Alembic data migration or the admin tool;
   do not write to `model_routes` from ad-hoc psql sessions.
4. **A retrieval-eval gold set exists for the affected tenant(s)** under
   `tests/retrieval_eval/gold_sets/<tenant_id>/<version>.json`, anchored on stable
   `chunk_id` values per `retrieval-eval-suite.md`. If a tenant has no gold set, **the
   upgrade does not run for that tenant** — gold set creation is a prerequisite, not a
   step.
5. **Founder sign-off** is recorded as an `audit_entries.action = 'embedding_upgrade_proposed'`
   row with the proposed model, dimension, snapshot, and rationale in `details`.
   Per CLAUDE.md §5, this is a High-risk operation; founder approval is non-negotiable.
6. **Disk + Qdrant capacity headroom.** The dual-index step doubles vector storage for
   the duration of the upgrade. Confirm Railway/Qdrant quotas before starting.

## Stage 1 — Provision the second index (dual-index)

### Step 1.1 — Add a second collection (or named vector) in Qdrant

Per ADR-0013 §Decision, the Phase 1 topology is one shared `chunks` collection. The
upgrade introduces a parallel space:

- **Option A (preferred for embedding-only upgrades):** add a second named dense vector
  to the existing collection (e.g. `dense_v2`). The original named vector (`dense_v1`)
  continues to serve production until cutover.
- **Option B (required when changing distance metric, sparse model, or payload index
  structure):** create a second collection (e.g. `chunks_v2`) with the new
  configuration. Both collections share the same payload-filter contract from ADR-0013.

Record the chosen option in the founder sign-off audit row. Both options are reversible
at this stage by deleting the new vector / collection.

### Step 1.2 — Verify dimension consistency

The new model's embedding dimension is recorded in the new `ModelRoute` row. The Qdrant
named-vector or collection is provisioned at that dimension. The
`VectorStoreInvalidDimensionError` boot check (per `vector-store-interface.md`) MUST
NOT fire — if it does, the new collection was provisioned wrong.

## Stage 2 — Backfill the new index

### Step 2.1 — Run the backfill worker

A worker (`workers/tasks/embedding_backfill.py`) re-embeds every approved chunk for the
target tenant(s) under the new `ModelRoute` and `upsert`s into the new named vector or
collection. The worker:

- Iterates chunks in `chunks.created_at` order, scoped to the target tenant(s) and
  `approved = true`.
- Reads the canonical chunk text from Postgres (not from the existing vector payload).
- Calls the new provider's embedding API, retrying with exponential backoff per
  `provider-interface.md`.
- Writes the new `ChunkPayload` with `embedding_model = "<provider>:<model>@<snapshot>"`
  matching the new `ModelRoute.routeId`.
- Emits structured progress (`embedding_backfill_progress` log event) every 100 chunks
  so a dashboard can show backfill state without scraping Qdrant.

### Step 2.2 — Verify backfill completeness

After the worker drains, the following invariants MUST hold (assert via SQL + Qdrant
scroll, recorded in the same audit row):

- `SELECT COUNT(*) FROM chunks WHERE tenant_id IN (...) AND approved = true` equals the
  count of points in the new named vector / collection under the same tenant filter.
- For every sampled chunk (uniform-random 50 per tenant), the new payload's
  `embedding_model`, `embedding_dimension`, and `chunk_id` match the Postgres row.

A failed invariant blocks the upgrade. Re-run the backfill for the missing chunks; do
not proceed to Stage 3 with a partial index.

## Stage 3 — Certify the new route

### Step 3.1 — Run the retrieval-eval gate

Per `retrieval-eval-suite.md` and approved-decisions-register row D-EVAL-001:

- Execute the per-tenant gold set against the new index.
- Collect deterministic metrics (Recall@K, Precision@K, MRR, nDCG@K at K∈{6,12,20}) and
  the Ragas-style LLM-judge metrics (faithfulness, answer_relevancy, context_precision,
  context_recall).
- **Pass rule:** every metric ≥ baseline − 0.02 for the active gold-set version.
- Record the run as `retrieval_eval_runs.<run_id>` with a pointer from the
  `model_routes.retrieval_eval_run_id` column.

### Step 3.2 — Run the safety-suite gate

Per ADR-0004:

- Execute `tests/safety/test_20_queries.py` and `tests/safety/test_20_queries_paraphrases.py`
  with the new embedding route active in a staging configuration.
- All 20 canonical cases plus all generated paraphrases must produce the expected
  `handling` and `sensitivityPrimary`.
- Record the run as `safety_suite_runs.<run_id>` with a pointer from the
  `model_routes.safety_suite_run_id` column.

### Step 3.3 — Promote to certified

Once both gates pass, the `ModelRoute` row is updated:
`certification_status = 'experiment' → 'certified'`. This change is itself an
`audit_entries.action = 'model_route_certified'` row carrying both gate run IDs.

A failed gate at any sub-step blocks promotion. The new index remains parked; either
re-run the backfill against a different model, or roll back per Stage 5.

## Stage 4 — Cutover

The cutover is a single atomic change: the active embedding route for the affected
tenant(s) is switched from the old `ModelRoute.routeId` to the new one. Concretely:

- For tenant-scoped routing (Phase 2+ when `model_routes.tenant_scope` is added): update
  the active row.
- For Phase 1 global routing: update the env-var-pinned route in `app/core/config.py`
  and redeploy. The redeploy is the cutover.

After cutover:

- A3 retrieval reads from the new named vector / collection.
- All new chunks ingested through `workers/tasks/ingestion.py` embed under the new route
  by virtue of the route being the certified-active embedding route.
- The response cache (per `cache-key.md`) is **fully invalidated** for affected tenants
  because `model_route_version` is part of the cache key. No manual cache flush needed.

Record the cutover as `audit_entries.action = 'embedding_upgrade_cutover'` with the
old and new `routeId` values and the timestamp.

## Stage 5 — Rollback

Rollback is the cutover in reverse. Concretely:

- Switch the active embedding route back to the old `ModelRoute.routeId`.
- Redeploy.
- The cache invalidates again (new `model_route_version`).

The old named vector / collection is **preserved for one retention window** (configurable
per `phase1-implementation-contract.md`; default 14 days post-cutover). Until that
window expires, rollback is a single env change. After it expires, rollback requires
re-running Stages 1–4 against the previous model.

Record the rollback as `audit_entries.action = 'embedding_upgrade_rollback'` with the
reason and the diagnostic data.

## Stage 6 — Decommission the old index

After the old index has been parked for the retention window and no rollback has been
needed, the old named vector / collection is deleted via
`workers/tasks/embedding_backfill_decommission.py` (or a one-shot admin command). The
deletion is gated by:

- The new route's `certification_status = 'certified'` AND `cutover_at > now() - retention_window`.
- A second founder sign-off (`audit_entries.action = 'embedding_upgrade_decommission_approved'`).
- A final invariant check that no chunk under the affected tenant(s) still has a
  payload referencing the old `embedding_model` value.

A failed invariant blocks decommissioning. Old payloads referencing the old model must
be either re-backfilled under the new route or explicitly deleted before decommission
proceeds.

## Pinning the snapshot

Embedding APIs change beneath their endpoint names. OpenAI shipped
`text-embedding-3-small` in January 2024 and has since shipped server-side dimension
trimming, encoding-format changes, and (per provider documentation) silent behavior
changes that do not change the model name.

The `<provider>:<model>@<snapshot>` format requires the snapshot suffix even when the
provider does not publish dated snapshots, because:

1. The exact route certification (Stage 3) was against a specific provider build. If
   the provider silently changes the build, retrieval quality may drift below the
   `baseline − 0.02` floor that this SOP relies on.
2. Re-running the retrieval-eval suite on a quarterly cadence catches drift early. The
   `<snapshot>` field is the version of *the validation*, not necessarily of the
   underlying API.
3. The chunk payload carries the same snapshot, so a future re-embed against a different
   snapshot is detectable at the per-chunk level.

Default snapshot policy for Phase 1: **the current month, YYYY-MM, recorded at route
certification time.** The retrieval-eval suite re-runs at least quarterly under
`docs/contracts/retrieval-eval-suite.md` cadence; a re-run that passes is recorded as
a new `safety_suite_run_id` and `retrieval_eval_run_id` against the same route, with no
chunk re-embed needed. A re-run that fails the `baseline − 0.02` floor triggers this
SOP under a new snapshot.

## Embedding input contract — Contextual Retrieval prefix

When `Chunk.contextPrefix` is set (ADR-0009 Step 4), the embedding input is
`contextPrefix + "\n\n" + text`, not `text` alone. The same concatenation is fed
to the sparse (BM25) index so the contextual signal is symmetric across signals.
Backfill workers (Stage 2) MUST honor this rule: a re-embed pass that ignores
`contextPrefix` would silently degrade retrieval quality relative to the
ingestion-time embeddings.

Toggling Contextual Retrieval on or off for a tenant is a `corpusVersion` bump:
the new vectors are not comparable to the old ones, the cache key changes (see
`cache-key.md`), and a full re-embed is required. The dual-index window
described above is the canonical mechanism for that re-embed.

## REC-008 dual-index benchmark — BGE-M3 vs text-embedding-3-large vs current baseline

REC-008 (frontier meta-evaluation 2026-05-22) opens a Phase-1 dual-index window
comparing two embedding-model candidates against the certified
`openai:text-embedding-3-small` baseline:

- **BGE-M3** (Apache-2.0, open-weight) — unifies dense + sparse + ColBERT in
  one model; 8192-token context unlocks late chunking (see below). Winning BGE-M3
  retires three separate ModelRoutes and also unlocks REC-015 (ColBERT 3rd
  retrieval signal) at no additional cost.
- **text-embedding-3-large** (managed, OpenAI) — 3072d Matryoshka; +10.9 MIRACL
  points over the current baseline. Does NOT unlock late chunking (the long-doc
  context window is not large enough for Patristic chapters).

Both candidates run through this SOP unchanged: dual-index, backfill, retrieval-
eval and safety-suite gates, owner certification, cutover. The decision criteria
and timeline are recorded in `docs/task_cards/phase1/T-009-embedding-upgrade.md`.

## Late chunking — gated activation

Late chunking (Jina 2024-09, arXiv:2409.04701) — embed the whole source document
with a long-context model, then segment the embedding stream into chunks —
preserves long-range Patristic argument coherence inside each chunk vector.
Text boundaries are unchanged, so A6 quote-overlap is unaffected.

Late chunking activates only after the dual-index benchmark above selects an
embedding model whose context window can hold an entire source document (BGE-M3
qualifies; `text-embedding-3-large` does not without sharding). Activation
bumps `corpusVersion` and triggers a full re-embed under this SOP. Until
activation, the chunking service emits per-chunk embeddings as today.

## What this SOP does NOT cover

- **Reranker upgrades.** The reranker reads `ScoredChunk` objects, not embeddings, so a
  reranker swap is a `Reranker` Protocol implementation change plus a route certification.
  See ADR-0012.
- **Sparse model upgrades.** Phase 1 uses BM25 via Qdrant FastEmbed (ADR-0011). Swapping
  to BM42 / SPLADE / a custom sparse model follows the same dual-index + certify + cutover
  pattern, but the named sparse vector is `sparse_v2` and Stage 3 runs the retrieval-eval
  suite with the new sparse signal. Promote a separate SOP doc if and when this becomes
  active work.
- **Chunking strategy changes.** Re-chunking is a different operation: it produces new
  `chunk_id` values and breaks gold-set anchoring (per `retrieval-eval-suite.md` §Gold
  Set Stability). A re-chunk requires its own SOP that includes gold-set re-anchoring
  steps.

## References

- ADR-0004 — model provider routing and route certification protocol.
- ADR-0006 — selects `text-embedding-3-small` as the Phase 1 baseline and commits to the
  Phase 2 multilingual upgrade benchmark.
- ADR-0011 — hybrid retrieval (the sparse signal is independent of this SOP).
- ADR-0013 — Qdrant collection topology that this SOP operates against.
- `docs/contracts/vector-store-interface.md` — `ChunkPayload.embedding_model` field.
- `docs/contracts/db-schema.md` §`chunks` — `embedding_model` and `embedding_dimension`
  columns.
- `docs/contracts/retrieval-eval-suite.md` — Stage 3.1 gate.
- `docs/contracts/cache-key.md` — `model_route_version` is part of the cache key, so
  cutover invalidates the cache automatically.
- `docs/contracts/approved-decisions-register.md` row 17 and row D-EVAL-001.
- `docs/schemas/chunk.schema.json` — `embeddingModel` field format.
- `docs/schemas/model-route.schema.json` — the `ModelRoute` row this SOP mutates.
- `docs/schemas/audit-entry.schema.json` — the actions this SOP records.
