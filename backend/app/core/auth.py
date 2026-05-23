"""Auth resolution per docs/contracts/auth-context.md.

T-001 ships the dev-mode header decoder plus a Clerk placeholder that raises NotImplementedError.
Real JWKS verification lands in T-005."""

from __future__ import annotations

import base64
import json
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.domain.models.principal import Principal

logger = get_logger(__name__)


_ROLE_SCOPES: dict[str, list[str]] = {
    "member": ["query:read", "corpus:read"],
    "scholar": ["query:read", "corpus:read", "tenant:config:read"],
    "content_manager": [
        "query:read",
        "corpus:read",
        "tenant:config:read",
        "corpus:write",
        "corpus:approve",
        "admin:queries:read",
        "admin:flagged:read",
    ],
    "admin": [
        "query:read",
        "corpus:read",
        "tenant:config:read",
        "corpus:write",
        "corpus:approve",
        "admin:queries:read",
        "admin:flagged:read",
        "admin:audit:read",
        "admin:raw_sensitive:read",
        "tenant:config:write",
        "billing:read",
    ],
    "owner": [
        "query:read",
        "corpus:read",
        "tenant:config:read",
        "corpus:write",
        "corpus:approve",
        "admin:queries:read",
        "admin:flagged:read",
        "admin:audit:read",
        "admin:raw_sensitive:read",
        "tenant:config:write",
        "billing:read",
        "model_route:certify",
    ],
}


def scopes_for_role(role: str) -> list[str]:
    return list(_ROLE_SCOPES.get(role, _ROLE_SCOPES["member"]))


def make_dev_principal(
    *,
    tenant_id: str = "dev-tenant",
    role: str = "member",
    user_id: str | None = None,
) -> Principal:
    """Construct a Principal for dev-mode tests; defaults mirror auth-context.md §Header format."""
    return Principal(
        user_id=user_id or f"dev-user-{role}",
        clerk_user_id="dev-clerk-user",
        tenant_id=tenant_id,
        clerk_org_id="dev-clerk-org",
        role=role,
        scopes=scopes_for_role(role),
        data_region="us",
    )


def _decode_dev_header(header_value: str) -> Principal | None:
    try:
        raw = base64.b64decode(header_value, validate=True).decode("utf-8")
        payload: dict[str, Any] = json.loads(raw)
    except (ValueError, json.JSONDecodeError):
        return None

    tenant_id = payload.get("tenantId")
    role = payload.get("role")
    if not tenant_id or not role:
        return None

    fallback = make_dev_principal(tenant_id=tenant_id, role=role)
    merged: dict[str, Any] = {
        "userId": payload.get("userId") or fallback.user_id,
        "clerkUserId": payload.get("clerkUserId") or fallback.clerk_user_id,
        "tenantId": tenant_id,
        "clerkOrgId": payload.get("clerkOrgId") or fallback.clerk_org_id,
        "role": role,
        "scopes": payload.get("scopes") or scopes_for_role(role),
        "dataRegion": payload.get("dataRegion") or "us",
    }
    try:
        return Principal.model_validate(merged)
    except Exception:
        return None


def resolve_principal(
    *,
    authorization: str | None,
    dev_principal_header: str | None,
    settings: Settings | None = None,
) -> Principal:
    """Resolve a request to a Principal. Honors AUTH_PROVIDER."""
    cfg = settings or get_settings()

    if cfg.auth_provider == "dev":
        if dev_principal_header:
            decoded = _decode_dev_header(dev_principal_header)
            if decoded is not None:
                return decoded
        return make_dev_principal()

    # AUTH_PROVIDER=clerk — JWKS verification lands in T-005.
    del authorization  # unused in the scaffold stub; T-005 will verify the bearer token here
    raise NotImplementedError(
        "Clerk JWKS verification is implemented in T-005; "
        "set AUTH_PROVIDER=dev for local development."
    )


def log_auth_startup(settings: Settings | None = None) -> None:
    cfg = settings or get_settings()
    logger.info(
        "auth.startup",
        auth_provider=cfg.auth_provider,
        app_env=cfg.app_env,
    )


__all__ = [
    "make_dev_principal",
    "resolve_principal",
    "scopes_for_role",
    "log_auth_startup",
]
