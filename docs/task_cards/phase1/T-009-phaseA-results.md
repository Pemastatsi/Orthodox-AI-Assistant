# T-009 Phase-A — Retrieval-Eval Results & Certification Runbook

**Status:** offline gate validated ✅ · live embedding-certification **pending owner action** ⏳
**Scope of this document:** records the free, offline deterministic retrieval-eval run, and gives the
owner a precise runbook to execute the real (paid) embedding-route certification. It does **not**
certify a route — that is an owner-only decision (ADR-0004) requiring a paid backfill and infra.

Related: `docs/contracts/retrieval-eval-suite.md`, `docs/contracts/embedding-upgrade-sop.md`,
`docs/adr/0004-model-provider-routing.md`, `docs/adr/0017-bge-m3-runtime-dependency.md`,
task card `docs/task_cards/phase1/T-009-embedding-upgrade.md`.

---

## 1. Offline deterministic eval (no spend, no infra)

Command (also `make retrieval-eval-run`):

```
cd backend && uv run python ../scripts/run_retrieval_eval.py \
    --offline --gold-set tenant_smoke/2026-05-29.1 \
    --route-id embedding_openai_large@2026-05-29.1 --config dense_only
```

Result — gold set `tenant_smoke/2026-05-29.1` (6 cases), `dense_only`:

| metric          | observed | gate      |
|-----------------|----------|-----------|
| mrr             | 1.0000   | first-run |
| recall_at_6     | 1.0000   | first-run |
| recall_at_12    | 1.0000   | first-run |
| recall_at_20    | 1.0000   | first-run |
| ndcg_at_6       | 1.0000   | first-run |
| ndcg_at_12      | 1.0000   | first-run |
| ndcg_at_20      | 1.0000   | first-run |
| precision_at_6  | 0.1667   | first-run |
| precision_at_12 | 0.0833   | first-run |
| precision_at_20 | 0.0500   | first-run |

**Result: PASS (first run).** Run id `reval_01KT8R9Y7KAWGN2QVA5ZFRDGM2` was generated but **not
persisted** (no `--persist`). `backend/tests/retrieval_eval` — 43 passed.

**Interpretation.** This exercises the metric math and the pass/fail-vs-baseline gate end-to-end and
confirms they are wired correctly. The low `precision_at_K` is expected and not a regression signal:
each smoke case has a single minimally-sufficient chunk, so precision falls as K grows while
`recall_at_K`/`mrr` stay at 1.0 because the offline harness's lexical embedding trivially separates the
synthetic fixture. **It does not decide the real embedding question** — that needs a curated
production gold set plus real embeddings (below).

**No baseline committed.** Per `docs/contracts/retrieval-eval-suite.md`, a baseline is pinned only
after the owner approves the first passing **live** run. None is written here.

---

## 2. Owner live-certification runbook (paid; not executed here)

Two candidates are seeded as `experiment` routes (migration 0004), benchmarked against the certified
baseline (`text-embedding-3-small`); pass gate = **every** metric ≥ baseline − 0.02
(`docs/task_cards/phase1/T-009-embedding-upgrade.md`):

- `embedding_openai_large@2026-05-29.1` (`openai:text-embedding-3-large`) — **runnable** (paid OpenAI).
- `embedding_bge_m3@2026-05-29.1` (`bge:bge-m3`) — **blocked**, see §3.

Follow `docs/contracts/embedding-upgrade-sop.md`:

1. **Stage 1–2 — provision + backfill** the candidate index (paid; ~$10–15, corpus-dependent):
   ```
   make up && make migrate
   cd backend && uv run python ../scripts/run_embedding_backfill.py \
       --tenant-id <tenant> --route-id embedding_openai_large@2026-05-29.1 \
       --collection chunks_candidate --execute --verify
   ```
2. **Stage 3.1 — retrieval-eval gate** against a **curated** gold set (validate it first with
   `scripts/validate_gold_set.py`), persisting + attaching to the route, and linking a passing
   safety-suite run:
   ```
   make retrieval-eval-run LIVE=1 COLLECTION=chunks_candidate \
       GOLD_SET=<tenant>/<version> ROUTE_ID=embedding_openai_large@2026-05-29.1 \
       PERSIST=1 ATTACH=1 SAFETY_RUN_ID=ssr_<passing_safety_run>
   ```
3. **Stage 3.2 — safety-suite gate** (must already be green for the route).
4. **Stage 3.3 — promote (owner-only)** via the certification endpoint
   (`PATCH /api/v1/admin/model-routes/{routeId}/certify`, scope `model_route:certify`, role `owner`).
   Both gates are enforced server-side; it records `audit_entries(action='model_route_certified')`.
5. **Stage 4 — cutover**, **Stage 6 — decommission** the losing index.

Optional paid LLM-judge metrics stay gated behind `RETRIEVAL_EVAL_RUN_JUDGE=1` + `deepeval` + a
certified `retrieval_eval_judge` route (Anthropic Batch API).

---

## 3. BGE-M3 candidate is blocked (ADR-0017)

`bge:bge-m3` is not runnable until the **owner** picks a runtime (ADR-0017): local `FlagEmbedding`
(~2.3 GB weights + torch, no egress) **or** a hosted embeddings endpoint (light image, per-call egress).
Until then `build_live_harness`/`run_embedding_backfill` raise `NotImplementedError` for `bge`. After
the decision, adding the `BgeM3Provider` adapter is ~1–2 days, then it follows §2.

---

## 4. No-winner outcome

If neither candidate clears `baseline − 0.02` on every metric, "no winner" is a valid result: keep the
certified `text-embedding-3-small` baseline and **decommission the dual index per SOP Stage 6**. Record
the decision; Phase-A then ships on the current baseline and Phases B/C (late chunking, ColBERT) stay
gated on a future long-context winner.
