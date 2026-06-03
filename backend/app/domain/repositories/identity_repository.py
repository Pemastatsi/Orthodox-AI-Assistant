"""Identity resolution for the Clerk auth path — reads `tenants`/`users` by Clerk IDs and
JIT-provisions first-seen users.

Runs on the `app_admin` (BYPASSRLS) session because auth must resolve the tenant *before* a
tenant GUC can be set (the RLS chicken-and-egg); see `app/api/v1/_deps.py` + ADR-0016. Bounded by
design to three operations: tenant lookup, user lookup, user JIT-insert.
"""

from __future__ import annotations

from dataclasses import dataclass

import ulid
from sqlalchemy import text

from app.domain.models.principal import DataRegion, Role
from app.domain.repositories._base import AsyncSession


@dataclass(frozen=True)
class TenantAuthRow:
    tenant_id: str
    status: str
    data_region: DataRegion


@dataclass(frozen=True)
class UserAuthRow:
    user_id: str
    tenant_id: str
    role: Role


class IdentityRepository:
    """Pre-tenant identity lookups for the Clerk auth path (admin / BYPASSRLS session)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_tenant_by_clerk_org(self, clerk_org_id: str) -> TenantAuthRow | None:
        result = await self._session.execute(
            text("SELECT tenant_id, status, data_region FROM tenants WHERE clerk_org_id = :org"),
            {"org": clerk_org_id},
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return TenantAuthRow(
            tenant_id=row["tenant_id"],
            status=row["status"],
            data_region=row["data_region"],
        )

    async def get_user_by_clerk_id(self, clerk_user_id: str) -> UserAuthRow | None:
        result = await self._session.execute(
            text("SELECT user_id, tenant_id, role FROM users WHERE clerk_user_id = :uid"),
            {"uid": clerk_user_id},
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return UserAuthRow(user_id=row["user_id"], tenant_id=row["tenant_id"], role=row["role"])

    async def jit_provision_user(self, *, clerk_user_id: str, tenant_id: str) -> UserAuthRow:
        """Insert a first-seen Clerk user as role='member', status='active' (auth-context.md
        step 5 — JIT NEVER assigns a non-member role). `ON CONFLICT` makes a concurrent
        first-request race return the existing row instead of raising a unique violation."""
        result = await self._session.execute(
            text(
                """
                INSERT INTO users (user_id, clerk_user_id, tenant_id, role, status,
                                   created_at, last_seen_at)
                VALUES (:user_id, :clerk_user_id, :tenant_id, 'member', 'active',
                        now(), now())
                ON CONFLICT (clerk_user_id) DO UPDATE SET last_seen_at = now()
                RETURNING user_id, tenant_id, role
                """
            ),
            {
                "user_id": f"usr_{ulid.new()}",
                "clerk_user_id": clerk_user_id,
                "tenant_id": tenant_id,
            },
        )
        row = result.mappings().one()
        return UserAuthRow(user_id=row["user_id"], tenant_id=row["tenant_id"], role=row["role"])


__all__ = ["IdentityRepository", "TenantAuthRow", "UserAuthRow"]
