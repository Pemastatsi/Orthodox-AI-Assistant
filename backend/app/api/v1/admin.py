"""Admin read endpoints per `docs/api/openapi.yaml` §/admin and
`docs/contracts/auth-context.md` §Role / scope table.

Three GET endpoints expose tenant-scoped, role-gated views of operational data:

- `GET /admin/queries`  — paginated run_traces. content_manager+. The redacted
  query text already lives in `flagged_queries.query_text_redacted`; the
  `run_traces` row itself is metadata-only, so no extra redaction is required
  here (the raw query never enters `run_traces`).
- `GET /admin/flagged`  — paginated flagged_queries with the redacted text.
  content_manager+. `raw_sensitive_log_id` is stripped for non-admin readers
  (the FK must not leak to roles without `admin:raw_sensitive:read`).
- `GET /admin/audit`    — paginated audit_entries. admin+ only.

All endpoints use cursor-based keyset pagination on the primary key (ULIDs are
time-sortable, so `DESC` yields newest-first). Tenant isolation: every query
filters by `principal.tenant_id`; the repository methods call `assert_tenant`
and Postgres RLS enforces the boundary independently.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import Field

from app.api.v1._deps import (
    get_sensitive_log_cipher,
    get_tenant_session,
    require_scope,
)
from app.domain.models._base import WireModel
from app.domain.models.audit_entry import AuditEntry
from app.domain.models.flagged_query import FlaggedQuery
from app.domain.models.model_route import ModelRoute
from app.domain.models.principal import Principal
from app.domain.models.run_trace import RunTrace
from app.domain.repositories._base import AsyncSession
from app.domain.repositories.audit_repository import AuditRepository
from app.domain.repositories.flagged_query_repository import FlaggedQueryRepository
from app.domain.repositories.model_route_repository import ModelRouteRepository
from app.domain.repositories.raw_sensitive_log_repository import (
    RawSensitiveLogRepository,
)
from app.domain.repositories.run_trace_repository import RunTraceRepository
from app.domain.services.encryption_service import (
    CipherDecryptError,
    EncryptedBlob,
    SensitiveLogCipher,
)
from app.domain.services.route_certification import (
    evaluate_certification,
    requires_retrieval_eval_gate,
)

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminQueryListResponse(WireModel):
    items: list[RunTrace]
    next_cursor: str | None


class AdminFlaggedListResponse(WireModel):
    items: list[FlaggedQuery]
    next_cursor: str | None


class AdminAuditListResponse(WireModel):
    items: list[AuditEntry]
    next_cursor: str | None


class AdminRawSensitiveResponse(WireModel):
    run_id: str
    tenant_id: str
    raw_query_text: str
    raw_sensitive_payload: dict[str, Any] = Field(default_factory=dict)
    audit_entry_id: str


@router.get(
    "/queries",
    response_model=AdminQueryListResponse,
    response_model_by_alias=True,
)
async def list_admin_queries(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    handling: str | None = Query(default=None),
    confidence_tier: str | None = Query(
        default=None,
        alias="confidenceTier",
        pattern="^(GREEN|YELLOW|RED)$",
    ),
    since: datetime | None = Query(default=None),
    principal: Principal = Depends(require_scope("admin:queries:read")),
    session: AsyncSession = Depends(get_tenant_session),
) -> AdminQueryListResponse:
    items, next_cursor = await RunTraceRepository(session).list_by_tenant(
        tenant_id=principal.tenant_id,
        cursor=cursor,
        limit=limit,
        handling=handling,
        confidence_tier=confidence_tier,
        since=since,
    )
    return AdminQueryListResponse(items=items, next_cursor=next_cursor)


@router.get(
    "/flagged",
    response_model=AdminFlaggedListResponse,
    response_model_by_alias=True,
)
async def list_admin_flagged(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    flag_reason: str | None = Query(default=None, alias="flagReason"),
    principal: Principal = Depends(require_scope("admin:flagged:read")),
    session: AsyncSession = Depends(get_tenant_session),
) -> AdminFlaggedListResponse:
    items, next_cursor = await FlaggedQueryRepository(session).list_by_tenant(
        tenant_id=principal.tenant_id,
        cursor=cursor,
        limit=limit,
        flag_reason=flag_reason,
    )
    if "admin:raw_sensitive:read" not in principal.scopes:
        items = [
            item.model_copy(update={"raw_sensitive_log_id": None})
            for item in items
        ]
    return AdminFlaggedListResponse(items=items, next_cursor=next_cursor)


@router.get(
    "/audit",
    response_model=AdminAuditListResponse,
    response_model_by_alias=True,
)
async def list_admin_audit(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None, alias="resourceType"),
    since: datetime | None = Query(default=None),
    principal: Principal = Depends(require_scope("admin:audit:read")),
    session: AsyncSession = Depends(get_tenant_session),
) -> AdminAuditListResponse:
    items, next_cursor = await AuditRepository(session).list_by_tenant(
        tenant_id=principal.tenant_id,
        cursor=cursor,
        limit=limit,
        action=action,
        resource_type=resource_type,
        since=since,
    )
    return AdminAuditListResponse(items=items, next_cursor=next_cursor)


@router.get(
    "/queries/{runId}/raw",
    response_model=AdminRawSensitiveResponse,
    response_model_by_alias=True,
)
async def get_admin_query_raw(
    run_id: str = Path(alias="runId"),
    # `require_scope` resolves before `get_tenant_session`, so a caller lacking the scope is
    # rejected (403) before any DB transaction opens.
    principal: Principal = Depends(require_scope("admin:raw_sensitive:read")),
    session: AsyncSession = Depends(get_tenant_session),
    cipher: SensitiveLogCipher | None = Depends(get_sensitive_log_cipher),
) -> AdminRawSensitiveResponse:
    """Admin-only un-redacted view of a run's raw sensitive log (auth-context.md §Raw views).

    Returns 404 (never 403) when no raw log exists for the run in this tenant, so the endpoint
    never discloses whether a run id belongs to another tenant's history. Each successful read
    decrypts the stored blob and writes an `action='raw_sensitive_view'` audit row.
    """
    log = await RawSensitiveLogRepository(session).get_by_run_id(
        tenant_id=principal.tenant_id, run_id=run_id
    )
    if log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": f"no raw sensitive log for run {run_id}"},
        )
    if cipher is None:
        # Unreachable in production (the boot guard requires the key) — fail closed regardless.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "internal_error",
                "message": "sensitive-log decryption key is not configured",
            },
        )
    try:
        raw_query_text = cipher.decrypt(
            EncryptedBlob(
                nonce=log.nonce, ciphertext=log.ciphertext, key_version=log.key_version
            )
        )
    except CipherDecryptError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "internal_error",
                "message": "failed to decrypt raw sensitive log",
            },
        ) from exc

    audit_entry_id = await AuditRepository(session).insert(
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        actor_role=principal.role,
        action="raw_sensitive_view",
        resource_type="run",
        resource_id=run_id,
    )
    return AdminRawSensitiveResponse(
        run_id=run_id,
        tenant_id=principal.tenant_id,
        raw_query_text=raw_query_text,
        raw_sensitive_payload={
            "logId": log.log_id,
            "keyVersion": log.key_version,
            "capturedAt": log.created_at.isoformat(),
            "expiresAt": log.expires_at.isoformat(),
        },
        audit_entry_id=audit_entry_id,
    )


class CertifyModelRouteRequest(WireModel):
    certification_notes: str = Field(min_length=1)


@router.patch(
    "/model-routes/{routeId}/certify",
    response_model=ModelRoute,
    response_model_by_alias=True,
)
async def certify_model_route(
    body: CertifyModelRouteRequest,
    route_id: str = Path(alias="routeId"),
    # `require_scope` is resolved before `get_tenant_session`, so a non-owner is rejected (403)
    # without ever opening a DB transaction.
    principal: Principal = Depends(require_scope("model_route:certify")),
    session: AsyncSession = Depends(get_tenant_session),
) -> ModelRoute:
    """Owner-only PATCH that promotes a route to `certified` (ADR-0004), enforcing the binding
    gates: a passing safety-suite run for every route, plus a passing retrieval-eval run for
    embedding/rerank routes (`docs/contracts/retrieval-eval-suite.md`). Records an
    `action='model_route_certified'` audit entry.
    """
    repo = ModelRouteRepository(session)
    route = await repo.get(route_id)
    if route is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": f"model route {route_id} not found"},
        )

    safety_passed = (
        await repo.safety_run_passed(route.safety_suite_run_id)
        if route.safety_suite_run_id
        else False
    )
    retrieval_eval_passed: bool | None = None
    if requires_retrieval_eval_gate(route):
        retrieval_eval_passed = (
            await repo.retrieval_eval_run_passed(route.retrieval_eval_run_id)
            if route.retrieval_eval_run_id
            else False
        )

    decision = evaluate_certification(
        route, safety_passed=safety_passed, retrieval_eval_passed=retrieval_eval_passed
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "route_not_certifiable", "message": decision.reason},
        )

    certified = await repo.mark_certified(
        route_id=route_id, certified_by=principal.user_id
    )
    await AuditRepository(session).insert(
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        actor_role=principal.role,
        action="model_route_certified",
        resource_type="model_route",
        resource_id=route_id,
        details={
            "certificationNotes": body.certification_notes,
            "safetySuiteRunId": route.safety_suite_run_id,
            "retrievalEvalRunId": route.retrieval_eval_run_id,
        },
    )
    return certified


__all__ = ["router"]
