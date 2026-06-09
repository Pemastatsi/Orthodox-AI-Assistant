# Runbook: Private Beta Launch (Phase 1 → 2)

Status: Canonical
Date: 2026-06-09
Owner: Founder (`role='owner'`) for accounts, secrets, corpus, deploy, and sign-off; Ops for execution.

This is the **infrastructure / deployment / content** companion to `docs/runbooks/phase1-exit-gate.md`
(which is the *attestation* side). The code and contracts are Phase‑1 complete; the nine
Phase‑1 → Phase‑2 exit criteria cannot turn green until a real private beta is running. This runbook
is the sequenced path to stand one up.

> **Starting state (verified 2026-06-09):** pre‑deployment, local‑dev only. The app runs via
> `make dev`; `infrastructure/railway.toml` is configured but not instantiated; all secrets are
> `REPLACE_ME`; there is no real corpus (only `tests/fixtures/corpus/`); and **Stripe metering is not
> implemented** (no `import stripe` in the backend — schema + an unused `stripe_usage_record_id`
> only). The safety configs (`config/*.yaml`, v`2026-05-28.1`) and paraphrase suite are already real.

## Accounts to create first

- **Host** — Railway is pre‑configured (`infrastructure/railway.toml`: `backend`, `retention-worker`,
  `web`, `qdrant`). Postgres + Redis are Railway‑managed plugins attached in the dashboard.
- **Clerk** organization + the founder user (provides `clerk_org_id` / `clerk_user_id`).
- **Stripe** account with a metered‑billing product whose meter is `served_answer_count`.
- **Qdrant** (Railway service from the manifest, or Qdrant Cloud).
- **LLM provider** keys (Anthropic + OpenAI, or OpenRouter for A1/A2).
- An **AES‑256 key** (base64) for `SENSITIVE_LOG_DATA_KEY_BASE64`.

## Steps (each notes the exit criterion it unblocks)

1. **Provision data services** — Postgres 16, Redis, Qdrant (Railway plugins / Qdrant Cloud).

2. **Set environment** (see `.env.example` for the full annotated list). Production boot **guards**
   in `backend/app/main.py` will refuse to start unless these are right:
   - `APP_ENV=production` **and** `AUTH_PROVIDER=clerk` (prod refuses `AUTH_PROVIDER=dev`).
   - `AUTH_PROVIDER=clerk` requires `CLERK_JWT_ISSUER` + `CLERK_AUTHORIZED_PARTIES` (+ secret keys).
   - `SENSITIVE_LOG_DATA_KEY_BASE64` must be a valid AES‑256 key.
   - `DATABASE_URL` → the `app_runtime` role (RLS‑subject); `DATABASE_ADMIN_URL` → `app_admin`
     (BYPASSRLS, used by migrations/seeder/workers). Set `QDRANT_URL`, provider keys, `STRIPE_*`.
   - Frontend: `NEXT_PUBLIC_AUTH_MODE=clerk`, `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`,
     `NEXT_PUBLIC_API_BASE_URL=https://<backend>/api/v1`.

3. **Migrate** — `uv run alembic upgrade head` using `DATABASE_ADMIN_URL` (creates schema + the
   `app_runtime`/`app_admin` roles + RLS policies; migrations 0001–0006).

4. **Seed the tenant + owner** — `python scripts/seed_beta_tenant.py --db-url "$DATABASE_ADMIN_URL"
   --clerk-org-id <org_…> --clerk-user-id <user_…> --email <founder@…>`. Idempotent; must use the
   admin URL (RLS blocks seeding a new tenant otherwise). Creates `tn_orthodoxethos` + `usr_founder`
   (`role=owner`), which the attestation rows reference.

5. **Deploy** backend + `retention-worker` + web (Railway services from `railway.toml`).

6. **Confirm the safety gate releases** — configs are already real (v`2026-05-28.1`), so
   `assert_production_ready` will not block prod boot. Run `make check-safety-coverage` to confirm
   English coverage is complete and to see the deferred Greek (`el`) gaps
   (`other_sensitive`, `canonical_dispute_active`, `minor_protection`). Supports **#9**.

7. **Ingest + approve corpus** — load real Orthodox sources, then approve via
   `PATCH /api/v1/corpus/{chunkId}` (content_manager+; the `/admin/corpus` UI). Target **≥100 approved
   chunks across ≥5 sources**. Re‑embed if changing model: `scripts/run_embedding_backfill.py … --execute`
   (needs live Qdrant + API budget). → **#7**.

8. **Implement Stripe metering** *(missing code — the one remaining Phase‑1 engineering gap)*. After a
   served answer, record usage on the `served_answer_count` meter and persist
   `billing_usage.stripe_usage_record_id`; add the `POST /api/v1/webhooks/stripe` handler with
   signature verification. The `stripe` dependency and `billing_usage` repository already exist. → **#8**.

9. **Generate internal traffic** — serve **≥50 distinct queries over 7 days**; watch the RED rate
   (≤30%) and p95 latency (<8000 ms) via the dashboard. → **#2 / #3 / #4**.

10. **Founder review** — review **≥20 runs across ≥3 sensitivity categories** in `/admin/queries`. → **#6**.

11. **Let the retention worker run once** (`docs/runbooks/retention-worker.md`) so it writes the
    `retention_purged` row. Combined with ≥1 `run_traces` row and a metered `billing_usage` row
    (step 8). → **#8**.

12. **Record the attestations** (`docs/runbooks/phase1-exit-gate.md`, against the DB as owner):
    ```
    python scripts/record_audit_event.py safety-suite-passed     --db-url "$DB" --tenant tn_orthodoxethos --actor-user usr_founder --passed --commit <main_sha>   # #1
    python scripts/record_audit_event.py tenant-isolation-passed --db-url "$DB" --tenant tn_orthodoxethos --actor-user usr_founder --result pass --commit <main_sha> # #5
    python scripts/record_audit_event.py founder-signoff         --db-url "$DB" --tenant tn_orthodoxethos --actor-user usr_founder --reviewed-run-ids … --sensitivity-categories …  # #6
    python scripts/record_audit_event.py safety-config-approved  --db-url "$DB" --tenant tn_orthodoxethos --actor-user usr_founder   # #9
    ```

13. **Open the gate** — `python scripts/exit_criteria_dashboard.py --db-url "$DB"`. Exit 0 = all nine
    pass → Phase‑1 → Phase‑2 review can open.

## Criterion → owner quick map

| # | Criterion | Gating step | Owner |
|---|-----------|-------------|-------|
| 1 | Safety‑suite attestation | 12 (after CI green on main) | Founder/Ops |
| 2 | ≥50 internal queries | 9 | Real usage |
| 3 | RED ≤30% / 7d | 9 | Real usage |
| 4 | p95 <8s / 7d | 9 | Real usage |
| 5 | Tenant isolation | 12 (CI already green) | Founder/Ops |
| 6 | Founder review | 10 → 12 | Founder |
| 7 | ≥100 chunks / ≥5 sources | 7 | Founder (content) |
| 8 | Operational basics | 8 + 11 | Eng (Stripe code) + Ops |
| 9 | Real safety configs | done (v2026‑05‑28.1) + 12 | Founder (sign‑off) |

## Still code‑incomplete

- **Stripe metering** (step 8) is the only remaining Phase‑1 *code* gap; everything else is infra,
  content, traffic, or owner attestation. The optional deferred Greek (`el`) safety‑rule variants
  (step 6) are founder Greek‑authoring, not a launch blocker.

## References

- `docs/runbooks/phase1-exit-gate.md` — the attestation recorder + dashboard.
- `docs/runbooks/retention-worker.md` — the #8 retention sub‑check.
- `docs/contracts/phase1-implementation-contract.md` — the canonical criteria.
- `scripts/seed_beta_tenant.py`, `scripts/check_safety_coverage.py` — tooling added with this runbook.
- `infrastructure/railway.toml`, `.env.example` — deploy manifest + env reference.
