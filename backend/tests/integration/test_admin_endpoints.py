"""Integration tests for `/api/v1/admin/{queries,flagged,audit}` per T-006 B.0.

Each test seeds a small batch of rows for two tenants, then verifies:
- the new repository `list_by_tenant` methods return per-tenant data with
  cursor-based keyset pagination,
- the route handlers enforce the documented scopes,
- the flagged-query response strips `raw_sensitive_log_id` for non-admin readers.

Tests skip cleanly when Postgres is not reachable (per `conftest.py::postgres_available`).
"""

from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from app.domain.models.run_trace import RunTrace, RunTraceUsage
from app.main import app
from fastapi.testclient import TestClient

pytestmark = pytest.mark.asyncio


def _dev_header(
    *, tenant_id: str = "tn_test", role: str = "admin", user_id: str = "usr_test"
) -> dict[str, str]:
    payload = {"tenantId": tenant_id, "role": role, "userId": user_id}
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return {"x-dev-principal": encoded}


@pytest_asyncio.fixture()
async def seed_admin_fixtures(
    seed_tenant: tuple[str, str],
) -> AsyncIterator[tuple[str, str]]:
    """Seed three run_traces + three flagged_queries + three audit_entries for the
    test tenant, in well-defined ULID order (newest ID last)."""
    tenant_id, user_id = seed_tenant
    from app.domain.repositories._base import session_scope
    from app.domain.repositories.audit_repository import AuditRepository
    from app.domain.repositories.flagged_query_repository import (
        FlaggedQueryRepository,
    )
    from app.domain.repositories.run_trace_repository import RunTraceRepository

    async with session_scope() as session:
        # Run traces: ulid.new() emits monotonically-increasing IDs.
        import ulid

        run_repo = RunTraceRepository(session)
        for i in range(3):
            trace = RunTrace(
                run_id=f"run_{ulid.new()!s}",
                tenant_id=tenant_id,
                user_id=user_id,
                started_at=datetime.now(UTC),
                cache_hit=False,
                stages=[],
                usage=RunTraceUsage(served_answer_count=1, fresh_model_run_count=1),
                final_handling="answer" if i % 2 == 0 else "block_with_redirect",
                final_confidence_tier="YELLOW",
                verifier_passed=True,
            )
            await run_repo.insert(trace)

        flagged_repo = FlaggedQueryRepository(session)
        for i in range(3):
            await flagged_repo.insert(
                tenant_id=tenant_id,
                user_id=user_id,
                query_text_redacted=f"[redacted query {i}]",
                flag_reason="hard_safety_trigger" if i == 0 else "verifier_failed",
                raw_sensitive_log_id=f"rsl_{i}",
                sensitivity_primary="pastoral_advice",
                risk_flags=["self_harm"] if i == 0 else [],
            )

        audit_repo = AuditRepository(session)
        for i in range(3):
            await audit_repo.insert(
                tenant_id=tenant_id,
                actor_user_id=user_id,
                actor_role="admin",
                action="chunk_approved" if i % 2 == 0 else "raw_sensitive_view",
                resource_type="chunk",
                resource_id=f"chk_{i}",
            )

        await session.commit()

    yield tenant_id, user_id


async def test_run_trace_list_by_tenant_paginates(
    seed_admin_fixtures: tuple[str, str],
) -> None:
    tenant_id, _ = seed_admin_fixtures
    from app.domain.repositories._base import session_scope
    from app.domain.repositories.run_trace_repository import RunTraceRepository

    async with session_scope() as session:
        repo = RunTraceRepository(session)
        page1, cursor = await repo.list_by_tenant(tenant_id=tenant_id, limit=2)
    assert len(page1) == 2
    assert cursor is not None
    # Ordering is run_id DESC (newest-first via ULID).
    assert page1[0].run_id > page1[1].run_id

    async with session_scope() as session:
        repo = RunTraceRepository(session)
        page2, cursor2 = await repo.list_by_tenant(
            tenant_id=tenant_id, limit=2, cursor=cursor
        )
    assert len(page2) == 1
    assert cursor2 is None  # only 3 rows seeded
    # Pages do not overlap.
    assert {r.run_id for r in page1}.isdisjoint({r.run_id for r in page2})


async def test_run_trace_list_filter_by_handling(
    seed_admin_fixtures: tuple[str, str],
) -> None:
    tenant_id, _ = seed_admin_fixtures
    from app.domain.repositories._base import session_scope
    from app.domain.repositories.run_trace_repository import RunTraceRepository

    async with session_scope() as session:
        repo = RunTraceRepository(session)
        traces, _ = await repo.list_by_tenant(
            tenant_id=tenant_id, handling="block_with_redirect"
        )
    assert all(t.final_handling == "block_with_redirect" for t in traces)
    assert len(traces) >= 1


async def test_flagged_query_list_by_tenant_paginates(
    seed_admin_fixtures: tuple[str, str],
) -> None:
    tenant_id, _ = seed_admin_fixtures
    from app.domain.repositories._base import session_scope
    from app.domain.repositories.flagged_query_repository import (
        FlaggedQueryRepository,
    )

    async with session_scope() as session:
        repo = FlaggedQueryRepository(session)
        page1, cursor = await repo.list_by_tenant(tenant_id=tenant_id, limit=2)
    assert len(page1) == 2
    assert cursor is not None
    assert page1[0].flagged_query_id > page1[1].flagged_query_id


async def test_flagged_query_filter_by_flag_reason(
    seed_admin_fixtures: tuple[str, str],
) -> None:
    tenant_id, _ = seed_admin_fixtures
    from app.domain.repositories._base import session_scope
    from app.domain.repositories.flagged_query_repository import (
        FlaggedQueryRepository,
    )

    async with session_scope() as session:
        repo = FlaggedQueryRepository(session)
        rows, _ = await repo.list_by_tenant(
            tenant_id=tenant_id, flag_reason="hard_safety_trigger"
        )
    assert len(rows) == 1
    assert rows[0].flag_reason == "hard_safety_trigger"


async def test_audit_list_by_tenant_paginates(
    seed_admin_fixtures: tuple[str, str],
) -> None:
    tenant_id, _ = seed_admin_fixtures
    from app.domain.repositories._base import session_scope
    from app.domain.repositories.audit_repository import AuditRepository

    async with session_scope() as session:
        repo = AuditRepository(session)
        page1, cursor = await repo.list_by_tenant(tenant_id=tenant_id, limit=2)
    assert len(page1) == 2
    assert cursor is not None
    assert page1[0].audit_id > page1[1].audit_id


async def test_audit_filter_by_action(
    seed_admin_fixtures: tuple[str, str],
) -> None:
    tenant_id, _ = seed_admin_fixtures
    from app.domain.repositories._base import session_scope
    from app.domain.repositories.audit_repository import AuditRepository

    async with session_scope() as session:
        repo = AuditRepository(session)
        rows, _ = await repo.list_by_tenant(
            tenant_id=tenant_id, action="raw_sensitive_view"
        )
    assert all(r.action == "raw_sensitive_view" for r in rows)
    assert len(rows) >= 1


async def test_get_admin_queries_endpoint(
    seed_admin_fixtures: tuple[str, str],
) -> None:
    tenant_id, _ = seed_admin_fixtures
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/admin/queries",
            headers=_dev_header(tenant_id=tenant_id, role="content_manager"),
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "items" in body and "nextCursor" in body
    assert len(body["items"]) == 3
    assert all(item["tenantId"] == tenant_id for item in body["items"])


async def test_get_admin_queries_rejects_member_role(
    seed_admin_fixtures: tuple[str, str],
) -> None:
    tenant_id, _ = seed_admin_fixtures
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/admin/queries",
            headers=_dev_header(tenant_id=tenant_id, role="member"),
        )
    assert response.status_code == 403, response.text


async def test_get_admin_flagged_strips_raw_log_id_for_content_manager(
    seed_admin_fixtures: tuple[str, str],
) -> None:
    tenant_id, _ = seed_admin_fixtures
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/admin/flagged",
            headers=_dev_header(tenant_id=tenant_id, role="content_manager"),
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["items"]) == 3
    for item in body["items"]:
        assert item["rawSensitiveLogId"] is None, (
            "content_manager must not see rawSensitiveLogId"
        )


async def test_get_admin_flagged_keeps_raw_log_id_for_admin(
    seed_admin_fixtures: tuple[str, str],
) -> None:
    tenant_id, _ = seed_admin_fixtures
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/admin/flagged",
            headers=_dev_header(tenant_id=tenant_id, role="admin"),
        )
    assert response.status_code == 200, response.text
    body = response.json()
    raw_ids = [item["rawSensitiveLogId"] for item in body["items"]]
    assert all(rid is not None for rid in raw_ids), (
        "admin must see rawSensitiveLogId"
    )


async def test_get_admin_audit_requires_admin_role(
    seed_admin_fixtures: tuple[str, str],
) -> None:
    tenant_id, _ = seed_admin_fixtures
    with TestClient(app) as client:
        cm_response = client.get(
            "/api/v1/admin/audit",
            headers=_dev_header(tenant_id=tenant_id, role="content_manager"),
        )
    assert cm_response.status_code == 403, cm_response.text

    with TestClient(app) as client:
        admin_response = client.get(
            "/api/v1/admin/audit",
            headers=_dev_header(tenant_id=tenant_id, role="admin"),
        )
    assert admin_response.status_code == 200, admin_response.text
    body = admin_response.json()
    assert len(body["items"]) == 3


async def test_get_admin_queries_pagination_cursor(
    seed_admin_fixtures: tuple[str, str],
) -> None:
    tenant_id, _ = seed_admin_fixtures
    with TestClient(app) as client:
        first = client.get(
            "/api/v1/admin/queries?limit=2",
            headers=_dev_header(tenant_id=tenant_id, role="admin"),
        )
    assert first.status_code == 200
    first_body = first.json()
    assert len(first_body["items"]) == 2
    cursor = first_body["nextCursor"]
    assert cursor is not None

    with TestClient(app) as client:
        second = client.get(
            f"/api/v1/admin/queries?limit=2&cursor={cursor}",
            headers=_dev_header(tenant_id=tenant_id, role="admin"),
        )
    assert second.status_code == 200
    second_body = second.json()
    assert len(second_body["items"]) == 1
    assert second_body["nextCursor"] is None
    # Pages do not overlap.
    first_ids = {item["runId"] for item in first_body["items"]}
    second_ids = {item["runId"] for item in second_body["items"]}
    assert first_ids.isdisjoint(second_ids)
