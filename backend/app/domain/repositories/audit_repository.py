"""AuditEntry repository — `audit_entries` table (append-only)."""

from __future__ import annotations

import ulid
from sqlalchemy import text

from app.domain.models.audit_entry import AuditEntry
from app.domain.repositories._base import AsyncSession, assert_tenant


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(
        self,
        *,
        tenant_id: str,
        actor_user_id: str,
        actor_role: str,
        action: str,
        resource_type: str,
        resource_id: str,
        details: dict[str, object] | None = None,
        ip_address: str | None = None,
    ) -> str:
        assert_tenant(tenant_id)
        audit_id = f"aud_{ulid.new()!s}"
        await self._session.execute(
            text(
                """
                INSERT INTO audit_entries (
                    audit_id, tenant_id, actor_user_id, actor_role, action, resource_type,
                    resource_id, details, ip_address, occurred_at
                ) VALUES (
                    :audit_id, :tenant_id, :actor_user_id, :actor_role, :action,
                    :resource_type, :resource_id, CAST(:details AS jsonb), :ip_address,
                    now()
                )
                """
            ),
            {
                "audit_id": audit_id,
                "tenant_id": tenant_id,
                "actor_user_id": actor_user_id,
                "actor_role": actor_role,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "details": _json(details or {}),
                "ip_address": ip_address,
            },
        )
        return audit_id

    async def list_by_resource(
        self, *, tenant_id: str, resource_type: str, resource_id: str
    ) -> list[AuditEntry]:
        assert_tenant(tenant_id)
        result = await self._session.execute(
            text(
                """
                SELECT * FROM audit_entries
                WHERE tenant_id = :tenant_id
                  AND resource_type = :resource_type
                  AND resource_id = :resource_id
                ORDER BY occurred_at ASC
                """
            ),
            {
                "tenant_id": tenant_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
            },
        )
        rows = result.mappings().all()
        return [
            AuditEntry(
                audit_id=r["audit_id"],
                tenant_id=r["tenant_id"],
                actor_user_id=r["actor_user_id"],
                actor_role=r["actor_role"],
                action=r["action"],
                resource_type=r["resource_type"],
                resource_id=r["resource_id"],
                details=r.get("details") or {},
                ip_address=str(r["ip_address"]) if r.get("ip_address") else None,
                occurred_at=r["occurred_at"],
            )
            for r in rows
        ]


def _json(value: dict[str, object]) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, default=str)


__all__ = ["AuditRepository"]
