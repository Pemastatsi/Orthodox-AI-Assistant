"""POST /api/v1/ingest and GET /api/v1/ingest/jobs/{jobId}."""

from __future__ import annotations

from typing import Literal

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from redis.asyncio import Redis

from app.api.v1._deps import (
    get_redis,
    get_session,
    get_settings_dep,
    require_scope,
)
from app.core.config import Settings
from app.domain.models._base import WireModel
from app.domain.models.ingest_job import IngestJob
from app.domain.models.principal import Principal
from app.domain.repositories._base import AsyncSession
from app.domain.repositories.ingest_job_repository import (
    CreateIngestJobParams,
    IngestJobRepository,
)
from app.domain.repositories.source_repository import (
    CreateSourceParams,
    SourceDuplicateError,
    SourceRepository,
    compute_source_hash,
)
from app.workers.ingestion_worker import stash_upload

router = APIRouter(prefix="/ingest", tags=["ingest"])


SourceType = Literal["pdf", "txt", "md", "docx"]


class IngestUploadResponse(WireModel):
    job_id: str
    source_id: str
    status: str


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IngestUploadResponse,
    response_model_by_alias=True,
)
async def upload_source(
    file: UploadFile = File(...),
    source_type: SourceType = Form("pdf", alias="sourceType"),
    title: str = Form(...),
    father: str | None = Form(default=None),
    work: str | None = Form(default=None),
    language: Literal["en", "el", "mixed"] = Form(default="en"),
    principal: Principal = Depends(require_scope("corpus:write")),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> IngestUploadResponse:
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ingest_invalid", "message": "empty upload"},
        )

    source_hash = compute_source_hash(file_bytes)

    source_repo = SourceRepository(session)
    try:
        source = await source_repo.create(
            CreateSourceParams(
                tenant_id=principal.tenant_id,
                title=title,
                source_type=source_type,
                extraction_method="pending",  # worker updates with parser_used + version
                corpus_version=settings.active_schema_version,
                source_hash=source_hash,
                father=father,
                work=work,
                language=language,
            )
        )
    except SourceDuplicateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "ingest_invalid",
                "message": "source already ingested for this tenant",
            },
        ) from exc

    job_repo = IngestJobRepository(session)
    job = await job_repo.create(
        CreateIngestJobParams(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            source_id=source.source_id,
        )
    )

    await stash_upload(
        redis=redis,
        job_id=job.job_id,
        file_bytes=file_bytes,
        mime_type=file.content_type or "application/octet-stream",
        source_id=source.source_id,
        tenant_id=principal.tenant_id,
    )

    await _enqueue_job(settings=settings, job_id=job.job_id)

    return IngestUploadResponse(
        job_id=job.job_id, source_id=source.source_id, status=job.status
    )


@router.get(
    "/jobs/{job_id}",
    response_model=IngestJob,
    response_model_by_alias=True,
)
async def get_ingest_job(
    job_id: str,
    principal: Principal = Depends(require_scope("corpus:read")),
    session: AsyncSession = Depends(get_session),
) -> IngestJob:
    job = await IngestJobRepository(session).get(
        tenant_id=principal.tenant_id, job_id=job_id
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": f"ingest job {job_id} not found"},
        )
    return job


async def _enqueue_job(*, settings: Settings, job_id: str) -> None:
    """Best-effort enqueue. If arq is unreachable, the job stays in `queued` and a separate
    runbook can call `run_ingest_job_inline`. Tests use the inline path directly.
    """
    try:
        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    except Exception:
        return
    try:
        await pool.enqueue_job("process_ingest_job", job_id)
    finally:
        await pool.close()


__all__ = ["router"]
