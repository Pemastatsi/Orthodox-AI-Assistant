# Runbook: Retrieval-Eval Run → Certify an Embedding/Rerank Route

Status: Canonical
Date: 2026-05-30
Owner: Owner (certification + baseline establishment are owner-only actions).

This runbook is the operator procedure for **gated item #5**: running a candidate embedding/rerank
route's retrieval-eval, persisting it, attaching it to the route, establishing the baseline, and
certifying. It composes the operationalized pieces (T-009 Phase-A) into the closed loop the founder
drives. It is the retrieval-eval counterpart to `embedding-upgrade-sop.md` §Stage 3.

Every paid/owner step is explicit. The free, offline parts run anywhere; the gated parts need the
corpus DB, Qdrant, API budget, and owner authority.

## Pre-conditions

1. A candidate route exists (`model_routes`, `certification_status='experiment'`) — migration 0004
   seeds the two T-009 embedding candidates.
2. A **validated** gold set exists for the tenant (`scripts/validate_gold_set.py --check-corpus`
   passes — see `tests/retrieval_eval/gold_sets/CURATION.md`, gated item #1).
3. For a **live** run: the candidate's dual-index collection is backfilled
   (`embedding-upgrade-sop.md` §Stage 2 / `scripts/run_embedding_backfill.py --execute`, gated
   item #3). For the **offline** smoke path none of this is needed.
4. A passing **safety-suite run** row exists for the route (`safety_suite_runs`) — T-006's harness
   domain. Certification needs both gates.

## Step 1 — Run + persist the retrieval-eval

Offline smoke (free; proves the loop without spend):

```bash
cd backend
uv run python ../scripts/run_retrieval_eval.py \
    --offline --gold-set tenant_smoke/2026-05-29.1 \
    --route-id embedding_openai_large@2026-05-29.1 --persist
```

Live candidate run (paid embedding calls over the backfilled collection; founder action):

```bash
cd backend
uv run python ../scripts/run_retrieval_eval.py \
    --gold-set tn_orthodoxethos/2026-05-29.1 \
    --route-id embedding_openai_large@2026-05-29.1 \
    --config hybrid --collection chunks_cand_large --persist
```

The command prints a per-metric report vs. baseline and writes one `retrieval_eval_runs` row
(`--persist`). A **failing** run stops here — diagnose against the baseline before re-running.

## Step 2 — Establish the baseline (owner, first version only)

The first passing run on a new gold-set version establishes the baseline. This is an **owner-only**
deliberate action (it mirrors `ModelRoute` certification authority; baselines are never auto-updated
on improvement):

```bash
cd backend
uv run python ../scripts/run_retrieval_eval.py \
    --offline --gold-set <tenant>/<version> --route-id <route> \
    --establish-baseline --initiated-by <owner_user_id>
```

This writes `tests/retrieval_eval/baselines/<tenant>.json`. A real tenant baseline is
**Confidential** (same tier as the gold set). Once set, the version is frozen; later changes ship as
a new version, and a new run is only ever compared against the baseline for its *own* version.

## Step 3 — Attach the passing runs to the route (owner, both gates)

Certification requires **both** `model_routes.safety_suite_run_id` and `retrieval_eval_run_id` set.
Attach the retrieval-eval run (and the safety run, if not already linked) in one owner command:

```bash
cd backend
uv run python ../scripts/run_retrieval_eval.py \
    --gold-set <tenant>/<version> --route-id <route> \
    --persist --attach --safety-run-id <ssr_id> --initiated-by <owner_user_id>
```

`--attach` refuses a failing run (the gate would never certify). Under the hood it calls
`ModelRouteRepository.attach_retrieval_eval_run` and, with `--safety-run-id`,
`attach_safety_suite_run`. Equivalently, an operator may call those repo methods directly.

## Step 4 — Certify (owner PATCH)

With both gates linked and passing, the owner promotes the route:

```bash
curl -X PATCH https://<host>/api/v1/admin/model-routes/<route>/certify \
    -H 'Authorization: <owner credential>' \
    -H 'Content-Type: application/json' \
    -d '{"certificationNotes": "Both gates green on <version>."}'
```

The endpoint (`PATCH /api/v1/admin/model-routes/{routeId}/certify`, owner scope `model_route:certify`)
re-verifies each linked run passed, sets `certification_status='certified'`, and records an
`audit_entries.action='model_route_certified'` row carrying both gate run ids. It returns:

- **200** — certified (the response body is the updated route).
- **403** — caller is not an owner.
- **404** — route not found.
- **409** `route_not_certifiable` — a gate is unlinked or its run did not pass, or the route is
  already certified / deprecated.

## Step 5 — Cutover

Certification makes a route *eligible*; cutover makes it *active*. Follow
`embedding-upgrade-sop.md` §Stage 4 (Phase 1: update the env-pinned route + redeploy; the cache
self-invalidates via `model_route_version` in the cache key). Rollback and decommission are SOP
§Stage 5 / §Stage 6.

## What this runbook does NOT do

- It does not curate the gold set (item #1 — `CURATION.md`), run the paid backfill (item #3 — the
  SOP / backfill driver), or run the paid LLM judge (item #4 — `retrieval-eval-judge.md`).
- It does not auto-update a baseline on improvement (owner-only, deliberate).
- It does not bypass either gate — the endpoint enforces both regardless of how runs were attached.

## References

- `docs/contracts/retrieval-eval-suite.md` — the gate definition + pass rule.
- `docs/contracts/embedding-upgrade-sop.md` — Stage 2 backfill / Stage 4 cutover / Stage 5–6.
- `scripts/run_retrieval_eval.py` — the operator CLI this runbook drives.
- `scripts/validate_gold_set.py` — gold-set pre-flight (item #1).
- `scripts/run_embedding_backfill.py` — the Stage-2 backfill (item #3).
- ADR-0004 — route certification protocol; the cert endpoint enforces it.
- `docs/runbooks/retrieval-eval-judge.md` — the paid judge path (item #4).
