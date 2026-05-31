# ADR 0016: Postgres Row-Level Security (RLS) for Tenant Isolation

Date: 2026-05-22
Status: Accepted

## Context

ADR-0003 establishes that the system is tenant-aware from day one. `docs/contracts/db-schema.md` originally recorded the Phase-1 posture as:

> *"Tenant scoping: app-layer. Every tenant table has `tenant_id NOT NULL`. The repository layer adds `WHERE tenant_id = :tenant_id` to every read and write. Postgres RLS is not enabled in Phase 1… RLS becomes a Phase 2 ADR."*

That deferral was a conscious cost-vs-coverage call when the contract pack was first drafted: every read/write through SQLAlchemy already takes a tenant predicate; `pgaudit` records any direct DB session that bypasses the application; the integration tests at `tests/integration/test_tenant_isolation.py` cover the cross-tenant invariant from the application boundary. The Qdrant side is independently covered by `VectorFilter.tenant_id` as a required dataclass field (`docs/contracts/vector-store-interface.md` L111–119).

The 2026-05-22 frontier meta-evaluation (GS-1) revisits the trade-off and recommends pulling RLS forward to Phase 1. The empirical case:

1. **Developer-omitted filter is the dominant SaaS multi-tenant failure mode.** A typical regression is a complex join that forgets the `WHERE tenant_id = ?` clause on a secondary table; the integration tests pass on the primary table and silently let the join leak. Postgres RLS catches this at the engine layer rather than at code-review time.
2. **The defense-in-depth pattern is already canonical elsewhere.** `vector-store-interface.md` §"Tenant Isolation Invariant" enforces tenant isolation at the Protocol surface (`VectorFilter.tenant_id` required field + runtime check). RLS is the same philosophy applied to Postgres — close the parallel gap.
3. **Pulling forward is cheap if done before code lands.** Adding RLS to migration #1 is a small one-time complexity bill (FastAPI session dependency for `SET LOCAL`, `BYPASSRLS` role provisioning, a test that asserts fail-closed behavior). Retrofitting RLS after Phase 2 launches against live tenants is materially more expensive (every existing query plan reconsidered; downtime for the ALTER TABLE).

This ADR records the decision to enable RLS in Phase 1, names the rules required to make it work cleanly with SQLAlchemy 2.x async + connection pooling, and supersedes the deferral language in `db-schema.md` L10–11.

## Decision

Postgres Row-Level Security is **enabled in Phase 1** on every multi-tenant table. The application layer remains responsible for issuing filtered queries (defense in depth); RLS is the engine-layer fail-closed backstop.

### Rule 1 — Enable on every multi-tenant table

Migration #1 issues, for every table with a `tenant_id` column:

```sql
ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <table_name> FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON <table_name>
  FOR ALL
  USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::text)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::text);
```

- `FORCE ROW LEVEL SECURITY` ensures the policy applies even to the table owner (without `FORCE`, the table owner bypasses RLS by default).
- The `USING` clause governs reads; the `WITH CHECK` clause governs writes. Both must reference the same GUC so an insert with a different `tenant_id` is rejected.
- `NULLIF(..., '')::text` converts an unset or empty GUC into `NULL`, which makes the equality fail (no rows visible). The cast to `text` matches the `tenant_id` column type (ULID strings per `db-schema.md`).
- Tables in scope at migration #1: every table with a `tenant_id` column today (`sources`, `chunks`, `ingest_jobs`, `sessions`, `run_traces`, `flagged_queries`, `raw_sensitive_logs`, `audit_entries`, `model_route_invocations`, `billing_usage`, `safety_suite_runs`, and `graph_candidates` once REC-013 lands). `tenants` and `users` are scoped by `tenant_id` differently (a `tenants` row IS a tenant; a `users` row maps to a tenant via the join table). For `users`, the policy uses `tenant_id` on the membership row, not the user row.

### Rule 2 — FastAPI dependency sets the GUC per request

A dependency in `app/api/deps.py` runs at the start of every authenticated route, after the `Principal` is resolved by Clerk:

```python
# illustrative
async def set_tenant_guc(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await session.execute(
        text("SET LOCAL app.current_tenant_id = :tid"),
        {"tid": principal.tenant_id},
    )
```

- `SET LOCAL` confines the GUC to the current transaction. The next checkout from the pool starts with the GUC unset; if a developer forgets to wire this dependency on a new route, the route sees zero rows (fail closed).
- The dependency is composed into every authenticated route via the existing `get_principal` dependency chain; there is no per-route boilerplate beyond ensuring the dependency is in the chain.
- Read-after-write within the same request is unaffected because the `SET LOCAL` applies to the entire transaction.

### Rule 3 — `BYPASSRLS` reserved to a dedicated role

A single `app_admin` Postgres role has `BYPASSRLS`. It is used by:

- Alembic migrations (`alembic.ini` ENV pointing at the `app_admin` connection string).
- Seed scripts (`backend/app/db/seeds/*.py`).
- The retention worker (`app/workers/tasks/retention.py`) for cross-tenant cleanup operations — every action it takes writes an `audit_entries` row with `actor_id='retention_worker'` and the cross-tenant scope recorded in `details`.
- Operator-issued one-off queries during incident response.

The application's normal connection pool uses an `app_runtime` role that does **not** have `BYPASSRLS`. The `app_admin` credential is stored in Railway secret manager as `DATABASE_URL_ADMIN`, read only by the components above, and is never injected into the FastAPI request path.

### Rule 4 — Integration test asserts fail-closed behavior

`tests/integration/test_rls_zero_results.py` runs against the test database with the `app_runtime` role. For every multi-tenant table:

1. Insert a row under tenant A (with the GUC set).
2. Clear the GUC (no `SET LOCAL`).
3. `SELECT * FROM <table>` returns zero rows (RLS denies; no exception is raised).
4. `INSERT INTO <table>` with `tenant_id='B'` while the GUC is set to `'A'` raises `psycopg.errors.CheckViolation` (the `WITH CHECK` clause rejects).

This test is added to the existing `tests/integration/test_tenant_isolation.py` suite as a new file (parallel scope) and is part of the Phase-1 → 2 exit criterion #5 coverage.

### Rule 5 — Background workers carry tenant context explicitly

Workers that operate on behalf of a specific tenant (e.g., ingestion) MUST set the GUC before any tenant-scoped query, using the same `SET LOCAL` pattern as the request path. Workers that are intentionally cross-tenant (retention) connect as `app_admin` (BYPASSRLS) and log every cross-tenant action to `audit_entries`. Workers that need both modes within one job carry an explicit `tenant_id` parameter and re-enter the GUC scope per tenant.

### Rule 6 — Connection pooling discipline

SQLAlchemy 2.x async uses `asyncpg` under a connection pool. The `SET LOCAL` GUC is transaction-scoped, but the connection itself is returned to the pool with whatever GUCs were `SET SESSION`. The codebase MUST NOT use `SET SESSION app.current_tenant_id` anywhere — only `SET LOCAL`. This is enforced by a unit test that greps the codebase for `SET SESSION app` and fails if any match is found.

## Tests

In addition to the integration test in Rule 4:

- `tests/unit/test_rls_policy_coverage.py` — introspects the live schema and asserts that every table with a `tenant_id` column has `relrowsecurity = true` and `relforcerowsecurity = true` in `pg_class`, and that a `tenant_isolation_policy` policy exists on each.
- `tests/integration/test_retention_audit_trail.py` — invokes the retention worker against a multi-tenant fixture and asserts every cross-tenant action produces an `audit_entries` row.
- `tests/safety/test_20_queries.py` — existing test, unchanged. RLS does not affect the safety-suite path because the safety suite runs as a single-tenant workflow.

## Consequences

- **Cost.** Every request adds one `SET LOCAL` statement before the first query. The cost is one round-trip to Postgres per request (or zero if multiple queries share the same transaction). Below noise on the p95 latency budget.
- **Migration complexity.** Migration #1 grows by one `ALTER TABLE … ENABLE ROW LEVEL SECURITY` + one `CREATE POLICY` per multi-tenant table. The pattern is mechanical; the migration file gains ~30 lines.
- **Operational discipline.** Operators issuing one-off queries against production must use the `app_admin` connection string OR set the GUC explicitly. This is documented in the on-call runbook (out of scope for this ADR).
- **Defense in depth, not defense in width.** RLS protects against missing-filter regressions in application code. It does NOT protect against:
  - A bug that sets the GUC to a different tenant than the authenticated `Principal.tenant_id`. The FastAPI dependency in Rule 2 is the single source of the tenant-id value; the integration test asserts the dependency runs before any tenant-scoped query.
  - SQL injection that overrides the GUC mid-transaction. The codebase uses parameterized queries everywhere; this is covered by the existing SQL-injection lint rule.
  - Application-layer logic that disregards the resolved Principal (e.g., returning a row from a cross-tenant cache). This is the responsibility of the cache layer and the auth layer; RLS does not extend to those.
- **No effect on Qdrant.** Qdrant tenant isolation is handled by `VectorFilter.tenant_id` (ADR-0010, `vector-store-interface.md`). The two backstops are parallel — one enforces tenant isolation at the relational engine, the other at the Protocol surface for the vector store. Both are required because the Qdrant payload filter cannot use a Postgres GUC.

## Alternatives Considered

- **Defer to Phase 2 (the original posture).** Rejected per the 2026-05-22 evaluation: the cost of retrofitting RLS against live data is materially higher than the cost of including it in migration #1.
- **App-layer-only with stricter linting** (e.g., a custom ruff rule that requires every SQLAlchemy query against a multi-tenant model to include a `.filter(Model.tenant_id == X)` call). Rejected as fragile: complex joins and raw `text()` queries are hard to lint deterministically, and the failure mode is silent (no test catches it unless the test happens to exercise the leaked join).
- **Per-tenant Postgres schema / per-tenant database.** Rejected for Phase 1: provisioning cost and Alembic complexity per tenant make this a Phase-3 escape hatch, not a Phase-1 default. ADR-0015 (regional tenancy) and a future per-tenant-schema ADR could revisit this if a tenant's compliance posture requires it.

## Implementation status (T-008 GS-1)

The DB layer shipped with T-005 (migration `0002_rls_and_app_roles.py`): RLS `ENABLE` + `FORCE` and the `tenant_isolation_policy` on every multi-tenant table; roles `app_runtime` (NOLOGIN) and `app_admin` (NOLOGIN BYPASSRLS). The runtime wiring that makes the backstop actually engage landed in T-008 GS-1:

- **Request path (Rule 2).** `app/api/v1/_deps.py::get_tenant_session` resolves the `Principal` and calls `app/core/tenant_context.py::set_tenant_guc` (`SET LOCAL app.current_tenant_id`) inside the request transaction. All authenticated tenant-scoped routes depend on it; `query.py` sets the GUC inline on its own session. `get_session` is retained as an explicit RLS-bypass for platform-table callers.
- **Role split (Rules 3 & 5).** `init_engine(admin=…)` selects `database_url` (→ `app_runtime`, subject to RLS) for the request path and `database_admin_url` (→ `app_admin`, BYPASSRLS) for migrations (`alembic/env.py`), the retention worker, and the ingestion worker. Both fall back to `database_url` when no admin URL is set, so dev's single-superuser URL keeps working (RLS inert locally). Migration `0005_app_runtime_login.py` grants `app_runtime` LOGIN; its password is provisioned out-of-band (never committed).
- **Deploy contract.** Production sets `DATABASE_URL` to the `app_runtime` connection string and `DATABASE_ADMIN_URL` to the `app_admin` connection string. That is the single switch that turns enforcement on; if `DATABASE_URL` stays a superuser, RLS is bypassed and only the app-layer filter applies.
- **Follow-ups.** Per-job GUC for the ingestion worker so it runs as `app_runtime` rather than `app_admin` (Rule 5); wiring a Postgres service into CI so the isolation suite runs there instead of skipping.

## References

- ADR-0003 (Multi-Tenant Day One) — the parent decision this ADR strengthens.
- ADR-0010 (`VectorStore` Interface Pattern) — parallel defense-in-depth at the Qdrant Protocol boundary.
- ADR-0013 (Qdrant Collection Topology) — predicate-filtering on `tenant_id` at the vector-store layer.
- `docs/contracts/db-schema.md` L10–11 — original deferral, superseded by this ADR.
- `docs/contracts/auth-context.md` — Principal resolution, the source of the `tenant_id` value the GUC carries.
- 2026-05-22 frontier meta-evaluation — GS-1.
