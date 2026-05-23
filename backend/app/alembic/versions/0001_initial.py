"""Initial schema — `docs/contracts/db-schema.md` rendered 1:1.

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-23
"""

# Created by: T-001 scaffold

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext;")

    op.execute(
        """
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
        """
    )
    op.execute("CREATE INDEX idx_tenants_clerk_org ON tenants(clerk_org_id);")
    op.execute(
        "CREATE INDEX idx_tenants_stripe_customer ON tenants(stripe_customer_id) "
        "WHERE stripe_customer_id IS NOT NULL;"
    )

    op.execute(
        """
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
        """
    )
    op.execute("CREATE INDEX idx_users_tenant ON users(tenant_id);")
    op.execute(
        "CREATE INDEX idx_users_email ON users(tenant_id, email) WHERE email IS NOT NULL;"
    )

    op.execute(
        """
        CREATE TABLE sources (
            source_id                text PRIMARY KEY,
            tenant_id                text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
            title                    text NOT NULL,
            father                   text,
            work                     text,
            language                 text NOT NULL CHECK (language IN ('en','el','mixed')) DEFAULT 'en',
            source_type              text NOT NULL CHECK (source_type IN ('pdf','txt','md','docx')),
            source_hash              text NOT NULL CHECK (source_hash ~ '^sha256:[0-9a-f]{64}$'),
            extraction_method        text NOT NULL,
            corpus_origin            text,
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
        """
    )
    op.execute("CREATE INDEX idx_sources_tenant_approved ON sources(tenant_id, approved);")
    op.execute("CREATE INDEX idx_sources_corpus_version ON sources(tenant_id, corpus_version);")
    op.execute(
        "CREATE INDEX idx_sources_corpus_origin ON sources(tenant_id, corpus_origin) "
        "WHERE corpus_origin IS NOT NULL;"
    )

    op.execute(
        """
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
            page                text,
            timestamp           text,
            language            text NOT NULL DEFAULT 'en',
            categories          text[] NOT NULL DEFAULT '{}',
            section_path        text[] NOT NULL DEFAULT '{}',
            page_start          integer CHECK (page_start IS NULL OR page_start >= 1),
            page_end            integer CHECK (page_end IS NULL OR page_end >= 1),
            parent_chunk_id     text REFERENCES chunks(chunk_id) ON DELETE SET NULL,
            embedding_model     text NOT NULL,
            embedding_dimension integer NOT NULL,
            corpus_version      text NOT NULL,
            review_note         text,
            created_at          timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, chunk_hash),
            CHECK (page_end IS NULL OR page_start IS NULL OR page_end >= page_start)
        );
        """
    )
    op.execute(
        "CREATE INDEX idx_chunks_tenant_approved ON chunks(tenant_id, approved, visibility);"
    )
    op.execute("CREATE INDEX idx_chunks_source ON chunks(source_id);")
    op.execute(
        "CREATE INDEX idx_chunks_parent ON chunks(parent_chunk_id) "
        "WHERE parent_chunk_id IS NOT NULL;"
    )

    op.execute(
        """
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
        """
    )
    op.execute("CREATE INDEX idx_sessions_tenant_user ON sessions(tenant_id, user_id);")
    op.execute("CREATE INDEX idx_sessions_expiry ON sessions(expires_at);")

    op.execute(
        """
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
        """
    )
    op.execute("CREATE INDEX idx_ingest_jobs_tenant_status ON ingest_jobs(tenant_id, status);")

    op.execute(
        """
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
            evidence_packet_ref    text,
            created_at             timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        "CREATE INDEX idx_run_traces_tenant_started ON run_traces(tenant_id, started_at DESC);"
    )
    op.execute(
        "CREATE INDEX idx_run_traces_user ON run_traces(tenant_id, user_id, started_at DESC);"
    )

    # raw_sensitive_logs must precede flagged_queries because flagged_queries.raw_sensitive_log_id
    # references it (db-schema.md cross-table invariant #4).
    op.execute(
        """
        CREATE TABLE raw_sensitive_logs (
            log_id          text PRIMARY KEY,
            tenant_id       text NOT NULL REFERENCES tenants(tenant_id),
            user_id         text NOT NULL REFERENCES users(user_id),
            run_id          text REFERENCES run_traces(run_id),
            ciphertext      bytea NOT NULL,
            key_version     text NOT NULL,
            nonce           bytea NOT NULL,
            expires_at      timestamptz NOT NULL,
            created_at      timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute("CREATE INDEX idx_raw_sensitive_expiry ON raw_sensitive_logs(expires_at);")

    op.execute(
        """
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
            embedding            real[],
            embedding_model      text,
            cluster_id           text,
            created_at           timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        "CREATE INDEX idx_flagged_tenant_created ON flagged_queries(tenant_id, created_at DESC);"
    )
    op.execute(
        "CREATE INDEX idx_flagged_cluster ON flagged_queries(tenant_id, cluster_id) "
        "WHERE cluster_id IS NOT NULL;"
    )

    op.execute(
        """
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
        """
    )
    op.execute(
        "CREATE INDEX idx_audit_tenant_occurred ON audit_entries(tenant_id, occurred_at DESC);"
    )
    op.execute("CREATE INDEX idx_audit_resource ON audit_entries(resource_type, resource_id);")

    # prompt_versions must precede safety_suite_runs (FK target).
    op.execute(
        """
        CREATE TABLE prompt_versions (
            prompt_version    text PRIMARY KEY,
            purpose           text NOT NULL,
            body              text NOT NULL,
            is_platform_owned boolean NOT NULL DEFAULT true,
            activated_at      timestamptz,
            deprecated_at     timestamptz,
            created_at        timestamptz NOT NULL DEFAULT now()
        );
        """
    )

    op.execute(
        """
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
        """
    )
    op.execute(
        "CREATE INDEX idx_model_routes_purpose_status ON model_routes(purpose, certification_status);"
    )

    op.execute(
        """
        CREATE TABLE safety_suite_runs (
            safety_suite_run_id   text PRIMARY KEY,
            purpose               text NOT NULL CHECK (purpose IN ('query_analyzer','compose','verifier_judge','embedding')),
            provider              text NOT NULL CHECK (provider IN ('anthropic','openai')),
            model                 text NOT NULL,
            prompt_version        text NOT NULL,
            schema_version        text NOT NULL,
            case_count            integer NOT NULL CHECK (case_count = 20),
            case_run_ids          text[] NOT NULL,
            passed                boolean NOT NULL,
            failure_summary       jsonb,
            initiated_by          text NOT NULL REFERENCES users(user_id),
            started_at            timestamptz NOT NULL,
            finished_at           timestamptz NOT NULL,
            created_at            timestamptz NOT NULL DEFAULT now(),
            CHECK (cardinality(case_run_ids) = 20)
        );
        """
    )
    op.execute(
        "CREATE INDEX idx_safety_suite_purpose_passed "
        "ON safety_suite_runs(purpose, passed, finished_at DESC);"
    )

    op.execute(
        """
        ALTER TABLE model_routes
            ADD CONSTRAINT model_routes_safety_suite_run_id_fkey
            FOREIGN KEY (safety_suite_run_id) REFERENCES safety_suite_runs(safety_suite_run_id);
        """
    )
    op.execute(
        """
        ALTER TABLE safety_suite_runs
            ADD CONSTRAINT safety_suite_runs_prompt_version_fkey
            FOREIGN KEY (prompt_version) REFERENCES prompt_versions(prompt_version);
        """
    )

    op.execute(
        """
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
        """
    )
    op.execute("CREATE INDEX idx_billing_period_end ON billing_usage(period_end);")

    # Seed: prompt_versions (db-schema.md §First Migration Seed Data).
    op.execute(
        """
        INSERT INTO prompt_versions (prompt_version, purpose, body, is_platform_owned, activated_at) VALUES
          ('qa_analyze@2026-05-01.1',     'query_analyzer', '-- placeholder; real body lands in T-004', true, now()),
          ('a5_compose@2026-05-01.1',     'compose',        '-- placeholder; real body lands in T-004', true, now()),
          ('embedding_none@2026-05-01.1', 'embedding',      '', true, now());
        """
    )

    # Seed: model_routes (Phase 1 active routes per ADR-0004).
    op.execute(
        """
        INSERT INTO model_routes (
            route_id, purpose, provider, model, prompt_version, schema_version,
            supports_prompt_cache, supports_batch, supports_json_mode,
            certification_status, created_at
        ) VALUES
          ('qa_analyze_anthropic@2026-05-01.1', 'query_analyzer', 'anthropic', 'claude-sonnet-4-6',
           'qa_analyze@2026-05-01.1', '1.0', true, false, true, 'experiment', now()),
          ('a5_compose_anthropic@2026-05-01.1', 'compose', 'anthropic', 'claude-opus-4-7',
           'a5_compose@2026-05-01.1', '1.0', true, false, true, 'experiment', now()),
          ('embedding_openai@2026-05-01.1', 'embedding', 'openai', 'text-embedding-3-small',
           'embedding_none@2026-05-01.1', '1.0', false, false, false, 'experiment', now());
        """
    )


def downgrade() -> None:
    # Drop in reverse FK order. This downgrade exists for symmetry; production never runs it
    # (per db-schema.md §Migrations: forward-only).
    op.execute("DROP TABLE IF EXISTS billing_usage;")
    op.execute("ALTER TABLE IF EXISTS model_routes DROP CONSTRAINT IF EXISTS model_routes_safety_suite_run_id_fkey;")
    op.execute("ALTER TABLE IF EXISTS safety_suite_runs DROP CONSTRAINT IF EXISTS safety_suite_runs_prompt_version_fkey;")
    op.execute("DROP TABLE IF EXISTS safety_suite_runs;")
    op.execute("DROP TABLE IF EXISTS model_routes;")
    op.execute("DROP TABLE IF EXISTS prompt_versions;")
    op.execute("DROP TABLE IF EXISTS audit_entries;")
    op.execute("DROP TABLE IF EXISTS flagged_queries;")
    op.execute("DROP TABLE IF EXISTS raw_sensitive_logs;")
    op.execute("DROP TABLE IF EXISTS run_traces;")
    op.execute("DROP TABLE IF EXISTS ingest_jobs;")
    op.execute("DROP TABLE IF EXISTS sessions;")
    op.execute("DROP TABLE IF EXISTS chunks;")
    op.execute("DROP TABLE IF EXISTS sources;")
    op.execute("DROP TABLE IF EXISTS users;")
    op.execute("DROP TABLE IF EXISTS tenants;")
