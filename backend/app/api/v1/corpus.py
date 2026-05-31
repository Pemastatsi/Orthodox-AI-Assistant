"""GET /api/v1/corpus and PATCH /api/v1/corpus/{chunkId}."""

from __future__ import annotations

import json
from typing import Literal

import ulid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text

from app.api.v1._deps import get_tenant_session, require_scope
from app.domain.models._base import WireModel
from app.domain.models.chunk import Chunk
from app.domain.models.principal import Principal
from app.domain.repositories._base import AsyncSession
from app.domain.repositories.chunk_repository import (
    ChunkNotFoundError,
    ChunkRepository,
)

router = APIRouter(prefix="/corpus", tags=["corpus"])


Visibility = Literal["member", "scholar", "admin_only", "suppressed"]


class CorpusListResponse(WireModel):
    items: list[Chunk]
    next_cursor: str | None


class CorpusReviewRequest(WireModel):
    approved: bool | None = None
    visibility: Visibility | None = None
    review_note: str | None = None


@router.get(
    "",
    response_model=CorpusListResponse,
    response_model_by_alias=True,
)
async def list_corpus(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    approved: bool | None = Query(default=None),
    visibility: Visibility | None = Query(default=None),
    source_id: str | None = Query(default=None, alias="sourceId"),
    principal: Principal = Depends(require_scope("corpus:read")),
    session: AsyncSession = Depends(get_tenant_session),
) -> CorpusListResponse:
    items, next_cursor = await ChunkRepository(session).list_by_tenant(
        tenant_id=principal.tenant_id,
        approved=approved,
        visibility=visibility,
        source_id=source_id,
        cursor=cursor,
        limit=limit,
    )
    return CorpusListResponse(items=items, next_cursor=next_cursor)


@router.patch(
    "/{chunk_id}",
    response_model=Chunk,
    response_model_by_alias=True,
)
async def review_chunk(
    chunk_id: str,
    body: CorpusReviewRequest,
    principal: Principal = Depends(require_scope("corpus:approve")),
    session: AsyncSession = Depends(get_tenant_session),
) -> Chunk:
    if body.approved is None and body.visibility is None and body.review_note is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "validation_failed", "message": "no field to update"},
        )
    repo = ChunkRepository(session)
    try:
        chunk: Chunk | None = None
        if body.visibility is not None:
            chunk = await repo.set_visibility(
                tenant_id=principal.tenant_id,
                chunk_id=chunk_id,
                visibility=body.visibility,
                review_note=body.review_note,
            )
        if body.approved is True:
            chunk = await repo.mark_approved(
                tenant_id=principal.tenant_id,
                chunk_id=chunk_id,
                approved_by_user_id=principal.user_id,
                approval_note=body.review_note,
            )
        if body.approved is False:
            # Phase 1 "un-approval" → cascade to false per the cascade-or-reject decision
            # (we cascade; symmetric with the approve direction).
            await session.execute(
                text(
                    "UPDATE chunks SET approved = false WHERE tenant_id = :tenant_id "
                    "AND chunk_id = :chunk_id"
                ),
                {"tenant_id": principal.tenant_id, "chunk_id": chunk_id},
            )
            chunk = await repo.get(tenant_id=principal.tenant_id, chunk_id=chunk_id)
    except ChunkNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": f"chunk {chunk_id} not found"},
        ) from exc

    if chunk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": f"chunk {chunk_id} not found"},
        )

    # Audit entry — append-only per db-schema.md cross-table invariant #5.
    await session.execute(
        text(
            """
            INSERT INTO audit_entries (
                audit_id, tenant_id, actor_user_id, actor_role, action,
                resource_type, resource_id, details, occurred_at
            ) VALUES (
                :audit_id, :tenant_id, :actor_user_id, :actor_role, 'chunk_reviewed',
                'chunk', :resource_id, CAST(:details AS jsonb), now()
            )
            """
        ),
        {
            "audit_id": f"aud_{ulid.new()!s}",
            "tenant_id": principal.tenant_id,
            "actor_user_id": principal.user_id,
            "actor_role": principal.role,
            "resource_id": chunk_id,
            "details": json.dumps(
                {
                    "approved": body.approved,
                    "visibility": body.visibility,
                    "reviewNote": body.review_note,
                }
            ),
        },
    )

    return chunk


__all__ = ["router"]
