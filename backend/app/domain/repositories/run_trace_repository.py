"""RunTrace repository — `run_traces` table (db-schema.md)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.domain.models.run_trace import RunTrace, RunTraceUsage, Stage
from app.domain.repositories._base import AsyncSession, assert_tenant


def _row_to_run_trace(row: Any) -> RunTrace:
    usage = row["usage"] or {}
    stages_raw = row["stages"] or []
    stages = [Stage.model_validate(s) for s in stages_raw]
    return RunTrace(
        run_id=row["run_id"],
        tenant_id=row["tenant_id"],
        user_id=row["user_id"],
        session_id=row.get("session_id"),
        started_at=row["started_at"],
        finished_at=row.get("finished_at"),
        cache_hit=row["cache_hit"],
        stages=stages,
        usage=RunTraceUsage(
            served_answer_count=int(usage.get("servedAnswerCount", 0)),
            fresh_model_run_count=int(usage.get("freshModelRunCount", 0)),
        ),
        final_handling=row.get("final_handling"),
        final_confidence_tier=row.get("final_confidence_tier"),
        verifier_passed=row.get("verifier_passed"),
        evidence_packet_ref=row.get("evidence_packet_ref"),
    )


class RunTraceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(self, trace: RunTrace) -> None:
        assert_tenant(trace.tenant_id)
        stages_payload = [s.model_dump(by_alias=True, mode="json") for s in trace.stages]
        usage_payload = trace.usage.model_dump(by_alias=True, mode="json")
        await self._session.execute(
            text(
                """
                INSERT INTO run_traces (
                    run_id, tenant_id, user_id, session_id, started_at, finished_at,
                    cache_hit, stages, usage, final_handling, final_confidence_tier,
                    verifier_passed, evidence_packet_ref, created_at
                ) VALUES (
                    :run_id, :tenant_id, :user_id, :session_id, :started_at, :finished_at,
                    :cache_hit, CAST(:stages AS jsonb), CAST(:usage AS jsonb),
                    :final_handling, :final_confidence_tier, :verifier_passed,
                    :evidence_packet_ref, now()
                )
                """
            ),
            {
                "run_id": trace.run_id,
                "tenant_id": trace.tenant_id,
                "user_id": trace.user_id,
                "session_id": trace.session_id,
                "started_at": trace.started_at,
                "finished_at": trace.finished_at,
                "cache_hit": trace.cache_hit,
                "stages": _json(stages_payload),
                "usage": _json(usage_payload),
                "final_handling": trace.final_handling,
                "final_confidence_tier": trace.final_confidence_tier,
                "verifier_passed": trace.verifier_passed,
                "evidence_packet_ref": trace.evidence_packet_ref,
            },
        )

    async def get(self, *, tenant_id: str, run_id: str) -> RunTrace | None:
        assert_tenant(tenant_id)
        result = await self._session.execute(
            text(
                "SELECT * FROM run_traces "
                "WHERE tenant_id = :tenant_id AND run_id = :run_id"
            ),
            {"tenant_id": tenant_id, "run_id": run_id},
        )
        row = result.mappings().one_or_none()
        return _row_to_run_trace(row) if row else None

    async def list_by_tenant(
        self,
        *,
        tenant_id: str,
        cursor: str | None = None,
        limit: int = 25,
        handling: str | None = None,
        confidence_tier: str | None = None,
        since: Any | None = None,
    ) -> tuple[list[RunTrace], str | None]:
        """Keyset pagination by `run_id DESC` (ULIDs are time-sortable, so
        newest-first). Returns up to `limit` rows + a nextCursor string when
        more rows are available, otherwise None."""
        assert_tenant(tenant_id)
        clauses = ["tenant_id = :tenant_id"]
        params: dict[str, Any] = {"tenant_id": tenant_id, "limit": limit + 1}
        if cursor:
            clauses.append("run_id < :cursor")
            params["cursor"] = cursor
        if handling is not None:
            clauses.append("final_handling = :handling")
            params["handling"] = handling
        if confidence_tier is not None:
            clauses.append("final_confidence_tier = :confidence_tier")
            params["confidence_tier"] = confidence_tier
        if since is not None:
            clauses.append("started_at >= :since")
            params["since"] = since
        sql = (
            "SELECT * FROM run_traces WHERE "
            + " AND ".join(clauses)
            + " ORDER BY run_id DESC LIMIT :limit"
        )
        result = await self._session.execute(text(sql), params)
        rows = list(result.mappings().all())
        items = [_row_to_run_trace(r) for r in rows[:limit]]
        next_cursor = rows[limit - 1]["run_id"] if len(rows) > limit else None
        return items, next_cursor


def _json(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, default=str)


__all__ = ["RunTraceRepository"]
