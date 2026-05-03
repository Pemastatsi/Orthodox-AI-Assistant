# Database Schema

Status: Canonical
Date: 2026-05-02

This document is the canonical Postgres DDL for Phase 1. The first Alembic migration (`backend/app/alembic/versions/0001_initial.py`) renders this file 1:1.

## Decisions

- **Tenant scoping: app-layer.** Every tenant table has `tenant_id NOT NULL`. The repository layer adds `WHERE tenant_id = :tenant_id` to every read and write. Postgres RLS is not enabled in Phase 1.
- **Defense in depth:** a `pgaudit` rule (configured at infrastructure level) records every direct DB session that bypasses the application. RLS becomes a Phase 2 ADR.
- **Primary keys** are ULID strings (text). They are sortable by creation time and safe to include in URLs and logs.
- **Timestamps** are `timestamptz` (UTC).
- **Soft deletes** are not used in Phase 1 except where retention requires it (raw sensitive logs); admins use status enums (`closed`, `disabled`, `deprecated`).
- **JSON columns** are `jsonb`. All jsonb columns must have a documented schema in `docs/schemas/`.
- **`tenants.config`** is the single canonical jsonb document for safe tenant configuration. The shape is `tenant.schema.json#/properties/config` and the `calendarProfile` sub-object follows `calendar-profile.schema.json`. Cache-key references (`tenants.config.calendarProfile.version`, `tenants.config_version`) read from this column directly — there is no separate `calendar_profiles` table in Phase 1.

## Extensions

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- digest(), gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- trigram indexes for admin search
CREATE EXTENSION IF NOT EXISTS citext;     -- case-insensitive emails
```

## Tables

### `tenants`

```sql
CREATE TABLE tenants (
    tenant_id              text PRIMARY KEY,
    name                   text NOT NULL,
    clerk_org_id           text NOT NULL UNIQUE,
    stripe_customer_id     text UNIQUE,
    status                 text NOT NULL CHECK (status IN ('active','suspended','trial','closed')),
    data_region            text NOT NULL CHECK (data_region IN ('us','eu')) DEFAULT 'us',
    starter_corpus_enabled boolean NOT NULL DEFAULT false,
    config                 jsonb NOT NULL DEFAULT '{}'::jsonb,
    config_version         text NOT NULL DEFAULT '2026-05-01.1',
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz
);
CREATE INDEX idx_tenants_clerk_org ON tenants(clerk_org_id);
CREATE INDEX idx_tenants_stripe_customer ON tenants(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;
```

### `users`

```sql
CREATE TABLE users (
    user_id        text PRIMARY KEY,
    clerk_user_id  text NOT NULL UNIQUE,
    tenant_id      text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    email          citext,
    display_name   text,
    role           text NOT NULL CHECK (role IN ('member','scholar','content_manager','admin','owner')),
    status         text NOT NULL CHECK (status IN ('active','invited','disabled')) DEFAULT 'invited',
    created_at     timestamptz NOT NULL DEFAULT now(),
    last_seen_at   timestamptz
);
CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE INDEX idx_users_email ON users(tenant_id, email) WHERE email IS NOT NULL;
```

### `sources`

```sql
CREATE TABLE sources (
    source_id          text PRIMARY KEY,
    tenant_id          text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    title              text NOT NULL,
    father             text,
    work               text,
    language           text NOT NULL CHECK (language IN ('en','el','mixed')) DEFAULT 'en',
    source_type        text NOT NULL CHECK (source_type IN ('pdf','txt','md','docx')),
    source_hash        text NOT NULL,                 -- 'sha256:<hex>' per decision J
    extraction_method  text NOT NULL,
    approved           boolean NOT NULL DEFAULT false,
    approval_note      text,
    approved_by        text REFERENCES users(user_id),
    approved_at        timestamptz,
    corpus_version     text NOT NULL,
    metadata           jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, source_hash)
);
CREATE INDEX idx_sources_tenant_approved ON sources(tenant_id, approved);
CREATE INDEX idx_sources_corpus_version ON sources(tenant_id, corpus_version);
```

### `chunks`

```sql
CREATE TABLE chunks (
    chunk_id            text PRIMARY KEY,
    source_id           text NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    tenant_id           text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    text                text NOT NULL,
    chunk_hash          text NOT NULL,
    approved            boolean NOT NULL DEFAULT false,
    visibility          text NOT NULL CHECK (visibility IN ('member','scholar','admin_only','suppressed')) DEFAULT 'admin_only',
    father              text,
    work                text,
    page                text,
    timestamp           text,
    language            text NOT NULL DEFAULT 'en',
    categories          text[] NOT NULL DEFAULT '{}',
    embedding_model     text NOT NULL,
    embedding_dimension integer NOT NULL,
    corpus_version      text NOT NULL,
    review_note         text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, chunk_hash)
);
CREATE INDEX idx_chunks_tenant_approved ON chunks(tenant_id, approved, visibility);
CREATE INDEX idx_chunks_source ON chunks(source_id);
```

### `sessions`

```sql
CREATE TABLE sessions (
    session_id    text PRIMARY KEY,
    tenant_id     text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    user_id       text NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    session_hash  text NOT NULL,
    turn_count    integer NOT NULL DEFAULT 0,
    last_query_at timestamptz,
    expires_at    timestamptz NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_sessions_tenant_user ON sessions(tenant_id, user_id);
CREATE INDEX idx_sessions_expiry ON sessions(expires_at);
```

### `ingest_jobs`

```sql
CREATE TABLE ingest_jobs (
    job_id        text PRIMARY KEY,
    tenant_id     text NOT NULL REFERENCES tenants(tenant_id),
    user_id       text NOT NULL REFERENCES users(user_id),
    source_id     text NOT NULL REFERENCES sources(source_id),
    status        text NOT NULL CHECK (status IN ('queued','extracting','chunking','embedding','awaiting_review','completed','failed','cancelled')),
    progress      jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_code    text,
    error_message text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    started_at    timestamptz,
    finished_at   timestamptz
);
CREATE INDEX idx_ingest_jobs_tenant_status ON ingest_jobs(tenant_id, status);
```

### `run_traces`

```sql
CREATE TABLE run_traces (
    run_id                 text PRIMARY KEY,
    tenant_id              text NOT NULL REFERENCES tenants(tenant_id),
    user_id                text NOT NULL REFERENCES users(user_id),
    session_id             text REFERENCES sessions(session_id),
    started_at             timestamptz NOT NULL,
    finished_at            timestamptz,
    cache_hit              boolean NOT NULL DEFAULT false,
    stages                 jsonb NOT NULL DEFAULT '[]'::jsonb,
    usage                  jsonb NOT NULL DEFAULT '{}'::jsonb,
    final_handling         text,
    final_confidence_tier  text,
    verifier_passed        boolean,
    evidence_packet_ref    text,                       -- pointer into object storage if persisted
    created_at             timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_run_traces_tenant_started ON run_traces(tenant_id, started_at DESC);
CREATE INDEX idx_run_traces_user ON run_traces(tenant_id, user_id, started_at DESC);
```

### `flagged_queries`

```sql
CREATE TABLE flagged_queries (
    flagged_query_id     text PRIMARY KEY,
    tenant_id            text NOT NULL REFERENCES tenants(tenant_id),
    user_id              text NOT NULL REFERENCES users(user_id),
    run_id               text REFERENCES run_traces(run_id),
    query_text_redacted  text NOT NULL,
    raw_sensitive_log_id text REFERENCES raw_sensitive_logs(log_id),
    flag_reason          text NOT NULL CHECK (flag_reason IN ('red_tier','insufficient_evidence','block_with_redirect','verifier_failed','hard_safety_trigger','user_reported')),
    sensitivity_primary  text,
    risk_flags           text[] NOT NULL DEFAULT '{}',
    embedding            real[],                       -- nullable; only set when clustering enabled
    embedding_model      text,
    cluster_id           text,
    created_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_flagged_tenant_created ON flagged_queries(tenant_id, created_at DESC);
CREATE INDEX idx_flagged_cluster ON flagged_queries(tenant_id, cluster_id) WHERE cluster_id IS NOT NULL;
```

### `raw_sensitive_logs`

Encrypted-at-rest raw query text for sensitive cases. Admin-only, audited, 30-day retention.

```sql
CREATE TABLE raw_sensitive_logs (
    log_id          text PRIMARY KEY,
    tenant_id       text NOT NULL REFERENCES tenants(tenant_id),
    user_id         text NOT NULL REFERENCES users(user_id),
    run_id          text REFERENCES run_traces(run_id),
    ciphertext      bytea NOT NULL,                    -- envelope-encrypted
    key_version     text NOT NULL,                     -- KMS key version label
    nonce           bytea NOT NULL,
    expires_at      timestamptz NOT NULL,              -- now() + 30 days
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_raw_sensitive_expiry ON raw_sensitive_logs(expires_at);
```

A retention worker (`workers/tasks/retention_cleanup.py`) deletes rows where `expires_at < now()`.

### `audit_entries`

```sql
CREATE TABLE audit_entries (
    audit_id       text PRIMARY KEY,
    tenant_id      text NOT NULL REFERENCES tenants(tenant_id),
    actor_user_id  text NOT NULL REFERENCES users(user_id),
    actor_role     text NOT NULL,
    action         text NOT NULL,
    resource_type  text NOT NULL,
    resource_id    text NOT NULL,
    details        jsonb NOT NULL DEFAULT '{}'::jsonb,
    ip_address     inet,
    occurred_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_tenant_occurred ON audit_entries(tenant_id, occurred_at DESC);
CREATE INDEX idx_audit_resource ON audit_entries(resource_type, resource_id);
```

The `action` column is constrained at the API layer (not in DDL) to the enum in `docs/schemas/audit-entry.schema.json#/properties/action`. That enum includes `founder_phase2_signoff`, written by the Phase-1→2 founder review protocol described in `docs/contracts/phase1-implementation-contract.md`. The `details` jsonb on a `founder_phase2_signoff` row carries the review checklist (sample run IDs, coverage of `answerMode` values, coverage of `sensitivityPrimary` categories, noted concerns).

### `model_routes`

```sql
CREATE TABLE model_routes (
    route_id              text PRIMARY KEY,
    purpose               text NOT NULL CHECK (purpose IN ('query_analyzer','compose','verifier_judge','embedding')),
    provider              text NOT NULL CHECK (provider IN ('anthropic','openai')),
    model                 text NOT NULL,
    prompt_version        text NOT NULL,
    schema_version        text NOT NULL,
    supports_prompt_cache boolean NOT NULL DEFAULT false,
    supports_batch        boolean NOT NULL DEFAULT false,
    supports_json_mode    boolean NOT NULL DEFAULT false,
    certification_status  text NOT NULL CHECK (certification_status IN ('draft','experiment','certified','deprecated')) DEFAULT 'draft',
    safety_suite_run_id   text,
    certified_by          text REFERENCES users(user_id),
    certified_at          timestamptz,
    deprecated_at         timestamptz,
    created_at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_model_routes_purpose_status ON model_routes(purpose, certification_status);
```

### `prompt_versions`

```sql
CREATE TABLE prompt_versions (
    prompt_version    text PRIMARY KEY,                  -- e.g., 'a5_compose@2026-05-01.1'
    purpose           text NOT NULL,
    body              text NOT NULL,
    is_platform_owned boolean NOT NULL DEFAULT true,     -- tenant prompts are not free-form in MVP
    activated_at      timestamptz,
    deprecated_at     timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now()
);
```

### `billing_usage`

```sql
CREATE TABLE billing_usage (
    tenant_id              text NOT NULL REFERENCES tenants(tenant_id),
    period_start           timestamptz NOT NULL,
    period_end             timestamptz NOT NULL,
    served_answer_count    integer NOT NULL DEFAULT 0,
    fresh_model_run_count  integer NOT NULL DEFAULT 0,
    prompt_tokens          bigint NOT NULL DEFAULT 0,
    completion_tokens      bigint NOT NULL DEFAULT 0,
    embedding_tokens       bigint NOT NULL DEFAULT 0,
    stripe_usage_record_id text,
    reported_at            timestamptz,
    PRIMARY KEY (tenant_id, period_start)
);
CREATE INDEX idx_billing_period_end ON billing_usage(period_end);
```

## Cross-Table Invariants

1. Every row in a tenant-scoped table has `tenant_id` matching the parent (chunks → sources → tenants).
2. `chunks.approved=true` implies `sources.approved=true` for the parent. Enforced in the repository on update; tests cover this in `tests/integration/test_corpus.py`.
3. `flagged_queries.raw_sensitive_log_id` is non-null only when `sensitivity_primary` is set.
4. `audit_entries` are append-only. There is no UPDATE or DELETE granted to the application role.
5. `raw_sensitive_logs` are deleted only by the retention worker.

## Migrations

The first migration creates everything above and the extensions. Subsequent migrations are forward-only; squashing requires an ADR. Every migration:

- Has a `# Created by: <username>` line.
- Has both `upgrade()` and `downgrade()` even when downgrade is a no-op (document why).
- Adds an entry to `docs/adr/` only when changing semantics, not for additive columns with defaults.
