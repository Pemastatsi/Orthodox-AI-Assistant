"""Integration tests for `RetrievalEvalRunRepository` (T-009 Phase-A, operationalization).

Exercises the insert -> read-back path against real Postgres and the JSONB round-trips for
`scores` and `regressions`. Skips cleanly when Postgres is unreachable (per conftest's
`seed_tenant` -> `clean_tables` -> `db_engine` chain). The run model / metric logic is covered
DB-free elsewhere (`tests/retrieval_eval/`); this asserts the platform row persists and reads back
as the same camelCase wire shape.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.domain.models.retrieval_eval_run import (
    RetrievalEvalRegression,
    RetrievalEvalRun,
)
from app.domain.repositories._base import session_scope
from app.domain.repositories.retrieval_eval_run_repository import (
    RetrievalEvalRunRepository,
)
from sqlalchemy import text

pytestmark = pytest.mark.asyncio

_ROUTE_ID = "embedding_openai_large@2026-05-29.1"
_GOLD_VERSION = "2026-05-29.1"


def _make_run(
    *,
    run_id: str,
    initiated_by: str,
    passed: bool,
    regressions: list[RetrievalEvalRegression] | None = None,
) -> RetrievalEvalRun:
    now = datetime.now(UTC)
    return RetrievalEvalRun(
        retrieval_eval_run_id=run_id,
        route_id=_ROUTE_ID,
        purpose="embedding",
        config_label="dense_only",
        gold_set_tenant_id="tenant_smoke",
        gold_set_version=_GOLD_VERSION,
        case_count=6,
        scores={"recall_at_6": 1.0, "mrr": 1.0, "precision_at_6": 1 / 6},
        passed=passed,
        is_first_run=not regressions,
        judge_applied=False,
        regressions=regressions,
        initiated_by=initiated_by,
        started_at=now,
        finished_at=now,
    )


async def _cleanup(*run_ids: str) -> None:
    async with session_scope() as session:
        for run_id in run_ids:
            await session.execute(
                text(
                    "DELETE FROM retrieval_eval_runs WHERE retrieval_eval_run_id = :id"
                ),
                {"id": run_id},
            )


async def test_insert_then_get_round_trips_wire_shape(
    seed_tenant: tuple[str, str],
) -> None:
    _tenant_id, user_id = seed_tenant
    run = _make_run(run_id="reval_itest_passing", initiated_by=user_id, passed=True)
    try:
        async with session_scope() as session:
            inserted_id = await RetrievalEvalRunRepository(session).insert(run)
        assert inserted_id == run.retrieval_eval_run_id

        async with session_scope() as session:
            got = await RetrievalEvalRunRepository(session).get(
                run.retrieval_eval_run_id
            )
        assert got is not None
        # created_at is DB-defaulted on insert; everything else must match the camelCase wire shape.
        expected = run.model_dump(by_alias=True, exclude={"created_at"})
        actual = got.model_dump(by_alias=True, exclude={"created_at"})
        assert actual == expected
        assert got.created_at is not None  # DB stamped it
        assert got.scores["recall_at_6"] == 1.0
    finally:
        await _cleanup(run.retrieval_eval_run_id)


async def test_regressions_jsonb_round_trips(seed_tenant: tuple[str, str]) -> None:
    _tenant_id, user_id = seed_tenant
    run = _make_run(
        run_id="reval_itest_regressed",
        initiated_by=user_id,
        passed=False,
        regressions=[
            RetrievalEvalRegression(
                metric="precision_at_6", baseline=0.9, observed=1 / 6
            )
        ],
    )
    try:
        async with session_scope() as session:
            await RetrievalEvalRunRepository(session).insert(run)
        async with session_scope() as session:
            got = await RetrievalEvalRunRepository(session).get(
                run.retrieval_eval_run_id
            )
        assert got is not None
        assert got.passed is False
        assert got.regressions is not None
        assert len(got.regressions) == 1
        assert got.regressions[0].metric == "precision_at_6"
        assert got.regressions[0].baseline == 0.9
    finally:
        await _cleanup(run.retrieval_eval_run_id)


async def test_get_latest_passing_picks_newest(seed_tenant: tuple[str, str]) -> None:
    _tenant_id, user_id = seed_tenant
    failing = _make_run(
        run_id="reval_itest_latest_fail",
        initiated_by=user_id,
        passed=False,
        regressions=[
            RetrievalEvalRegression(metric="recall_at_6", baseline=1.0, observed=0.0)
        ],
    )
    passing = _make_run(
        run_id="reval_itest_latest_pass", initiated_by=user_id, passed=True
    )
    try:
        async with session_scope() as session:
            repo = RetrievalEvalRunRepository(session)
            await repo.insert(failing)
            await repo.insert(passing)
        async with session_scope() as session:
            latest = await RetrievalEvalRunRepository(session).get_latest_passing(
                route_id=_ROUTE_ID, gold_set_version=_GOLD_VERSION
            )
        assert latest is not None
        assert latest.retrieval_eval_run_id == passing.retrieval_eval_run_id
        assert latest.passed is True
    finally:
        await _cleanup(
            failing.retrieval_eval_run_id, passing.retrieval_eval_run_id
        )


async def test_get_unknown_returns_none(seed_tenant: tuple[str, str]) -> None:
    async with session_scope() as session:
        got = await RetrievalEvalRunRepository(session).get("reval_does_not_exist")
    assert got is None
