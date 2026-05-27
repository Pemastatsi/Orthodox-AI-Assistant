"""AuditEntry repository — `audit_entries` table (append-only)."""

from __future__ import annotations

from typing import Any

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
        return [_row_to_audit_entry(r) for r in rows]

    async def list_by_tenant(
        self,
        *,
        tenant_id: str,
        cursor: str | None = None,
        limit: int = 25,
        action: str | None = None,
        resource_type: str | None = None,
        since: Any | None = None,
    ) -> tuple[list[AuditEntry], str | None]:
        """Keyset pagination by `audit_id DESC` (ULIDs are time-sortable).
        Returns up to `limit` rows + nextCursor when more remain."""
        assert_tenant(tenant_id)
        clauses = ["tenant_id = :tenant_id"]
        params: dict[str, Any] = {"tenant_id": tenant_id, "limit": limit + 1}
        if cursor:
            clauses.append("audit_id < :cursor")
            params["cursor"] = cursor
        if action is not None:
            clauses.append("action = :action")
            params["action"] = action
        if resource_type is not None:
            clauses.append("resource_type = :resource_type")
            params["resource_type"] = resource_type
        if since is not None:
            clauses.append("occurred_at >= :since")
            params["since"] = since
        sql = (
            "SELECT * FROM audit_entries WHERE "
            + " AND ".join(clauses)
            + " ORDER BY audit_id DESC LIMIT :limit"
        )
        result = await self._session.execute(text(sql), params)
        rows = list(result.mappings().all())
        items = [_row_to_audit_entry(r) for r in rows[:limit]]
        next_cursor = rows[limit - 1]["audit_id"] if len(rows) > limit else None
        return items, next_cursor


def _row_to_audit_entry(row: Any) -> AuditEntry:
    return AuditEntry(
        audit_id=row["audit_id"],
        tenant_id=row["tenant_id"],
        actor_user_id=row["actor_user_id"],
        actor_role=row["actor_role"],
        action=row["action"],
        resource_type=row["resource_type"],
        resource_id=row["resource_id"],
        details=row.get("details") or {},
        ip_address=str(row["ip_address"]) if row.get("ip_address") else None,
        occurred_at=row["occurred_at"],
    )


def _json(value: dict[str, object]) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, default=str)


__all__ = ["AuditRepository"]
