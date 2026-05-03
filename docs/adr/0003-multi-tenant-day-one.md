# ADR 0003: Multi-Tenant From Day One

Date: 2026-04-26
Status: Accepted

## Context

Phase 1 has one live private-beta tenant, but retrofitting tenancy later would affect every table, cache key, vector payload, log, and admin screen.

## Decision

Phase 1 is implemented as tenant-aware from day one. Orthodox Ethos is the first tenant, not a hardcoded single-tenant architecture.

## Rules

1. Tenant data tables include `tenant_id`.
2. Qdrant payloads include `tenant_id`, `approved`, visibility, and source identifiers.
3. SQL queries and repositories scope tenant data by context.
4. Cache keys include tenant and role.
5. Logs include tenant and user context where applicable.
6. Clerk organization IDs map to internal tenants.
7. Stripe customer/subscription IDs live on tenant billing records.
8. Admin screens are tenant-aware even when only one tenant exists.

## Tests

- Tenant A cannot retrieve, cache-hit, log-read, or admin-view Tenant B data.
- Missing tenant context fails closed.
- Clerk org mapping resolves to exactly one active tenant.
- Cache keys differ by tenant and role.
