# Runbook: Retention Worker (expired sensitive-log sweep)

Status: Canonical
Date: 2026-06-04
Owner: Engineering for local/dev; Ops/Founder for production scheduling.

The retention worker deletes expired `raw_sensitive_logs` rows on a schedule and writes the
`audit_entries.action='retention_purged'` row that Phase-1→2 **exit criterion #8** reads. It is an
[arq](https://arq-docs.helpmanual.io/) cron job; the task lives in
`backend/app/workers/tasks/retention_cleanup.py` and is scheduled by `WorkerSettings` in
`backend/app/workers/retention_worker.py`.

## What it does (per run)

- Deletes `raw_sensitive_logs` whose TTL has expired (`RawSensitiveLogRepository.delete_expired`).
- Emits `worker.retention.started`, then `worker.retention.completed` (carrying `deleted_count` and
  `next_run_at`), or `worker.retention.failed` on error.
- Writes **one** `audit_entries` row in the **same transaction** as the delete — on **every** run,
  even when `deleted_count == 0` — so #8 is observable on each sweep and a purge can never land
  without its audit trail:

  | field | value |
  |-------|-------|
  | `action` | `retention_purged` |
  | `resource_type` | `raw_sensitive_logs` |
  | `resource_id` | `retention_sweep` |
  | `actor_role` | `system` |
  | `tenant_id` / `actor_user_id` | `tn_system` / `usr_system` (the platform **system principal**, seeded by migration `0006_system_principal`) |
  | `details` | `{"deleted_count": <int>, "next_run_at": "<ISO-8601>"}` |

The sweep is cross-tenant, so it connects as `app_admin` (BYPASSRLS, ADR-0016 Rule 5) and is
attributed to the dedicated system principal rather than any customer tenant.

## Configuration

| Setting | Env var | Default | Notes |
|---------|---------|---------|-------|
| DB connection | `DATABASE_ADMIN_URL` → falls back to `DATABASE_URL` | — | `on_startup` calls `init_engine(admin=True)` for the cross-tenant sweep. |
| Redis (arq broker) | `REDIS_URL` | — | arq populates `redis_settings` from `settings.redis_url`. |
| Schedule | `RETENTION_WORKER_CRON` | `5 * * * *` | Phase-1 supports the `M * * * *` form only (minute `M` of every hour); fuller cron is Phase-2 (`croniter`). |

## Run it locally

The compose deps must be up and migrations applied first (the system principal is seeded by
migration `0006`):

```bash
make up          # postgres + qdrant + redis (infrastructure/docker-compose.yml)
make migrate     # alembic upgrade head  (seeds tn_system / usr_system)
make worker      # cd backend && uv run arq app.workers.retention_worker.WorkerSettings
```

`make dev` also starts the worker automatically alongside uvicorn + web. On startup arq logs the
registered `retention_cleanup_task` cron; with the default cron it next fires at minute 5 of the
hour.

### Force a one-off sweep (testing)

The default cron means you may wait up to an hour to see a real run. To exercise it now, either:

- **Override the schedule** to the current minute and start the worker:
  ```bash
  RETENTION_WORKER_CRON="<current-minute> * * * *" make worker
  ```
- **Run the integration test**, which calls `run_retention_cleanup(...)` directly against the test DB
  and asserts the `retention_purged` row (no arq needed):
  ```bash
  cd backend && uv run pytest tests/integration/test_retention_worker.py -q
  ```

## Verify the audit row

```sql
SELECT occurred_at, details->>'deleted_count' AS deleted, details->>'next_run_at' AS next_run
FROM audit_entries
WHERE action = 'retention_purged'
ORDER BY occurred_at DESC
LIMIT 5;
```

A row here is exactly what `scripts/exit_criteria_dashboard.py::criterion_8_operational_basics`
checks for the retention sub-check (see `docs/runbooks/phase1-exit-gate.md`).

## Production (Railway)

`infrastructure/railway.toml` defines a `retention-worker` service that **reuses**
`infrastructure/Dockerfile.backend` and overrides the start command to
`arq app.workers.retention_worker.WorkerSettings` (`restartPolicyType = "ON_FAILURE"`, no
healthcheck — it is not an HTTP service). Attach the **same env as the `backend` service** in the
Railway dashboard: `DATABASE_ADMIN_URL` (or `DATABASE_URL`), `REDIS_URL`, and optionally
`RETENTION_WORKER_CRON`. Deploying / attaching env is a founder/ops action.

## References

- `backend/app/workers/retention_worker.py` — arq `WorkerSettings` (schedule + admin engine).
- `backend/app/workers/tasks/retention_cleanup.py` — the sweep + audit row (the #8 contract).
- `backend/app/alembic/versions/0006_system_principal.py` — seeds `tn_system` / `usr_system`.
- `backend/tests/integration/test_retention_worker.py` — behavioral proof (runs in CI).
- `docs/runbooks/phase1-exit-gate.md` — how #8 fits the full exit-criteria gate.
