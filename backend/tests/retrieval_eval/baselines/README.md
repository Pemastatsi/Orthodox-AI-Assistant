# Retrieval-eval baselines

`baselines/<tenant_id>.json` records the **last passing scores per gold-set version** for a tenant,
per `docs/contracts/retrieval-eval-suite.md` §Harness. `compare_to_baseline` (metrics.py) gates a
new run: every metric present in the baseline must score ≥ `baseline − ε` (ε defaults to `0.02`).

## Owner-only writes

Establishing or updating a baseline is a **deliberate owner-only action** — it mirrors `ModelRoute`
certification authority (the contract's pass/fail rule, "Improvement"/"First run" clauses). It is
written **only** via the owner-gated CLI path (`scripts/run_retrieval_eval.py`, which calls
`baselines.write_baseline`), never automatically from `run_eval`. A passing first run for a version
*may* establish the baseline; a later improvement does **not** auto-update it.

## Why no `tenant_smoke.json` is committed

The synthetic `tenant_smoke` gold set is a smoke fixture, not a certification gold set. Committing no
baseline for it keeps the offline run a *first run* (it passes with nothing to regress against),
which is exactly what the free `retrieval-eval-regression` CI path asserts. Real, founder-curated
tenant gold sets (e.g. Orthodox Ethos) get their baselines established here by the owner, and those
files are **Confidential** per `CLAUDE.md` §1 — same access tier as the corpus.

File shape:

```json
{
  "tenantId": "tenant_orthodox_ethos",
  "versions": {
    "2026-05-29.1": {
      "scores": { "recall_at_6": 1.0, "mrr": 1.0, "precision_at_6": 0.1667 },
      "establishedBy": "usr_founder",
      "establishedAt": "2026-05-29T12:00:00+00:00"
    }
  }
}
```
