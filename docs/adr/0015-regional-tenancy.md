# ADR 0015: Regional Tenancy and Data Residency

Date: 2026-05-22
Status: Accepted (design); implementation gated on Phase-2 trigger

## Context

The Phase-1 deployment is single-region (Railway US). The current `tenants` table already carries a `data_region` field (per founder decision row "EU data region" in `approved-decisions-register.md`), but no contract addresses how that field translates into actual regional pinning: no JWT region claim, no per-region database, no rejection of cross-region requests.

The first EU enterprise customer, or any ecclesiastical jurisdiction with a documented residency policy, requires resolution. Clerk does not natively guarantee EU residency on standard plans (Clerk DPA 2026); Railway has multi-region capability but does not automatically scope a deployment to one region. This ADR specifies the regional-tenancy mechanism so the implementation work in `docs/task_cards/phase2/T-2XX-regional-tenancy.md` has unambiguous direction.

## Decision

Regional tenancy is implemented through three coordinated mechanisms:

### 1. Per-region deployment instances

Each supported region is its own deployment (Railway region, Cloud Run region, or Fly region). A region runs Postgres + Qdrant + Redis + the FastAPI application + the worker fleet. Inter-region traffic is forbidden for tenant data; cross-region admin actions (founder review across regions) require explicit auth-context scoping documented in §4.

Phase-2 launch regions:

- `us-east-1` (default, Phase 1 carryover)
- `eu-west-1` (first EU customer)

Additional regions follow the same pattern.

### 2. `tenant.data_region` is authoritative; JWT carries `region` claim

The Clerk JWT issued for an authenticated session carries a `region` claim resolved from `tenants.data_region` at session creation time. The FastAPI region middleware:

1. Reads the `region` claim from the validated JWT.
2. Compares against the running instance's own region (read from `APP_REGION` env var at startup).
3. On mismatch: returns HTTP 421 (Misdirected Request) with the canonical error code `wrong_region`, the correct region's base URL in the `Location` header, and a typed body that the client can use to re-route. The error is added to `docs/contracts/error-taxonomy.md` as part of this ADR's implementation.

The Clerk webhook handler routes `org.created` and `user.org.assignment.created` events to the correct region's webhook endpoint based on the persisted `tenant.data_region`. The webhook URL stored in Clerk is a region-aware front-door that demultiplexes events; the front-door is the only multi-region service.

### 3. Per-region Postgres + Qdrant + Redis with no cross-region replication for tenant data

Per-region instances are independent. Backups are per-region. Cross-region restore is forbidden by the operational runbook. ADR-0016 Postgres RLS applies independently in each region (each region's database has its own `tenant_isolation_policy` keyed off the same GUC).

Tenant migration between regions (rare; e.g., a customer changes residency requirements) requires:

- Customer consent recorded in `audit_entries` (`action='tenant_region_migration_consented'`).
- A documented runbook process (out of scope for this ADR; tracked as a separate Phase-2 task card if and when needed).

### 4. Cross-region admin actions

The founder reviews all tenants regardless of region. Cross-region access requires:

- A `cross_region` scope on the founder's `Principal` (added to `auth-context.md` in the implementation phase).
- A `cross_region_access` audit row per request, carrying both region identifiers.
- A read-only posture by default; writes that cross regions require an additional safeguard (manual confirmation step) documented in the operational runbook.

### 5. Region-aware caching, billing, and logging

- Response cache: regional. The cache key already includes `tenant_id`; the regional cache is co-located with the regional Redis. No cross-region cache hits.
- Stripe billing: a single Stripe account aggregates usage across regions (legal entity is the same). Billing rows in each region's `billing_usage` table sync to the central billing pipeline via a region-aware export job.
- Logs and traces: regional. OTel exports go to the regional Langfuse instance (Phase-2 REC-025 wiring). No log shipping across regions.

## Interface Contract

### `tenant.schema.json` extensions

```json
{
  "dataRegion": {
    "type": "string",
    "enum": ["us-east-1", "eu-west-1"],
    "description": "Authoritative region pin for this tenant. Determines which deployment instance serves the tenant's requests and where its data is stored. Immutable after tenant creation except via the tenant-region-migration runbook."
  }
}
```

### `error-taxonomy.md` addition

| Code | HTTP | Retryable | Notes |
|---|---|---|---|
| `wrong_region` | 421 | no | The request reached the wrong region. The response includes the correct region's base URL in the `Location` header and a typed JSON body. Clients SHOULD re-issue the request to the correct region without retrying the current endpoint. |

### `Principal` extension

A new boolean field `cross_region` on the resolved `Principal`. Only the founder role can have `cross_region=true`. Every request where `cross_region=true` and the request's targeted tenant is in a different region writes an `audit_entries` row.

## Tests

- A request to the us-east-1 instance for a tenant whose `data_region='eu-west-1'` returns HTTP 421 `wrong_region` with the correct `Location` header.
- A Clerk webhook event for a tenant in `eu-west-1` is delivered to the eu-west-1 region (the front-door demux is exercised in an integration test against a fixture webhook stream).
- The founder issues a `cross_region` read; the access is allowed and writes an `audit_entries` row. A non-founder admin attempting the same is refused with `forbidden_role`.
- Backup/restore is exercised per-region in CI; cross-region restore is rejected by the runbook automation.

## Consequences

- **Operational complexity.** Two (or more) deployment instances replace one. CI/CD pipelines, monitoring, and on-call rotations need region awareness. The cost is real but bounded by the number of supported regions.
- **Customer onboarding.** Every new tenant chooses a region at creation time. The Clerk-org-creation flow gains a region selector (or the founder sets it based on the customer contract).
- **Latency.** EU customers see EU-region latency rather than transatlantic round trips. US customers are unaffected.
- **Compliance posture.** Documented per-region data handling supports GDPR data-controller / data-processor agreements with EU customers.
- **Cost.** Per-region instances have minimum-instance overhead. For small regions, this is partially offset by lower Railway tier requirements; for large regions, it scales linearly with traffic.

## Alternatives Considered

- **Multi-region Postgres with synchronous replication.** Rejected: violates residency (data exists in multiple regions); also expensive and operationally complex.
- **Single-region deployment with EU data-residency disclaimer.** Rejected: cannot honor contractual EU residency for enterprise customers.
- **CDN-based region routing only (data still in one region).** Rejected: CDN routing helps latency but not residency. Tenant data must physically live in the chosen region.

## References

- ADR-0003 (Multi-Tenant Day One).
- ADR-0016 (Postgres RLS) — applies independently per region.
- `docs/contracts/approved-decisions-register.md` — founder decision row "EU data region".
- `docs/task_cards/phase2/T-2XX-regional-tenancy.md` — implementation card.
- 2026-05-22 frontier meta-evaluation — REC-023.
