"""Integration tests for the owner-gated route<->run linking (T-009 Phase-A, operationalization).

Closes the half-wired gate: certification needs BOTH `model_routes.safety_suite_run_id` and
`retrieval_eval_run_id` set, but nothing set them. These exercise the new
`ModelRouteRepository.attach_safety_suite_run` / `attach_retrieval_eval_run` against real Postgres
and prove the end-to-end loop: insert passing runs -> attach both -> `PATCH …/certify` 200 + audit
row; omit either attach -> 409. The retrieval-eval run is inserted via `RetrievalEvalRunRepository`
(Step 1), so this also covers persist -> attach -> certify together.

Skips cleanly without Postgres (per conftest's seed_tenant -> clean_tables -> db_engine chain); the
gate *decision* is covered DB-free in tests/unit/test_route_certification.py.
"""

from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from app.domain.models.retrieval_eval_run import RetrievalEvalRun
from app.domain.repositories._base import session_scope
from app.domain.repositories.model_route_repository import ModelRouteRepository
from app.domain.repositories.retrieval_eval_run_repository import (
    RetrievalEvalRunRepository,
)
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import text

pytestmark = pytest.mark.asyncio

_ROUTE_ID = "embedding_attach_test@2026-05-29.1"
_SSR_ID = "ssr_attach_test"
_REVAL_ID = "reval_attach_test"


def _dev_header(
    *, role: str = "owner", tenant_id: str = "tn_test", user_id: str = "usr_test"
) -> dict[str, str]:
    payload = {"tenantId": tenant_id, "role": role, "userId": user_id}
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return {"x-dev-principal": encoded}


def _passing_reval(initiated_by: str) -> RetrievalEvalRun:
    now = datetime.now(UTC)
    return RetrievalEvalRun(
        retrieval_eval_run_id=_REVAL_ID,
        route_id=_ROUTE_ID,
        purpose="embedding",
        config_label="dense_only",
        gold_set_tenant_id="tenant_smoke",
        gold_set_version="2026-05-29.1",
        case_count=6,
        scores={"recall_at_6": 1.0, "mrr": 1.0},
        passed=True,
        is_first_run=True,
        judge_applied=False,
        regressions=None,
        initiated_by=initiated_by,
        started_at=now,
        finished_at=now,
    )


async def _delete_rows() -> None:
    async with session_scope() as session:
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
async def unlinked_route(seed_tenant: tuple[str, str]) -> AsyncIterator[tuple[str, str]]:
    """An experiment route with both passing runs present but NEITHER gate pointer set yet."""
    _tenant_id, user_id = seed_tenant
    await _delete_rows()
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
        # Persist the passing retrieval-eval run via the Step 1 repository (exercises insert).
        await RetrievalEvalRunRepository(session).insert(_passing_reval(user_id))
        await session.execute(
            text(
                """
                INSERT INTO model_routes (
                    route_id, purpose, provider, model, prompt_version, schema_version,
                    certification_status, created_at
                ) VALUES (
                    :id, 'embedding', 'openai', 'text-embedding-3-large',
                    'embedding_none@2026-05-01.1', '1.0', 'experiment', :ts
                )
                """
            ),
            {"id": _ROUTE_ID, "ts": datetime.now(UTC)},
        )
    yield _ROUTE_ID, user_id
    await _delete_rows()


async def test_attach_both_then_certify_200(unlinked_route: tuple[str, str]) -> None:
    route_id, _user_id = unlinked_route
    async with session_scope() as session:
        repo = ModelRouteRepository(session)
        await repo.attach_safety_suite_run(route_id=route_id, run_id=_SSR_ID)
        linked = await repo.attach_retrieval_eval_run(
            route_id=route_id, run_id=_REVAL_ID
        )
    assert linked.safety_suite_run_id == _SSR_ID
    assert linked.retrieval_eval_run_id == _REVAL_ID

    with TestClient(app) as client:
        resp = client.patch(
            f"/api/v1/admin/model-routes/{route_id}/certify",
            headers=_dev_header(role="owner"),
            json={"certificationNotes": "Both gates linked via attach_*."},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["certificationStatus"] == "certified"

    async with session_scope() as session:
        result = await session.execute(
            text(
                "SELECT details FROM audit_entries "
                "WHERE resource_id = :r AND action = 'model_route_certified'"
            ),
            {"r": route_id},
        )
        row = result.mappings().one_or_none()
    assert row is not None
    assert row["details"]["retrievalEvalRunId"] == _REVAL_ID
    assert row["details"]["safetySuiteRunId"] == _SSR_ID


async def test_omitting_retrieval_eval_attach_is_409(
    unlinked_route: tuple[str, str],
) -> None:
    route_id, _user_id = unlinked_route
    async with session_scope() as session:
        await ModelRouteRepository(session).attach_safety_suite_run(
            route_id=route_id, run_id=_SSR_ID
        )
    with TestClient(app) as client:
        resp = client.patch(
            f"/api/v1/admin/model-routes/{route_id}/certify",
            headers=_dev_header(role="owner"),
            json={"certificationNotes": "Safety only — retrieval-eval gate unlinked."},
        )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["code"] == "route_not_certifiable"


async def test_omitting_safety_attach_is_409(
    unlinked_route: tuple[str, str],
) -> None:
    route_id, _user_id = unlinked_route
    async with session_scope() as session:
        await ModelRouteRepository(session).attach_retrieval_eval_run(
            route_id=route_id, run_id=_REVAL_ID
        )
    with TestClient(app) as client:
        resp = client.patch(
            f"/api/v1/admin/model-routes/{route_id}/certify",
            headers=_dev_header(role="owner"),
            json={"certificationNotes": "Retrieval-eval only — safety gate unlinked."},
        )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["code"] == "route_not_certifiable"
