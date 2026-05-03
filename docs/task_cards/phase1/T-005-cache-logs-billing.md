# T-005: Cache, Logs, Usage, Privacy

## Goal

Implement safe response caching, query/run logs, served-answer metering, and sensitive-log privacy.

## Required Reads

- [`AGENTS.md`](../../../AGENTS.md) — "Cache, Billing, Logs" section.
- [`docs/adr/0005-cache-billing-privacy.md`](../../adr/0005-cache-billing-privacy.md) — usage accounting + sensitive log retention.
- [`docs/contracts/cache-key.md`](../../contracts/cache-key.md) — exact algorithm + 4 SHA-256 reference vectors (V1, V2, V3, V4 — implementations must hash these to the listed values).
- [`docs/contracts/observability.md`](../../contracts/observability.md) — log line schema, redaction rules, `cache.*` and `worker.retention.*` events.
- [`docs/contracts/db-schema.md`](../../contracts/db-schema.md) — `run_traces`, `flagged_queries`, `raw_sensitive_logs`, `audit_entries`, `billing_usage` table DDL; cross-table invariants.
- [`docs/contracts/api-versioning.md`](../../contracts/api-versioning.md) — version field formats; `modelRouteId` (full id with `@YYYY-MM-DD.NN` suffix) is the cache-key field name.
- [`docs/schemas/billing-usage.schema.json`](../../schemas/billing-usage.schema.json), [`audit-entry.schema.json`](../../schemas/audit-entry.schema.json), [`run-trace.schema.json`](../../schemas/run-trace.schema.json), [`flagged-query.schema.json`](../../schemas/flagged-query.schema.json).
- [`docs/contracts/provider-interface.md`](../../contracts/provider-interface.md) — token-counting fallback affects `count_estimated` flag in run_trace.

## Files In Scope

- response cache service
- run trace tables
- query log tables
- billing usage counters
- sensitive redaction utilities
- retention worker (`workers/tasks/retention_cleanup.py`)
- audit log tests

## Acceptance Tests

- Cache key includes tenant, normalized query, role, session hash when applicable, corpus version, prompt version, model routes, schema version, and config/calendar version.
- Hashing the V1, V2, V3, V4 input dicts in `cache-key.md` produces the SHA-256 values listed there byte-for-byte.
- Cache hit increments `served_answer_count`.
- Cache hit does not increment `fresh_model_run_count`.
- Sensitive logs store redacted text by default.
- Raw sensitive text is encrypted, admin-only, audited, and retention-limited.
- The retention worker (`workers/tasks/retention_cleanup.py`) runs once in CI against a seeded `raw_sensitive_logs` row whose `expires_at < now()`. It deletes the row, increments no other table, and emits a `worker.retention.completed` log line carrying `deleted_count=1` and `next_run_at`. A second invocation with no expired rows still emits `worker.retention.completed` with `deleted_count=0`. (Phase-1→2 exit criterion #8.)

## Forbidden Scope

- Do not send raw sensitive logs to analytics.
- Do not make cached answers free in usage accounting.
- Do not share follow-up cache entries with standalone queries.
- Do not implement public billing launch workflows.
