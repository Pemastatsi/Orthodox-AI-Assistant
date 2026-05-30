"""RetrievalEvalRun repository — `retrieval_eval_runs` (a platform table; no tenant scoping / RLS).

Persists and reads the second-gate run rows that `model_routes.retrieval_eval_run_id` points at
(migration `0003_retrieval_eval_runs`). Mirrors `model_route_repository.py`: raw SQL via `text()`,
`result.mappings()`, and JSONB columns for `scores` / `regressions`. The harness/runner build the
`RetrievalEvalRun` (offline, DB-free); this repository is the only place that writes the row.

The run's id is the runner-supplied ULID-based `reval_…` id (see `tests/retrieval_eval/runner.py`);
`insert` persists it verbatim and returns it, mirroring `ModelRouteRepository` (which likewise does
not fabricate ids for the platform `model_routes` table).
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.domain.models.retrieval_eval_run import (
    RetrievalEvalRegression,
    RetrievalEvalRun,
)
from app.domain.repositories._base import AsyncSession


def _row_to_run(row: Any) -> RetrievalEvalRun:
    """Map a `retrieval_eval_runs` row to the wire model.

    `scores` (JSONB) is decoded by SQLAlchemy's asyncpg dialect to a `dict[str, float]`;
    `regressions` (JSONB, nullable) to a list of `RetrievalEvalRegression` (or `None`).
    """
    raw_regressions = row.get("regressions")
    regressions = (
        [RetrievalEvalRegression.model_validate(r) for r in raw_regressions]
        if raw_regressions
        else None
    )
    return RetrievalEvalRun(
        retrieval_eval_run_id=row["retrieval_eval_run_id"],
        route_id=row["route_id"],
        purpose=row["purpose"],
        config_label=row.get("config_label"),
        gold_set_tenant_id=row["gold_set_tenant_id"],
        gold_set_version=row["gold_set_version"],
        case_count=row["case_count"],
        scores=row["scores"],
        passed=row["passed"],
        is_first_run=row["is_first_run"],
        judge_applied=row["judge_applied"],
        regressions=regressions,
        initiated_by=row["initiated_by"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        created_at=row.get("created_at"),
    )


class RetrievalEvalRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(self, run: RetrievalEvalRun) -> str:
        """Write one `retrieval_eval_runs` row; returns its id. `created_at` is DB-defaulted."""
        regressions_json = (
            json.dumps([r.model_dump(by_alias=True) for r in run.regressions])
            if run.regressions is not None
            else None
        )
        await self._session.execute(
            text(
                """
                INSERT INTO retrieval_eval_runs (
                    retrieval_eval_run_id, route_id, purpose, config_label,
                    gold_set_tenant_id, gold_set_version, case_count, scores, passed,
                    is_first_run, judge_applied, regressions, initiated_by,
                    started_at, finished_at
                ) VALUES (
                    :id, :route_id, :purpose, :config_label,
                    :gold_set_tenant_id, :gold_set_version, :case_count,
                    CAST(:scores AS jsonb), :passed, :is_first_run, :judge_applied,
                    CAST(:regressions AS jsonb), :initiated_by, :started_at, :finished_at
                )
                """
            ),
            {
                "id": run.retrieval_eval_run_id,
                "route_id": run.route_id,
                "purpose": run.purpose,
                "config_label": run.config_label,
                "gold_set_tenant_id": run.gold_set_tenant_id,
                "gold_set_version": run.gold_set_version,
                "case_count": run.case_count,
                "scores": json.dumps(run.scores),
                "passed": run.passed,
                "is_first_run": run.is_first_run,
                "judge_applied": run.judge_applied,
                "regressions": regressions_json,
                "initiated_by": run.initiated_by,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
            },
        )
        return run.retrieval_eval_run_id

    async def get(self, retrieval_eval_run_id: str) -> RetrievalEvalRun | None:
        result = await self._session.execute(
            text(
                "SELECT * FROM retrieval_eval_runs WHERE retrieval_eval_run_id = :id"
            ),
            {"id": retrieval_eval_run_id},
        )
        row = result.mappings().one_or_none()
        return _row_to_run(row) if row else None

    async def get_latest_passing(
        self, *, route_id: str, gold_set_version: str
    ) -> RetrievalEvalRun | None:
        """The newest passing run for a route on a pinned gold-set version (the cert-flow lookup).

        Versions are not commensurable (retrieval-eval-suite.md §Forbidden Patterns), so the
        gold-set version is part of the key — never compared across versions.
        """
        result = await self._session.execute(
            text(
                """
                SELECT * FROM retrieval_eval_runs
                WHERE route_id = :route_id
                  AND gold_set_version = :version
                  AND passed = true
                ORDER BY finished_at DESC
                LIMIT 1
                """
            ),
            {"route_id": route_id, "version": gold_set_version},
        )
        row = result.mappings().one_or_none()
        return _row_to_run(row) if row else None


__all__ = ["RetrievalEvalRunRepository"]
