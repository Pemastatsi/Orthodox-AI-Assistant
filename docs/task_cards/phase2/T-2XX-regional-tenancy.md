# T-2XX: Regional Tenancy Implementation

Status: Phase 2 — gated on first EU enterprise customer (or other regional-residency requirement).

## Trigger conditions

- A signed contract with an EU customer that names data-residency or GDPR processing-region requirements.
- A US customer with HIPAA / state-level residency requirements that the shared deployment cannot meet.
- An ecclesiastical jurisdiction's data-handling policy requires a specific region.

## Required Reads

- ADR-0015 (Regional Tenancy) — the design this card implements.
- ADR-0003 (Multi-Tenant Day One) — the tenant-isolation parent decision.
- ADR-0016 (Postgres RLS) — extends naturally to per-region database instances.
- REC-023 in the 2026-05-22 frontier meta-evaluation.
- `docs/schemas/tenant.schema.json` — the `dataRegion` field landed by ADR-0015.

## Implementation scope

- Per-region Postgres + Qdrant + Redis instances provisioned via Railway region selection or migrated to a multi-region provider (Cloud Run + Cloud SQL is one named option in ADR-0015).
- Clerk JWT carries a `region` claim resolved from `tenants.dataRegion`; routing layer rejects requests for a tenant whose `region` claim does not match the running instance's region.
- Cross-region admin actions (founder review of all tenants) require explicit auth-context scoping.
- Audit trail: every cross-region action logs to `audit_entries` with `action='cross_region_access'` and the region pair.

## Acceptance Criteria

- A tenant created with `dataRegion='eu-west-1'` is provisioned in the eu-west-1 instance; requests to the us-east-1 instance for that tenant return `wrong_region` (a new error code in `error-taxonomy.md`).
- Clerk webhook handler routes tenant-creation events to the correct region.
- Backup/restore is per-region; cross-region restore is forbidden by the runbook.
- Latency p95 from the EU customer's location remains under the same target as the US baseline.

## Forbidden Scope

- No data replication across regions for customer corpora (defeats residency).
- No tenant moved between regions without an explicit migration plan and customer consent.
- No relaxation of the tenant-isolation invariant — per-region instances are themselves multi-tenant within their region, and ADR-0016 RLS applies.
