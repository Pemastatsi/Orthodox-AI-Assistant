"""AuditRepository insert + read."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_insert_then_read_back(seed_tenant: tuple[str, str]) -> None:
    tenant_id, user_id = seed_tenant
    from app.domain.repositories._base import session_scope
    from app.domain.repositories.audit_repository import AuditRepository

    async with session_scope() as session:
        repo = AuditRepository(session)
        audit_id = await repo.insert(
            tenant_id=tenant_id,
            actor_user_id=user_id,
            actor_role="admin",
            action="raw_sensitive_view",
            resource_type="raw_sensitive_log",
            resource_id="rsl_01HZX",
            details={"reason": "review", "viewer_seat": "admin-1"},
            ip_address="127.0.0.1",
        )

    assert audit_id.startswith("aud_")

    async with session_scope() as session:
        repo = AuditRepository(session)
        rows = await repo.list_by_resource(
            tenant_id=tenant_id,
            resource_type="raw_sensitive_log",
            resource_id="rsl_01HZX",
        )

    assert len(rows) == 1
    row = rows[0]
    assert row.audit_id == audit_id
    assert row.action == "raw_sensitive_view"
    assert row.actor_role == "admin"
    assert row.details == {"reason": "review", "viewer_seat": "admin-1"}


@pytest.mark.asyncio
async def test_resource_id_scopes_lookup(seed_tenant: tuple[str, str]) -> None:
    """Two audit rows on different resources are not returned together."""
    tenant_id, user_id = seed_tenant
    from app.domain.repositories._base import session_scope
    from app.domain.repositories.audit_repository import AuditRepository

    async with session_scope() as session:
        repo = AuditRepository(session)
        await repo.insert(
            tenant_id=tenant_id,
            actor_user_id=user_id,
            actor_role="admin",
            action="chunk_approved",
            resource_type="chunk",
            resource_id="chk_A",
        )
        await repo.insert(
            tenant_id=tenant_id,
            actor_user_id=user_id,
            actor_role="admin",
            action="chunk_approved",
            resource_type="chunk",
            resource_id="chk_B",
        )

    async with session_scope() as session:
        repo = AuditRepository(session)
        a_rows = await repo.list_by_resource(
            tenant_id=tenant_id, resource_type="chunk", resource_id="chk_A"
        )
        b_rows = await repo.list_by_resource(
            tenant_id=tenant_id, resource_type="chunk", resource_id="chk_B"
        )

    assert [r.resource_id for r in a_rows] == ["chk_A"]
    assert [r.resource_id for r in b_rows] == ["chk_B"]
