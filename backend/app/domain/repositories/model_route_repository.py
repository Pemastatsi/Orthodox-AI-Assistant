"""ModelRoute repository — `model_routes` (a platform table; no tenant scoping / RLS).

DB I/O for route certification: load a route, check whether its linked safety-suite and
retrieval-eval runs passed, and stamp it certified. The gate *decision* is the pure function in
`app/domain/services/route_certification.py`; this repo only reads/writes rows.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from app.domain.models.model_route import ModelRoute
from app.domain.repositories._base import AsyncSession


def _row_to_model_route(row: Any) -> ModelRoute:
    return ModelRoute(
        route_id=row["route_id"],
        purpose=row["purpose"],
        provider=row["provider"],
        model=row["model"],
        prompt_version=row["prompt_version"],
        schema_version=row["schema_version"],
        certification_status=row["certification_status"],
        created_at=row["created_at"],
        supports_prompt_cache=row["supports_prompt_cache"],
        supports_batch=row["supports_batch"],
        supports_json_mode=row["supports_json_mode"],
        safety_suite_run_id=row.get("safety_suite_run_id"),
        retrieval_eval_run_id=row.get("retrieval_eval_run_id"),
        certified_by=row.get("certified_by"),
        certified_at=row.get("certified_at"),
        deprecated_at=row.get("deprecated_at"),
    )


class ModelRouteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, route_id: str) -> ModelRoute | None:
        result = await self._session.execute(
            text("SELECT * FROM model_routes WHERE route_id = :rid"),
            {"rid": route_id},
        )
        row = result.mappings().one_or_none()
        return _row_to_model_route(row) if row else None

    async def safety_run_passed(self, run_id: str) -> bool:
        result = await self._session.execute(
            text("SELECT passed FROM safety_suite_runs WHERE safety_suite_run_id = :id"),
            {"id": run_id},
        )
        row = result.mappings().one_or_none()
        return bool(row["passed"]) if row else False

    async def retrieval_eval_run_passed(self, run_id: str) -> bool:
        result = await self._session.execute(
            text(
                "SELECT passed FROM retrieval_eval_runs WHERE retrieval_eval_run_id = :id"
            ),
            {"id": run_id},
        )
        row = result.mappings().one_or_none()
        return bool(row["passed"]) if row else False

    async def mark_certified(self, *, route_id: str, certified_by: str) -> ModelRoute:
        result = await self._session.execute(
            text(
                """
                UPDATE model_routes
                SET certification_status = 'certified',
                    certified_by = :cb,
                    certified_at = :ts
                WHERE route_id = :rid
                RETURNING *
                """
            ),
            {"cb": certified_by, "ts": datetime.now(UTC), "rid": route_id},
        )
        row = result.mappings().one()
        return _row_to_model_route(row)


    async def attach_safety_suite_run(
        self, *, route_id: str, run_id: str
    ) -> ModelRoute:
        """Link a (passing) safety-suite run to a route — the ADR-0004 gate pointer.

        Owner-gated at the call site (the CLI / a future endpoint). Populating
        `safety_suite_runs` *rows* remains T-006's harness domain; this only wires the pointer so
        the certification gate isn't left half-satisfiable.
        """
        result = await self._session.execute(
            text(
                """
                UPDATE model_routes
                SET safety_suite_run_id = :run_id
                WHERE route_id = :rid
                RETURNING *
                """
            ),
            {"run_id": run_id, "rid": route_id},
        )
        row = result.mappings().one()
        return _row_to_model_route(row)

    async def attach_retrieval_eval_run(
        self, *, route_id: str, run_id: str
    ) -> ModelRoute:
        """Link a (passing) retrieval-eval run to a route — the second cert gate pointer
        (`docs/contracts/retrieval-eval-suite.md`). Owner-gated at the call site."""
        result = await self._session.execute(
            text(
                """
                UPDATE model_routes
                SET retrieval_eval_run_id = :run_id
                WHERE route_id = :rid
                RETURNING *
                """
            ),
            {"run_id": run_id, "rid": route_id},
        )
        row = result.mappings().one()
        return _row_to_model_route(row)


__all__ = ["ModelRouteRepository"]
