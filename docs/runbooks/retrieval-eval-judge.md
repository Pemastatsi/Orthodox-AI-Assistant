# Runbook: Paid LLM-Judge Retrieval-Eval Run

Status: Canonical
Date: 2026-05-30
Owner: Owner / Founder (paid; egress of query + evidence text to the judge route).

This runbook is the operator procedure for **gated item #4**: running the Ragas-style LLM-judge
answer-quality metrics (faithfulness, answer_relevancy, context_precision, context_recall) that
augment the deterministic retrieval metrics. It is **PAID and OFF BY DEFAULT** — the judge never
runs in CI or in a default operator run; this runbook is what deliberately turns it on.

## Why it's gated

- **Cost.** One judge call per (case, route) where retrieval succeeded. A ~50-case gold set across
  three configs is ~150 judge calls per gating run — a few cents on Haiku-class models, but real
  spend that must not happen on every commit (`retrieval-eval-suite.md` §CI Integration).
- **Egress.** Judge calls send the user query and admitted-evidence text to the judge route — the
  same egress profile as A5 composition, subject to the same closed-corpus-egress review.
- **A deferred dependency.** `deepeval` (REC-019) is not installed. The judge module imports it
  lazily so the default suite stays free and offline; installing it is a gated action.

## Pre-conditions (ALL must hold)

1. **A certified `retrieval_eval_judge` route.** `purpose='retrieval_eval_judge'`,
   `certification_status IN ('certified','experiment')`. The judge is intentionally a different
   model family from A5 (`retrieval-eval-suite.md` §Answer Quality Metrics) — `anthropic:claude-haiku-4-5`
   is the leading candidate. Running the judge against an unapproved route is forbidden
   (§Forbidden Patterns).
2. **`deepeval` installed.** Add it to a dev/eval dependency group and `uv sync`. DeepEval cloud
   telemetry/login stays disabled — never run `deepeval login`, never set `CONFIDENT_API_KEY`
   (gold sets and chunk text must not leave the private remote).
3. **The opt-in env var set:** `RETRIEVAL_EVAL_RUN_JUDGE=1`. Both this **and** an importable
   `deepeval` are required — `judge.judge_metrics_enabled()` returns `False` otherwise, and
   `runner.run_eval` leaves `judge_applied=False`.
4. **Judge inputs available.** The judge scores A5-composed answers against admitted evidence, so a
   run that requests the judge must supply `judge_cases` (composed answers + retrieved/expected
   contexts) and a `judge_model`. `run_eval` raises if `--judge`'s gate is open but these are
   missing — this is deliberate: the judge is not a free rerun of retrieval.

## Procedure

1. Provision + certify the `retrieval_eval_judge` route (this runbook's sibling,
   `retrieval-eval-certification.md`, is the certification mechanism; the judge route's own gates
   apply).
2. Install `deepeval` and set the env flag:

   ```bash
   cd backend
   # add deepeval to the eval dependency group, then:
   uv sync
   export RETRIEVAL_EVAL_RUN_JUDGE=1
   ```

3. Run with `--judge`. Batch mode (REC-020) submits Anthropic judge calls through the Batch API for
   the 50% discount / 24h window — Batch is NEVER used on the user-facing answer path.

   ```bash
   uv run python ../scripts/run_retrieval_eval.py \
       --gold-set <tenant>/<version> --route-id <route> \
       --config hybrid --collection <backfilled_collection> \
       --persist --judge --initiated-by <owner_user_id>
   ```

   The resulting `retrieval_eval_runs` row carries `judge_applied=true` and the four judge metrics
   merged into `scores`. The pass gate then includes those metrics against the baseline.

## Safety / cost guardrails

- **Confirm budget before running** — judge spend is real (CLAUDE.md §10). Use the smallest gold set
  that exercises the path first.
- **Redaction.** Sensitive-tier cases carry their `sensitivityPrimary`; the judge run applies the
  same redaction rules as production egress.
- **Off by default everywhere else.** Unset `RETRIEVAL_EVAL_RUN_JUDGE` after the run so no later
  invocation silently incurs cost. CI never sets it.

## What this runbook does NOT do

- It does not install `deepeval` for you, certify the judge route, or compose the A5 answers the
  judge scores — those are the owner/founder actions this runbook gates.
- It does not change the deterministic-metric pass gate; judge metrics are *added* when enabled.

## References

- `docs/contracts/retrieval-eval-suite.md` §Answer Quality Metrics, §REC-019 (DeepEval), §REC-020
  (Batch API).
- `backend/tests/retrieval_eval/judge.py` — the gated, lazily-imported judge wrapper.
- `backend/tests/retrieval_eval/runner.py` — `run_eval(judge_enabled=…)`; the gate check.
- `scripts/run_retrieval_eval.py` — the `--judge` flag.
- `docs/runbooks/retrieval-eval-certification.md` — certifying the judge route + the candidate route.
- ADR-0005 — managed-inference egress review the judge call is subject to.
