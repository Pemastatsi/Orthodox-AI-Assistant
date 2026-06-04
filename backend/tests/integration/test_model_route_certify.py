"""Integration tests for PATCH /api/v1/admin/model-routes/{routeId}/certify (T-009 Phase-A).

Exercises the full HTTP -> endpoint -> ModelRouteRepository -> Postgres path and the ADR-0004 +
retrieval-eval-suite.md certification gates. Skips cleanly when Postgres is not reachable (per
conftest.py::postgres_available) — the gate *logic* is covered DB-free in
tests/unit/test_route_certification.py, which always runs in CI.
"""

from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text

pytestmark = pytest.mark.asyncio

# A dedicated, uniquely-named route so the test never mutates the migration-seeded routes.
_ROUTE_ID = "embedding_certify_test@2026-05-29.1"
_SSR_ID = "ssr_certify_test"
_REVAL_ID = "reval_certify_test"
_SEEDED_EXPERIMENT_ROUTE = "embedding_openai@2026-05-01.1"  # seeded by migration 0001


def _dev_header(
    *, tenant_id: str = "tn_test", role: str = "owner", user_id: str = "usr_test"
) -> dict[str, str]:
    payload = {"tenantId": tenant_id, "role": role, "userId": user_id}
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return {"x-dev-principal": encoded}


async def _delete_test_rows() -> None:
    from app.domain.repositories._base import session_scope

    async with session_scope() as session:
        # Unlink first (FK), then drop the platform rows this test owns.
        await session.execute(
            text("DELETE FROM model_routes WHERE route_id = :r"), {"r": _ROUTE_ID}
        )
        await session.execute(
            text("DELETE FROM retrieval_eval_runs WHERE retrieval_eval_run_id = :r"),
            {"r": _REVAL_ID},
        )
        await session.execute(
            text("DELETE FROM safety_suite_runs WHERE safety_suite_run_id = :r"),
            {"r": _SSR_ID},
        )


@pytest_asyncio.fixture()
async def certifiable_route(seed_tenant: tuple[str, str]) -> AsyncIterator[str]:
    """Insert a fully-gated embedding route (passing safety + retrieval-eval runs linked)."""
    _tenant_id, user_id = seed_tenant
    from app.domain.repositories._base import session_scope

    await _delete_test_rows()
    async with session_scope() as session:
        await session.execute(
            text(
                """
                INSERT INTO safety_suite_runs (
                    safety_suite_run_id, purpose, provider, model, prompt_version,
                    schema_version, case_count, case_run_ids, passed, initiated_by,
                    started_at, finished_at
                ) VALUES (
                    :id, 'embedding', 'openai', 'text-embedding-3-large',
                    'embedding_none@2026-05-01.1', '1.0', 20, :runs, true, :uid, :ts, :ts
                )
                """
            ),
            {
                "id": _SSR_ID,
                "runs": [f"run_{i}" for i in range(20)],
                "uid": user_id,
                "ts": datetime.now(UTC),
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO retrieval_eval_runs (
                    retrieval_eval_run_id, route_id, purpose, config_label,
                    gold_set_tenant_id, gold_set_version, case_count, scores, passed,
                    is_first_run, judge_applied, initiated_by, started_at, finished_at
                ) VALUES (
                    :id, :route, 'embedding', 'dense_only', 'tenant_smoke',
                    '2026-05-29.1', 6, CAST(:scores AS jsonb), true, true, false, :uid, :ts, :ts
                )
                """
            ),
            {
                "id": _REVAL_ID,
                "route": _ROUTE_ID,
                "scores": json.dumps({"recall_at_6": 1.0, "mrr": 1.0}),
                "uid": user_id,
                "ts": datetime.now(UTC),
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO model_routes (
                    route_id, purpose, provider, model, prompt_version, schema_version,
                    certification_status, safety_suite_run_id, retrieval_eval_run_id, created_at
                ) VALUES (
                    :id, 'embedding', 'openai', 'text-embedding-3-large',
                    'embedding_none@2026-05-01.1', '1.0', 'experiment', :ssr, :reval, :ts
                )
                """
            ),
            {"id": _ROUTE_ID, "ssr": _SSR_ID, "reval": _REVAL_ID, "ts": datetime.now(UTC)},
        )
        await session.commit()

    yield _ROUTE_ID
    await _delete_test_rows()


async def test_non_owner_is_forbidden(
    async_client: AsyncClient, seed_tenant: tuple[str, str]
) -> None:
    resp = await async_client.patch(
        f"/api/v1/admin/model-routes/{_SEEDED_EXPERIMENT_ROUTE}/certify",
        headers=_dev_header(role="content_manager"),
        json={"certificationNotes": "nope"},
    )
    assert resp.status_code == 403, resp.text


async def test_unknown_route_is_404(
    async_client: AsyncClient, seed_tenant: tuple[str, str]
) -> None:
    resp = await async_client.patch(
        "/api/v1/admin/model-routes/does_not_exist@2026-01-01.1/certify",
        headers=_dev_header(role="owner"),
        json={"certificationNotes": "x"},
    )
    assert resp.status_code == 404, resp.text


async def test_ungated_route_is_409(
    async_client: AsyncClient, seed_tenant: tuple[str, str]
) -> None:
    # The migration-seeded embedding route has no passing safety/retrieval runs linked.
    resp = await async_client.patch(
        f"/api/v1/admin/model-routes/{_SEEDED_EXPERIMENT_ROUTE}/certify",
        headers=_dev_header(role="owner"),
        json={"certificationNotes": "premature"},
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["code"] == "route_not_certifiable"


async def test_owner_certifies_fully_gated_route(
    async_client: AsyncClient, certifiable_route: str
) -> None:
    resp = await async_client.patch(
        f"/api/v1/admin/model-routes/{certifiable_route}/certify",
        headers=_dev_header(role="owner"),
        json={"certificationNotes": "Both gates green on 2026-05-29.1."},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["certificationStatus"] == "certified"
    assert body["certifiedBy"] == "usr_test"
    assert body["certifiedAt"] is not None

    # An audit entry was recorded.
    from app.domain.repositories._base import session_scope

    async with session_scope() as session:
        result = await session.execute(
            text(
                "SELECT action, resource_id, details FROM audit_entries "
                "WHERE resource_id = :r AND action = 'model_route_certified'"
            ),
            {"r": certifiable_route},
        )
        row = result.mappings().one_or_none()
    assert row is not None
    assert row["details"]["certificationNotes"].startswith("Both gates green")


async def test_already_certified_route_is_409(
    async_client: AsyncClient, certifiable_route: str
) -> None:
    first = await async_client.patch(
        f"/api/v1/admin/model-routes/{certifiable_route}/certify",
        headers=_dev_header(role="owner"),
        json={"certificationNotes": "first"},
    )
    assert first.status_code == 200, first.text
    second = await async_client.patch(
        f"/api/v1/admin/model-routes/{certifiable_route}/certify",
        headers=_dev_header(role="owner"),
        json={"certificationNotes": "again"},
    )
    assert second.status_code == 409, second.text
