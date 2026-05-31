"""Postgres Row-Level Security + per-role app accounts (ADR-0016, T-005).

Revision ID: 0002_rls_and_app_roles
Revises: 0001_initial
Create Date: 2026-05-27
"""

# Created by: T-005 (cache/logs/billing/privacy)

from __future__ import annotations

from alembic import op

revision = "0002_rls_and_app_roles"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

# Every tenant-scoped table gets ENABLE + FORCE ROW LEVEL SECURITY plus a single
# tenant_isolation_policy. The GUC `app.current_tenant_id` is set per-request by
# `app/core/tenant_context.py:set_tenant_guc` and read here via current_setting(..., true).
# The second arg `true` returns NULL when the GUC is unset → the policy returns zero rows
# (fail closed) instead of erroring.
RLS_TABLES = (
    "tenants",
    "users",
    "sources",
    "chunks",
    "sessions",
    "ingest_jobs",
    "run_traces",
    "flagged_queries",
    "raw_sensitive_logs",
    "audit_entries",
    "billing_usage",
    "graph_candidates",
)


def upgrade() -> None:
    # Roles. Idempotent: skip silently if the role already exists or if the migrator lacks
    # CREATEROLE (managed Postgres providers often do; in that case the operator provisions
    # roles out-of-band and this DO block is a no-op).
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime') THEN
                BEGIN
                    EXECUTE 'CREATE ROLE app_runtime NOLOGIN';
                EXCEPTION WHEN insufficient_privilege THEN
                    RAISE NOTICE 'skipping CREATE ROLE app_runtime (insufficient privilege)';
                END;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
                BEGIN
                    EXECUTE 'CREATE ROLE app_admin NOLOGIN BYPASSRLS';
                EXCEPTION WHEN insufficient_privilege THEN
                    RAISE NOTICE 'skipping CREATE ROLE app_admin (insufficient privilege)';
                END;
            END IF;
        END
        $$;
        """
    )

    # Privileges. The app_runtime role gets DML on every multi-tenant table; app_admin gets
    # everything. Skip silently if the role wasn't actually created above.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime') THEN
                EXECUTE 'GRANT USAGE ON SCHEMA public TO app_runtime';
                EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_runtime';
                EXECUTE 'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_runtime';
                EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_runtime';
                EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app_runtime';
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
                EXECUTE 'GRANT ALL ON SCHEMA public TO app_admin';
                EXECUTE 'GRANT ALL ON ALL TABLES IN SCHEMA public TO app_admin';
                EXECUTE 'GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO app_admin';
                EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO app_admin';
                EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO app_admin';
            END IF;
        END
        $$;
        """
    )

    # Enable RLS + FORCE + tenant_isolation_policy on every multi-tenant table.
    # Each table is guarded by a `to_regclass` existence check so a table that hasn't been
    # created yet is skipped silently instead of aborting the whole migration. This matters for
    # `graph_candidates`, which ADR-0016 scopes in "once REC-013 lands" — the table is named in
    # RLS_TABLES (so RLS auto-applies the moment it exists) but no migration creates it yet. When
    # REC-013's migration adds the table, re-running this is unnecessary; its own migration should
    # enable RLS, and this guard keeps a fresh `alembic upgrade head` green in the meantime.
    # Mirrors the role-creation guards above. (Table names are trusted constants, not user input.)
    for table in RLS_TABLES:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF to_regclass('public.{table}') IS NOT NULL THEN
                    EXECUTE 'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY';
                    EXECUTE 'ALTER TABLE {table} FORCE ROW LEVEL SECURITY';
                    EXECUTE 'DROP POLICY IF EXISTS tenant_isolation_policy ON {table}';
                    EXECUTE 'CREATE POLICY tenant_isolation_policy ON {table}
                        USING (tenant_id = current_setting(''app.current_tenant_id'', true))
                        WITH CHECK (tenant_id = current_setting(''app.current_tenant_id'', true))';
                ELSE
                    RAISE NOTICE 'skipping RLS for {table} (table does not exist yet)';
                END IF;
            END
            $$;
            """
        )


def downgrade() -> None:
    # Same existence guard as upgrade(): tables not yet created (e.g. graph_candidates) are
    # skipped rather than erroring on a non-existent relation.
    for table in RLS_TABLES:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF to_regclass('public.{table}') IS NOT NULL THEN
                    EXECUTE 'DROP POLICY IF EXISTS tenant_isolation_policy ON {table}';
                    EXECUTE 'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY';
                    EXECUTE 'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY';
                END IF;
            END
            $$;
            """
        )
    # Roles are intentionally not dropped — they may still own objects or be in use.
