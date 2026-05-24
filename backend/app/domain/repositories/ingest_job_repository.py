"""IngestJob repository — owns `ingest_jobs` table writes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import ulid
from sqlalchemy import text

from app.domain.models.ingest_job import IngestJob, IngestJobProgress
from app.domain.repositories._base import AsyncSession, assert_tenant


class IngestJobNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class CreateIngestJobParams:
    tenant_id: str
    user_id: str
    source_id: str


def _row_to_job(row: Any) -> IngestJob:
    progress_raw = row.get("progress") or {}
    progress: IngestJobProgress | None = None
    if isinstance(progress_raw, dict) and progress_raw.get("stage"):
        progress = IngestJobProgress(
            stage=str(progress_raw["stage"]),
            completed=int(progress_raw.get("completed", 0)),
            total=int(progress_raw.get("total", 0)),
        )
    return IngestJob(
        job_id=row["job_id"],
        tenant_id=row["tenant_id"],
        user_id=row["user_id"],
        source_id=row["source_id"],
        status=row["status"],
        progress=progress,
        error_code=row.get("error_code"),
        error_message=row.get("error_message"),
        started_at=row.get("started_at"),
        finished_at=row.get("finished_at"),
        created_at=row["created_at"],
    )


class IngestJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, params: CreateIngestJobParams) -> IngestJob:
        assert_tenant(params.tenant_id)
        job_id = f"ijb_{ulid.new()!s}"
        result = await self._session.execute(
            text(
                """
                INSERT INTO ingest_jobs (
                    job_id, tenant_id, user_id, source_id, status, progress, created_at
                ) VALUES (
                    :job_id, :tenant_id, :user_id, :source_id, 'queued',
                    CAST(:progress AS jsonb), now()
                )
                RETURNING *
                """
            ),
            {
                "job_id": job_id,
                "tenant_id": params.tenant_id,
                "user_id": params.user_id,
                "source_id": params.source_id,
                "progress": json.dumps({}),
            },
        )
        row = result.mappings().one()
        return _row_to_job(row)

    async def get(self, *, tenant_id: str, job_id: str) -> IngestJob | None:
        assert_tenant(tenant_id)
        result = await self._session.execute(
            text(
                "SELECT * FROM ingest_jobs "
                "WHERE tenant_id = :tenant_id AND job_id = :job_id"
            ),
            {"tenant_id": tenant_id, "job_id": job_id},
        )
        row = result.mappings().one_or_none()
        return _row_to_job(row) if row else None

    async def transition(
        self,
        *,
        tenant_id: str,
        job_id: str,
        status: str,
        progress: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> IngestJob:
        assert_tenant(tenant_id)
        now = datetime.now(UTC)
        started_at_clause = ""
        finished_at_clause = ""
        params: dict[str, Any] = {
            "tenant_id": tenant_id,
            "job_id": job_id,
            "status": status,
            "progress": json.dumps(progress or {}),
            "error_code": error_code,
            "error_message": error_message,
            "now": now,
        }
        if status == "extracting":
            started_at_clause = ", started_at = COALESCE(started_at, :now)"
        if status in {"completed", "failed", "cancelled", "awaiting_review"}:
            finished_at_clause = ", finished_at = :now"

        sql = f"""
            UPDATE ingest_jobs SET
                status = :status,
                progress = CAST(:progress AS jsonb),
                error_code = :error_code,
                error_message = :error_message
                {started_at_clause}
                {finished_at_clause}
            WHERE tenant_id = :tenant_id AND job_id = :job_id
            RETURNING *
        """
        result = await self._session.execute(text(sql), params)
        row = result.mappings().one_or_none()
        if not row:
            raise IngestJobNotFoundError(job_id)
        return _row_to_job(row)


__all__ = [
    "CreateIngestJobParams",
    "IngestJobNotFoundError",
    "IngestJobRepository",
]
