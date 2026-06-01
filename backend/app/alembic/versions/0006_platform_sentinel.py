"""Seed a platform sentinel tenant + system user for actorless platform audit rows.

The retention worker runs globally across all tenants as `app_admin` (BYPASSRLS) with no human
actor, but `audit_entries` requires `tenant_id`, `actor_user_id`, and `actor_role` (all NOT NULL,
the first two FK-constrained). So a `retention_purged` audit row — the DB-visible signal that
Phase-1→2 exit criterion #8c reads (see scripts/exit_criteria_dashboard.py) — needs a stable
sentinel to attribute itself to.

This seeds:
  - tenant `tn_platform` — a non-customer, platform-owned tenant (status 'active', region 'us').
  - user   `usr_system`  — a non-human service account under it. `users.role` is CHECK-constrained
      to ('member','scholar','content_manager','admin','owner'); we use the least-privileged
      'member' since this account never authenticates and holds no scopes. The audit row's own
      `actor_role` column (free text, no CHECK) records the descriptive 'system' instead.

Idempotent (`ON CONFLICT DO NOTHING`) so re-runs and partially-seeded envs are safe.

Revision ID: 0006_platform_sentinel
Revises: 0005_app_runtime_login
Create Date: 2026-06-01
"""

# Created by: Phase-1 exit-criteria dashboard work (criterion #8c retention audit row)

from __future__ import annotations

from alembic import op

revision = "0006_platform_sentinel"
down_revision = "0005_app_runtime_login"
branch_labels = None
depends_on = None

PLATFORM_TENANT_ID = "tn_platform"
SYSTEM_USER_ID = "usr_system"


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO tenants (tenant_id, name, clerk_org_id, status, data_region)
        VALUES ('tn_platform', 'Platform (system)', 'clerk_org_platform_sentinel', 'active', 'us')
        ON CONFLICT (tenant_id) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO users (user_id, clerk_user_id, tenant_id, role, status)
        VALUES ('usr_system', 'clerk_usr_system_sentinel', 'tn_platform', 'member', 'active')
        ON CONFLICT (user_id) DO NOTHING;
        """
    )


def downgrade() -> None:
    # Remove the sentinel user first (FK from users -> tenants), then the tenant. Any audit_entries
    # written against the sentinel would block this via FK — acceptable, since downgrading after the
    # retention worker has run is not an expected path and the rows are an append-only audit trail.
    op.execute("DELETE FROM users WHERE user_id = 'usr_system';")
    op.execute("DELETE FROM tenants WHERE tenant_id = 'tn_platform';")
