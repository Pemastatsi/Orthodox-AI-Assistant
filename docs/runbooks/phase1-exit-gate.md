# Runbook: Phase-1 → Phase-2 Exit Gate

Status: Canonical
Date: 2026-06-04
Owner: Founder (`role='owner'`) for the attestation/sign-off rows; Ops for reading the dashboard.

This is the operator procedure for driving the nine **Phase-1 → Phase-2 exit criteria** to green.
Two sibling scripts do the work:

- **`scripts/exit_criteria_dashboard.py`** — *reads* the DB and prints each criterion's current value
  vs. threshold (read-only).
- **`scripts/record_audit_event.py`** — *writes* the four `audit_entries` attestation/approval rows
  that four of the criteria are satisfied by.

By design there are **no CI→DB credentials**: a human runs the recorder after observing the relevant
CI result, and the founder runs the Phase-2 sign-off and the safety-config approval. The criteria
definitions are in `docs/contracts/phase1-implementation-contract.md`; the executable thresholds live
in the dashboard.

## Read current status

```bash
python scripts/exit_criteria_dashboard.py --db-url postgresql://user:pass@host/db
```

Prints a 9-row table and exits `0` if **all** pass (gate open), `1` if any are unmet, `2` if it
cannot connect.

## Recorder basics

Every `record_audit_event.py` subcommand needs `--db-url`, plus `--tenant` and `--actor-user` that
**reference existing rows** (`audit_entries.tenant_id`/`actor_user_id` are FKs). Use the Orthodox
Ethos tenant and the founder/owner user (e.g. `tn_orthodoxethos` / `usr_founder`); `--actor-role`
defaults to `owner`. Add `--dry-run` to print the row JSON without writing (and without a DB).

## The nine criteria

| # | Criterion | Threshold | How to satisfy |
|---|-----------|-----------|----------------|
| 1 | Safety-suite stability | a passing attestation ≤ 30 days old | After the `safety-suite-execution` check is green on `main`, **record it** (below). |
| 2 | Internal traffic | ≥ 50 distinct served queries | Accrues from real usage (`run_traces` with `finished_at` + `final_handling`). No recorder — read the dashboard. |
| 3 | RED rate | ≤ 30% over 7 days | Accrues from usage (hard blocks excluded). Read the dashboard. |
| 4 | Latency | p95 < 8000 ms over 7 days | Accrues from usage. Read the dashboard. |
| 5 | Tenant isolation | last CI result = pass | After the tenant-isolation suite is green, **record it** (below). |
| 6 | Founder review | ≥ 1 valid owner sign-off | Founder reviews ≥ 20 runs across ≥ 3 sensitivity categories, then **records the sign-off** (below). |
| 7 | Corpus health | ≥ 100 approved chunks, ≥ 5 sources (`tn_orthodoxethos`) | Ingest + approve corpus via the admin corpus-approval flow (`PATCH /api/v1/corpus/{chunkId}`). Read the dashboard. |
| 8 | Operational basics | run traces + a billing period + retention sweep | Retention: the **retention worker** writes the `retention_purged` row (see `docs/runbooks/retention-worker.md`). Billing: a `billing_usage` row with `served_answer_count > 0` **and** `stripe_usage_record_id` set (accrues from real Stripe-metered served answers). Traces: ≥ 1 `run_traces` row. |
| 9 | Real safety configs | config `version` ≠ `2026-05-01.1` | Founder completes **T-007** (real `sensitivity_keywords.yaml` + `pastoral_filters.yaml`), then **records approval** (below). The production startup guard also refuses to boot on the stub version. |

### Commands for the human-recorded criteria

```bash
# #1 — after `safety-suite-execution` is green on main (freshness window: 30 days)
python scripts/record_audit_event.py safety-suite-passed \
    --db-url "$DB" --tenant tn_orthodoxethos --actor-user usr_founder \
    --passed --commit <main_sha>

# #5 — after the tenant-isolation suite is green
python scripts/record_audit_event.py tenant-isolation-passed \
    --db-url "$DB" --tenant tn_orthodoxethos --actor-user usr_founder \
    --result pass --commit <main_sha>

# #6 — founder sign-off (owner; >=20 reviewed runs, >=3 distinct categories)
python scripts/record_audit_event.py founder-signoff \
    --db-url "$DB" --tenant tn_orthodoxethos --actor-user usr_founder --actor-role owner \
    --reviewed-run-ids run_a,run_b,...,run_t \
    --sensitivity-categories pastoral_advice,political,medical

# #9 — founder approval of the real safety configs (auto-hashes both YAMLs)
python scripts/record_audit_event.py safety-config-approved \
    --db-url "$DB" --tenant tn_orthodoxethos --actor-user usr_founder
```

`safety-config-approved` reads `config/sensitivity_keywords.yaml` and `config/pastoral_filters.yaml`
by default (override with `--sensitivity-keywords` / `--pastoral-filters`) and records each file's
`version` + SHA-256 into `details`. `founder-signoff` validates the `owner` role and the ≥20-run /
≥3-category thresholds before writing.

## What this gate does NOT do

- It does not generate traffic (#2/#3/#4), ingest corpus (#7), or meter billing (#8 billing
  sub-check) — those accrue from real product usage.
- It does not author the safety configs (#9 / T-007) — that is founder, non-coding work.
- It does not wire CI to write attestations — recording is a deliberate human step, by design.

## References

- `scripts/exit_criteria_dashboard.py` — the read-side (thresholds per criterion).
- `scripts/record_audit_event.py` — the write-side (the four attestation/approval subcommands).
- `docs/contracts/phase1-implementation-contract.md` — the canonical criteria + #1 freshness amendment.
- `docs/runbooks/retention-worker.md` — the #8 retention sub-check.
- `docs/task_cards/phase1/T-007-real-safety-configs.md` — the #9 founder task.
