"""Grant LOGIN to app_runtime so the request path can connect as a non-superuser (ADR-0016).

Migration 0002 created `app_runtime` as NOLOGIN (a privilege-holding role only). For RLS to
actually enforce tenant isolation at runtime, the FastAPI request path must connect AS app_runtime
(a superuser/owner bypasses RLS). This migration makes app_runtime a login role; the password is
provisioned out-of-band (Railway secret / `ALTER ROLE ... PASSWORD`), never committed here
(CLAUDE.md §2). `DATABASE_URL` then points at app_runtime and `DATABASE_ADMIN_URL` at app_admin.

Idempotent and privilege-tolerant, mirroring 0002: on managed Postgres where the migrator lacks
ALTER ROLE, the operator grants LOGIN out-of-band and this is a no-op. Dev keeps using the single
superuser URL (app_runtime simply gains the LOGIN attribute, unused until DATABASE_URL switches).

Revision ID: 0005_app_runtime_login
Revises: 0004_embedding_candidates
Create Date: 2026-05-31
"""

# Created by: T-008 GS-1 (Postgres RLS enforcement)

from __future__ import annotations

from alembic import op

revision = "0005_app_runtime_login"
down_revision = "0004_embedding_candidates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime') THEN
                BEGIN
                    EXECUTE 'ALTER ROLE app_runtime LOGIN';
                EXCEPTION WHEN insufficient_privilege THEN
                    RAISE NOTICE 'skipping ALTER ROLE app_runtime LOGIN (insufficient privilege)';
                END;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime') THEN
                BEGIN
                    EXECUTE 'ALTER ROLE app_runtime NOLOGIN';
                EXCEPTION WHEN insufficient_privilege THEN
                    RAISE NOTICE 'skipping ALTER ROLE app_runtime NOLOGIN (insufficient privilege)';
                END;
            END IF;
        END
        $$;
        """
    )
