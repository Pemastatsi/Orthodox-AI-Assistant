"""Auth resolution per docs/contracts/auth-context.md.

Two providers (`AUTH_PROVIDER`):
- `dev` — the base64 `x-dev-principal` header decoder (`resolve_principal`).
- `clerk` — `verify_clerk_token` validates a Clerk-issued RS256 JWT against the cached JWKS
  (issuer + `azp` allowlist + exp/iat + `sub`); the API layer (`app/api/v1/_deps.py`) then resolves
  the tenant/user and builds the `Principal`. Only token *content* is verified here; the DB identity
  lookup lives in the API layer because it needs the app_admin (BYPASSRLS) session."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

import jwt
from jwt import PyJWKClient

from app.core.config import Settings, get_settings
from app.core.errors import AuthInvalidTokenError, AuthMissingTokenError
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


# ---- Clerk JWKS verification (AUTH_PROVIDER=clerk) -----------------------------------


@dataclass(frozen=True)
class ClerkClaims:
    """The Clerk JWT claims the auth path consumes (auth-context.md §JWT Claims)."""

    sub: str
    org_id: str | None
    org_role: str | None
    azp: str | None


_jwks_client: PyJWKClient | None = None


def _jwks_url(settings: Settings) -> str:
    return f"{settings.clerk_jwt_issuer.rstrip('/')}/.well-known/jwks.json"


def _get_jwks_client(settings: Settings) -> PyJWKClient:
    """Process-cached JWKS client. PyJWKClient caches fetched signing keys for
    `clerk_jwks_cache_seconds` (≤ Clerk's ~1h TTL — auth-context.md §Forbidden patterns)."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(
            _jwks_url(settings),
            cache_keys=True,
            lifespan=settings.clerk_jwks_cache_seconds,
        )
    return _jwks_client


def reset_jwks_client_cache() -> None:
    """Test hook: drop the cached PyJWKClient so a stub key set can be injected."""
    global _jwks_client
    _jwks_client = None


def bearer_token(authorization: str | None) -> str:
    """Extract `<token>` from an `Authorization: Bearer <token>` header (fail closed)."""
    if not authorization:
        raise AuthMissingTokenError("missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthMissingTokenError("Authorization header is not a Bearer token")
    return token.strip()


def verify_clerk_token(token: str, settings: Settings | None = None) -> ClerkClaims:
    """Verify a Clerk RS256 JWT against the cached JWKS and return its claims.

    Validates the signature, `iss` (when configured), `exp`/`iat`, the presence of `sub`, and that
    `azp` is in the `CLERK_AUTHORIZED_PARTIES` allowlist. Any failure → `AuthInvalidTokenError`
    (fail closed). Does NOT touch the database — the tenant/user lookup is the caller's job."""
    cfg = settings or get_settings()
    try:
        signing_key = _get_jwks_client(cfg).get_signing_key_from_jwt(token)
        payload: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=cfg.clerk_jwt_issuer or None,
            options={"require": ["exp", "iat", "sub"], "verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise AuthInvalidTokenError("Clerk token verification failed") from exc

    azp = payload.get("azp")
    allowed = {p.strip() for p in cfg.clerk_authorized_parties.split(",") if p.strip()}
    if allowed and azp not in allowed:
        raise AuthInvalidTokenError("token azp is not an authorized party")

    return ClerkClaims(
        sub=str(payload["sub"]),
        org_id=payload.get("org_id"),
        org_role=payload.get("org_role"),
        azp=azp,
    )


def resolve_principal(
    *,
    authorization: str | None,
    dev_principal_header: str | None,
    settings: Settings | None = None,
) -> Principal:
    """Resolve a request to a Principal in dev mode (AUTH_PROVIDER=dev).

    The Clerk path is resolved by the API layer (`app/api/v1/_deps.py:get_principal`), which needs
    async DB access for the tenant/user lookup; this function stays the synchronous dev-only path.
    """
    cfg = settings or get_settings()

    if cfg.auth_provider == "dev":
        if dev_principal_header:
            decoded = _decode_dev_header(dev_principal_header)
            if decoded is not None:
                return decoded
        return make_dev_principal()

    del authorization
    raise NotImplementedError(
        "Clerk auth is resolved in app/api/v1/_deps.py (get_principal), not resolve_principal."
    )


def log_auth_startup(settings: Settings | None = None) -> None:
    cfg = settings or get_settings()
    logger.info(
        "auth.startup",
        auth_provider=cfg.auth_provider,
        app_env=cfg.app_env,
    )


__all__ = [
    "ClerkClaims",
    "bearer_token",
    "log_auth_startup",
    "make_dev_principal",
    "reset_jwks_client_cache",
    "resolve_principal",
    "scopes_for_role",
    "verify_clerk_token",
]
