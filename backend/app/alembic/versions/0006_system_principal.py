"""Seed the platform system principal (tn_system / usr_system) for system-actor audit rows.

Phase-1->2 exit criterion #8 requires the retention worker to write an `audit_entries` row with
`action='retention_purged'`. That sweep is a cross-tenant system action with no per-tenant actor,
and `audit_entries.tenant_id` / `actor_user_id` are NOT NULL FKs — so we seed a dedicated platform
service account the worker writes under. Idempotent (`ON CONFLICT DO NOTHING`) so re-running, or an
already-onboarded database, is a no-op. Keep the IDs in sync with
`app/workers/tasks/retention_cleanup.py` (`_SYSTEM_TENANT_ID` / `_SYSTEM_USER_ID`).

Revision ID: 0006_system_principal
Revises: 0005_app_runtime_login
Create Date: 2026-06-04
"""

from __future__ import annotations

from alembic import op

revision = "0006_system_principal"
down_revision = "0005_app_runtime_login"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO tenants (tenant_id, name, clerk_org_id, status, data_region)
        VALUES ('tn_system', 'Platform System', 'org_system', 'active', 'us')
        ON CONFLICT (tenant_id) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO users (user_id, clerk_user_id, tenant_id, role, status)
        VALUES ('usr_system', 'user_system', 'tn_system', 'owner', 'active')
        ON CONFLICT (user_id) DO NOTHING;
        """
    )


def downgrade() -> None:
    # Audit rows authored by the system principal must go first to satisfy the actor_user_id FK.
    # (The audit log is append-only in normal operation; a migration downgrade is the exception.)
    op.execute("DELETE FROM audit_entries WHERE actor_user_id = 'usr_system';")
    op.execute("DELETE FROM users WHERE user_id = 'usr_system';")
    op.execute("DELETE FROM tenants WHERE tenant_id = 'tn_system';")
