#!/usr/bin/env python3
"""Seed the private-beta tenant + founder owner user into a freshly-migrated database.

The repo ships no seed migration for the live `tn_orthodoxethos` tenant / `usr_founder` owner
(migrations create schema only; those ids exist only in test fixtures). This CLI inserts the two
rows so a freshly-migrated deployment has a tenant to scope data to and an owner to log in as and
to attribute the Phase-1->2 exit-criteria attestations to (see scripts/record_audit_event.py).

Run AFTER `alembic upgrade head`, against the ADMIN connection (DATABASE_ADMIN_URL -> the
`app_admin` BYPASSRLS role): the RLS policies from migration 0002 otherwise block inserting a
brand-new tenant. Idempotent — re-running skips rows that already exist (ON CONFLICT DO NOTHING).

`--clerk-org-id` / `--clerk-user-id` must be the REAL ids from your Clerk organization and user
(both are NOT NULL UNIQUE and are how Clerk-authenticated requests resolve to these rows). The
command refuses to write while either still contains the REPLACE_ME placeholder. Use --dry-run to
print the planned rows without a database.

Usage:
  python scripts/seed_beta_tenant.py --db-url "$DATABASE_ADMIN_URL" \\
      --clerk-org-id org_xxx --clerk-user-id user_xxx --email founder@example.com
"""
from __future__ import annotations

import argparse
import sys

try:  # SQLAlchemy + a sync driver are only needed to actually write.
    from sqlalchemy import create_engine, text
except ImportError:  # pragma: no cover - import guard so --help / --dry-run work without the dep
    create_engine = None  # type: ignore[assignment]
    text = None  # type: ignore[assignment]

_PLACEHOLDER = "REPLACE_ME"

_TENANT_SQL = """
INSERT INTO tenants (tenant_id, name, clerk_org_id, stripe_customer_id, status, data_region)
VALUES (:tenant_id, :name, :clerk_org_id, :stripe_customer_id, 'active', :data_region)
ON CONFLICT (tenant_id) DO NOTHING
"""

_USER_SQL = """
INSERT INTO users (user_id, clerk_user_id, tenant_id, email, role, status)
VALUES (:user_id, :clerk_user_id, :tenant_id, :email, :role, 'active')
ON CONFLICT (user_id) DO NOTHING
"""


def _normalize_db_url(db_url: str) -> str:
    """Pin the sync psycopg (v3) driver, matching record_audit_event.py / the dashboard."""
    for prefix in ("postgresql://", "postgres://"):
        if db_url.startswith(prefix):
            return "postgresql+psycopg://" + db_url[len(prefix) :]
    return db_url


def _seed(db_url: str, tenant: dict[str, object], user: dict[str, object]) -> int:
    if create_engine is None:  # pragma: no cover - guarded import
        raise RuntimeError(
            "SQLAlchemy + psycopg are required to write "
            "(pip install 'sqlalchemy>=2' 'psycopg[binary]')."
        )
    engine = create_engine(_normalize_db_url(db_url), future=True, pool_pre_ping=True)
    with engine.begin() as conn:
        t_rows = conn.execute(text(_TENANT_SQL), tenant).rowcount
        u_rows = conn.execute(text(_USER_SQL), user).rowcount
    t_status = "inserted" if t_rows else "already present (skipped)"
    u_status = "inserted" if u_rows else "already present (skipped)"
    print(f"tenants: {t_status} — {tenant['tenant_id']}")
    print(f"users:   {u_status} — {user['user_id']} (role={user['role']})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--db-url", help="PostgreSQL admin URL (required unless --dry-run)")
    parser.add_argument("--tenant-id", default="tn_orthodoxethos")
    parser.add_argument("--tenant-name", default="Orthodox Ethos")
    parser.add_argument("--clerk-org-id", default=f"org_{_PLACEHOLDER}", help="Clerk org id")
    parser.add_argument("--data-region", choices=["us", "eu"], default="us")
    parser.add_argument("--stripe-customer-id", default=None)
    parser.add_argument("--user-id", default="usr_founder")
    parser.add_argument("--clerk-user-id", default=f"user_{_PLACEHOLDER}", help="Clerk user id")
    parser.add_argument(
        "--role",
        choices=["member", "scholar", "content_manager", "admin", "owner"],
        default="owner",
    )
    parser.add_argument("--email", default=None, help="founder email (optional)")
    parser.add_argument("--dry-run", action="store_true", help="print the rows without writing")
    args = parser.parse_args(argv)

    tenant = {
        "tenant_id": args.tenant_id,
        "name": args.tenant_name,
        "clerk_org_id": args.clerk_org_id,
        "stripe_customer_id": args.stripe_customer_id,
        "data_region": args.data_region,
    }
    user = {
        "user_id": args.user_id,
        "clerk_user_id": args.clerk_user_id,
        "tenant_id": args.tenant_id,
        "email": args.email,
        "role": args.role,
    }

    print("tenant:", tenant)
    print("user:  ", user)

    if args.dry_run:
        print("\n[dry-run] not written.")
        return 0
    if _PLACEHOLDER in args.clerk_org_id or _PLACEHOLDER in args.clerk_user_id:
        print(
            f"\nERROR: pass real --clerk-org-id / --clerk-user-id (contain {_PLACEHOLDER!r}).",
            file=sys.stderr,
        )
        return 2
    if not args.db_url:
        print("\nERROR: --db-url is required unless --dry-run.", file=sys.stderr)
        return 2
    return _seed(args.db_url, tenant, user)


if __name__ == "__main__":
    sys.exit(main())
