# Database Schema

Status: Canonical
Date: 2026-05-11

This document is the canonical Postgres DDL for Phase 1. The first Alembic migration (`backend/app/alembic/versions/0001_initial.py`) renders this file 1:1.

## Decisions

- **Tenant scoping: app-layer + Postgres RLS (defense in depth).** Every tenant table has `tenant_id NOT NULL`. The repository layer adds `WHERE tenant_id = :tenant_id` to every read and write (primary line of defense). Postgres Row-Level Security is enabled in Phase 1 per **ADR-0016** as the engine-layer backstop: `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` on every multi-tenant table, with a `tenant_isolation_policy` keyed off the per-request GUC `app.current_tenant_id`. A FastAPI dependency sets the GUC via `SET LOCAL` at the start of every authenticated transaction; missing the GUC produces zero rows (fail closed). The `app_runtime` Postgres role used by the request pool does NOT have `BYPASSRLS`; only the `app_admin` role (used by Alembic migrations, seeders, and the audited retention worker) does.
- **Defense in depth:** a `pgaudit` rule (configured at infrastructure level) records every direct DB session that bypasses the application. The combination of (a) app-layer `WHERE tenant_id` filtering, (b) Postgres RLS, and (c) pgaudit is the Phase-1 tenant-isolation defense triad.
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
    config                 jsonb NOT NULL DEFAULT '{}'::jsonb,  -- shape: tenant.schema.json#/properties/config; config.corpusVersion is a system-managed string set by the ingestion service on cutover; never written via the PATCH /tenant/config endpoint
    config_version         text NOT NULL DEFAULT '2026-05-01.1',
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz
);
CREATE INDEX idx_tenants_clerk_org ON tenants(clerk_org_id);
CREATE INDEX idx_tenants_stripe_customer ON tenants(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;
```

`tenants.config.corpusVersion` (optional string) is populated by the ingestion service when a new corpus version is cut over. It is never written by application code that handles `PATCH /tenant/config`. The field is absent during initial provisioning and becomes present after the first successful ingestion cutover.

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
    source_id                text PRIMARY KEY,
    tenant_id                text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    title                    text NOT NULL,
    father                   text,
    work                     text,
    language                 text NOT NULL CHECK (language IN ('en','el','mixed')) DEFAULT 'en',
    source_type              text NOT NULL CHECK (source_type IN ('pdf','txt','md','docx')),
    source_hash              text NOT NULL CHECK (source_hash ~ '^sha256:[0-9a-f]{64}$'),  -- 'sha256:<hex>' per decision J
    extraction_method        text NOT NULL,
    corpus_origin            text,                       -- nullable; values per source.schema.json#/properties/corpusOrigin (enum + 'monastery_archive:<name>' pattern). Enforced at the API/Pydantic layer rather than as a CHECK constraint so the monastery-archive prefix pattern stays expressive.
    digitization_provenance  text CHECK (digitization_provenance IS NULL OR digitization_provenance IN (
        'manuscript','manuscript_facsimile','critical_edition','scholarly_edition',
        'paperback','hardcover','publisher_pdf','scanned_pdf','web_html','born_digital',
        'audio_transcript','video_transcript','unknown'
    )),
    approved                 boolean NOT NULL DEFAULT false,
    approval_note            text,
    approved_by              text REFERENCES users(user_id),
    approved_at              timestamptz,
    corpus_version           text NOT NULL,
    metadata                 jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at               timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, source_hash)
);
CREATE INDEX idx_sources_tenant_approved ON sources(tenant_id, approved);
CREATE INDEX idx_sources_corpus_version ON sources(tenant_id, corpus_version);
CREATE INDEX idx_sources_corpus_origin ON sources(tenant_id, corpus_origin) WHERE corpus_origin IS NOT NULL;
```

### `chunks`

```sql
CREATE TABLE chunks (
    chunk_id            text PRIMARY KEY,
    source_id           text NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    tenant_id           text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    text                text NOT NULL,
    chunk_hash          text NOT NULL CHECK (chunk_hash ~ '^sha256:[0-9a-f]{64}$'),
    approved            boolean NOT NULL DEFAULT false,
    visibility          text NOT NULL CHECK (visibility IN ('member','scholar','admin_only','suppressed')) DEFAULT 'admin_only',
    father              text,
    work                text,
    page                text,                                          -- legacy single-page citation string; new chunks populate page_start/page_end instead
    timestamp           text,
    language            text NOT NULL DEFAULT 'en',
    categories          text[] NOT NULL DEFAULT '{}',
    section_path        text[] NOT NULL DEFAULT '{}',                   -- chunking-contract.md §Required Chunk metadata; empty array for content before the first heading
    page_start          integer CHECK (page_start IS NULL OR page_start >= 1),
    page_end            integer CHECK (page_end IS NULL OR page_end >= 1),
    parent_chunk_id     text REFERENCES chunks(chunk_id) ON DELETE SET NULL,  -- chunking-contract.md §Chunk boundaries; the join key for the Phase 2 graph traversal layer per ADR-0006
    embedding_model     text NOT NULL,
    embedding_dimension integer NOT NULL,
    corpus_version      text NOT NULL,
    review_note         text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, chunk_hash),
    CHECK (page_end IS NULL OR page_start IS NULL OR page_end >= page_start)
);
CREATE INDEX idx_chunks_tenant_approved ON chunks(tenant_id, approved, visibility);
CREATE INDEX idx_chunks_source ON chunks(source_id);
CREATE INDEX idx_chunks_parent ON chunks(parent_chunk_id) WHERE parent_chunk_id IS NOT NULL;
```

The four columns `section_path`, `page_start`, `page_end`, and `parent_chunk_id` are populated by the hierarchical chunking service per `docs/contracts/chunking-contract.md` (ADR-0009). They are NULL-permitting (or empty-array-permitting) so chunks ingested before the chunking contract landed remain valid; the chunking service MUST populate all four on every new chunk it emits.

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

**Why two tables instead of one:** `flagged_queries` and `raw_sensitive_logs` are deliberately split. `flagged_queries` is reviewer-facing (admin UI lists, paginates, filters), retains for analytics, and stores no encrypted blobs. `raw_sensitive_logs` is encryption-isolated (single table = single retention worker scope, single KMS rotation surface, smaller blast radius). The cross-table FK (`flagged_queries.raw_sensitive_log_id → raw_sensitive_logs.log_id`) carries the linkage when sensitivity warrants; for non-sensitive flags, `raw_sensitive_log_id IS NULL`. A future consolidation would either split retention granularity (worse) or expose ciphertext columns to all flag review queries (also worse).

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
    purpose               text NOT NULL CHECK (purpose IN ('query_analyzer','compose','verifier_judge','embedding','rerank','retrieval_eval_judge')),
    provider              text NOT NULL CHECK (provider IN ('anthropic','openai')),
    model                 text NOT NULL,
    prompt_version        text NOT NULL,
    schema_version        text NOT NULL,
    supports_prompt_cache boolean NOT NULL DEFAULT false,
    supports_batch        boolean NOT NULL DEFAULT false,
    supports_json_mode    boolean NOT NULL DEFAULT false,
    certification_status  text NOT NULL CHECK (certification_status IN ('draft','experiment','certified','deprecated')) DEFAULT 'draft',
    safety_suite_run_id   text,                                                          -- FK to safety_suite_runs added below; defined here without inline REFERENCES because safety_suite_runs is created later in the same migration
    certified_by          text REFERENCES users(user_id),
    certified_at          timestamptz,
    deprecated_at         timestamptz,
    created_at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_model_routes_purpose_status ON model_routes(purpose, certification_status);
```

### `safety_suite_runs`

Aggregate row that groups one full pass of the canonical 20-case safety suite. Required by `model_routes.safety_suite_run_id`: a route cannot be certified without a `passed=true` row here. See ADR 0004 and `tests/safety/test_20_queries.py::CANONICAL_SAFETY_CASES` for the case list.

```sql
CREATE TABLE safety_suite_runs (
    safety_suite_run_id   text PRIMARY KEY,                       -- ULID
    purpose               text NOT NULL CHECK (purpose IN ('query_analyzer','compose','verifier_judge','embedding','rerank','retrieval_eval_judge')),
    provider              text NOT NULL CHECK (provider IN ('anthropic','openai')),
    model                 text NOT NULL,
    prompt_version        text NOT NULL,                           -- FK to prompt_versions added below
    schema_version        text NOT NULL,
    case_count            integer NOT NULL CHECK (case_count = 20),
    case_run_ids          text[] NOT NULL,                          -- exactly 20 run_traces.run_id entries, ordered by case id
    passed                boolean NOT NULL,
    failure_summary       jsonb,                                    -- empty when passed; per-case detail when failed
    initiated_by          text NOT NULL REFERENCES users(user_id),
    started_at            timestamptz NOT NULL,
    finished_at           timestamptz NOT NULL,
    created_at            timestamptz NOT NULL DEFAULT now(),
    CHECK (cardinality(case_run_ids) = 20)
);
CREATE INDEX idx_safety_suite_purpose_passed ON safety_suite_runs(purpose, passed, finished_at DESC);

-- FKs that close forward-references in this migration:
ALTER TABLE model_routes
    ADD CONSTRAINT model_routes_safety_suite_run_id_fkey
    FOREIGN KEY (safety_suite_run_id) REFERENCES safety_suite_runs(safety_suite_run_id);
ALTER TABLE safety_suite_runs
    ADD CONSTRAINT safety_suite_runs_prompt_version_fkey
    FOREIGN KEY (prompt_version) REFERENCES prompt_versions(prompt_version);
```

Each entry in `case_run_ids` MUST resolve to a valid `run_traces.run_id`; the application enforces this at insert time (no DB-level FK because `run_traces` is partitioned by tenant, while `safety_suite_runs` is platform-wide). On certification, an `audit_entries` row with `action='safety_suite_run_completed'` and `resource_type='safety_suite_run'` is written.

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

### `graph_candidates` (REC-013, Phase 1 capture per ADR-0006)

Holds candidate (unreviewed) lineage edges emitted at ingestion. Promotion to `lineage_edges` requires admin approval through a Phase-2 UI. Candidate edges never enter `EvidencePacket.lineageContext` and are invisible to A4/A5.

```sql
CREATE TABLE graph_candidates (
    candidate_id          text PRIMARY KEY,                    -- ULID
    tenant_id             text NOT NULL REFERENCES tenants(tenant_id),
    source_chunk_id       text NOT NULL REFERENCES chunks(chunk_id),
    target_chunk_id       text REFERENCES chunks(chunk_id),    -- nullable when target is an external citation not yet ingested
    target_external_ref   text,                                -- e.g., "Athanasius, Contra Arianos III.4" when target_chunk_id is NULL
    relation_type         text NOT NULL,                       -- 'quotes' | 'cites' | 'translation_of' | 'paraphrases' | 'builds_on' | 'contrasts_with' | 'supports' | 'contested_by'
    extraction_method     text NOT NULL,                       -- 'regex' | 'llm' | 'hybrid'
    extractor_route_id    text REFERENCES model_routes(route_id),  -- NULL when extraction_method='regex'
    confidence            real NOT NULL DEFAULT 0.0,           -- 0-1; regex hits default to 1.0, LLM hits use model-reported confidence
    review_status         text NOT NULL DEFAULT 'candidate',   -- 'candidate' | 'approved' | 'rejected'
    reviewed_by_user_id   text REFERENCES users(user_id),
    reviewed_at           timestamptz,
    corpus_version        text NOT NULL,
    created_at            timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, source_chunk_id, COALESCE(target_chunk_id, ''), COALESCE(target_external_ref, ''), relation_type, extraction_method)
);

CREATE INDEX idx_graph_candidates_tenant_status ON graph_candidates (tenant_id, review_status);
CREATE INDEX idx_graph_candidates_source_chunk ON graph_candidates (source_chunk_id) WHERE review_status = 'candidate';
```

- The `UNIQUE` constraint makes re-extraction on a new `corpus_version` idempotent — duplicates by `(source, target, relation, method)` are rejected at insertion.
- Approval promotes a row into `lineage_edges` and sets `review_status='approved'`. Rejection sets `review_status='rejected'` and never deletes; rejected rows are retained for audit and to suppress re-emission.
- `extraction_method='regex'` rows MUST set `extractor_route_id` to NULL; `'llm'` and `'hybrid'` rows MUST reference a valid `model_routes` row.
- Tenant isolation: every read and write predicate-filters on `tenant_id` per app-layer convention. When ADR-0016 (Postgres RLS) lands, this table will be among the multi-tenant tables receiving `ENABLE ROW LEVEL SECURITY`.

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
3. **Source-approval cascade.** Approving a chunk on an unapproved source MUST auto-approve the parent source in the same transaction. The cascade copies the chunk approval's `approved_by`, `approved_at`, and `approval_note` (or a derived note such as `"auto-approved via first-chunk approval"`) to `sources`. Once a source is approved, subsequent chunk approvals do not touch the source row. Source approval is therefore not a separate API operation in Phase 1; the only entry point is `PATCH /corpus/{chunkId}` with `approved=true`. An admin-only source-level edit (visibility, note) MAY be added later via ADR but MUST NOT change `sources.approved` from `true` to `false` without an audit entry.
4. `flagged_queries.raw_sensitive_log_id` is non-null only when `sensitivity_primary` is set.
5. `audit_entries` are append-only. There is no UPDATE or DELETE granted to the application role.
6. `raw_sensitive_logs` are deleted only by the retention worker.
7. `tenants.config.corpusVersion` is the active corpus pointer for cache-key invalidation per `cache-key.md`. It is set by the ingestion cutover step and never editable via the public tenant config API.
8. **Model-route certification grouping.** `model_routes.safety_suite_run_id` references `safety_suite_runs(safety_suite_run_id)`, NOT `run_traces(run_id)`. A `safety_suite_runs` row groups exactly 20 `run_traces.run_id` entries (one per case in `tests/safety/test_20_queries.py::CANONICAL_SAFETY_CASES`). A route may move to `certified` only when its referenced `safety_suite_runs` row has `passed=true` and was produced against the same `prompt_version`/`model`/`schema_version` triple recorded on the route. See ADR 0004.

## Migrations

The first migration creates everything above and the extensions. Subsequent migrations are forward-only; squashing requires an ADR. Every migration:

- Has a `# Created by: <username>` line.
- Has both `upgrade()` and `downgrade()` even when downgrade is a no-op (document why).
- Adds an entry to `docs/adr/` only when changing semantics, not for additive columns with defaults.

## First Migration Seed Data

The first migration ends with the seed inserts below. These rows are required at startup so the route registry can resolve the env vars `ACTIVE_MODEL_ROUTE_A1A2`, `ACTIVE_MODEL_ROUTE_A5`, and `ACTIVE_MODEL_ROUTE_EMBEDDING` (declared in `docs/contracts/scaffold-contract.md`). The decision to ship these three specific routes is recorded in `approved-decisions-register.md` row D-MDL-001.

### `prompt_versions`

Seed three rows so `model_routes.prompt_version` has something to refer to (`model_routes` does not enforce a FK against `prompt_versions` at the DDL level, but `safety_suite_runs` does — and certification of these routes via T-005 requires the FK target to exist):

```sql
INSERT INTO prompt_versions (prompt_version, purpose, body, is_platform_owned, activated_at) VALUES
  ('qa_analyze@2026-05-01.1',  'query_analyzer', '-- placeholder; real body lands in T-004', true, now()),
  ('a5_compose@2026-05-01.1',  'compose',        '-- placeholder; real body lands in T-004', true, now()),
  ('embedding_none@2026-05-01.1', 'embedding',   '', true, now());
```

The `embedding_none@2026-05-01.1` row is a sentinel: embedding models do not consume a system prompt, but `model_routes.prompt_version` is `NOT NULL`. The sentinel body is the empty string by convention; the route's prompt is never read at inference time.

### `model_routes`

Three rows seed the certified-track routes for Phase 1. All three start at `certification_status='experiment'` per ADR-0004; promotion to `certified` runs through the safety-suite gate in T-005.

```sql
-- Phase 1 active routes — see approved-decisions-register.md row D-MDL-001
INSERT INTO model_routes (
    route_id,
    purpose,
    provider,
    model,
    prompt_version,
    schema_version,
    supports_prompt_cache,
    supports_batch,
    supports_json_mode,
    certification_status,
    created_at
) VALUES
  -- A1/A2 query analysis: Sonnet for fast, reliable structured output
  ('qa_analyze_anthropic@2026-05-01.1', 'query_analyzer', 'anthropic', 'claude-sonnet-4-6',
   'qa_analyze@2026-05-01.1', '1.0', true, false, true, 'experiment', now()),

  -- A5 evidence composition: Opus for lowest hallucination risk on grounded composition
  ('a5_compose_anthropic@2026-05-01.1', 'compose', 'anthropic', 'claude-opus-4-7',
   'a5_compose@2026-05-01.1', '1.0', true, false, true, 'experiment', now()),

  -- Embeddings: Phase 1 baseline per ADR-0006
  ('embedding_openai@2026-05-01.1', 'embedding', 'openai', 'text-embedding-3-small',
   'embedding_none@2026-05-01.1', '1.0', false, false, false, 'experiment', now());
```

**Verifier-judge route is intentionally absent.** Per decision register row G, A6's deterministic citation and quote-overlap checks run unconditionally; the optional consistency-judge LLM call runs only when a certified `verifier_judge` route exists. `ACTIVE_MODEL_ROUTE_VERIFIER` in `.env.example` is left blank, the registry returns no certified `verifier_judge` row, and A6 skips the optional judge.

These route IDs MUST match the values referenced by `ACTIVE_MODEL_ROUTE_A1A2`, `ACTIVE_MODEL_ROUTE_A5`, and `ACTIVE_MODEL_ROUTE_EMBEDDING` in `scaffold-contract.md` §.env.example exactly. A startup self-test in `app/main.py` looks up each of the three env-var route IDs in `model_routes` and refuses to boot if any row is missing.
