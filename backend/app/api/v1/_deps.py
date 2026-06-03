"""FastAPI dependencies shared by the v1 router modules."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis

from app.adapters.providers.anthropic_provider import AnthropicProvider
from app.adapters.providers.base import LLMProvider
from app.adapters.providers.openai_provider import (
    OpenAIProvider,
    embedding_dimension_for,
)
from app.adapters.sparse.bm25_embedder import Bm25SparseEmbedder
from app.adapters.vector_store.base import VectorStore
from app.adapters.vector_store.qdrant_store import QdrantStore
from app.core.auth import (
    ClerkClaims,
    bearer_token,
    resolve_principal,
    scopes_for_role,
    verify_clerk_token,
)
from app.core.config import Settings, get_settings
from app.core.errors import (
    ApiException,
    AuthInvalidTokenError,
    AuthMissingOrgError,
    ForbiddenRoleError,
    TenantInactiveError,
    TenantMismatchError,
    TenantNotFoundError,
)
from app.core.tenant_context import set_tenant_guc
from app.domain.agents.composer import Composer
from app.domain.agents.evidence_packager import EvidencePackager
from app.domain.agents.query_analyzer import QueryAnalyzer
from app.domain.agents.verifier import Verifier, VerifierConfig
from app.domain.models.principal import Principal
from app.domain.repositories._base import (
    AsyncSession,
    admin_session_scope,
    session_scope,
)
from app.domain.repositories.identity_repository import IdentityRepository
from app.domain.services.cache_service import ResponseCache
from app.domain.services.encryption_service import (
    SensitiveLogCipher,
    load_key_map_from_env,
)
from app.domain.services.retriever import Retriever
from app.domain.services.safety_config import (
    PastoralConfig,
    SafetyConfig,
    load_pastoral_filters,
    load_sensitivity_keywords,
)


def get_settings_dep() -> Settings:
    return get_settings()


async def _resolve_clerk_identity(claims: ClerkClaims) -> Principal:
    """Map verified Clerk claims to a Principal: resolve the tenant by org, the user by Clerk id
    (JIT-provisioning a first-seen member), then build the Principal. Runs on the app_admin
    (BYPASSRLS) session because the tenant isn't known yet (RLS chicken-and-egg; ADR-0016)."""
    if not claims.org_id:
        raise AuthMissingOrgError("Clerk token has no active organization")
    async with admin_session_scope() as session:
        repo = IdentityRepository(session)
        tenant = await repo.get_tenant_by_clerk_org(claims.org_id)
        if tenant is None:
            raise TenantNotFoundError("no tenant is mapped to the Clerk organization")
        if tenant.status != "active":
            raise TenantInactiveError(f"tenant is {tenant.status}")
        user = await repo.get_user_by_clerk_id(claims.sub)
        if user is None:
            if not claims.org_role:
                raise AuthInvalidTokenError("cannot provision a user without an org role")
            user = await repo.jit_provision_user(
                clerk_user_id=claims.sub, tenant_id=tenant.tenant_id
            )
        if user.tenant_id != tenant.tenant_id:
            raise TenantMismatchError("user does not belong to the resolved tenant")
    return Principal(
        user_id=user.user_id,
        clerk_user_id=claims.sub,
        tenant_id=tenant.tenant_id,
        clerk_org_id=claims.org_id,
        role=user.role,
        scopes=scopes_for_role(user.role),
        data_region=tenant.data_region,
    )


async def get_principal(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
) -> Principal:
    """Resolve the request Principal. Dev mode decodes the `x-dev-principal` header; Clerk mode
    verifies the bearer JWT then resolves identity. Typed auth/tenant failures map to their HTTP
    status + error code; we never silently fall back to a dev principal."""
    if settings.auth_provider == "dev":
        return resolve_principal(
            authorization=request.headers.get("authorization"),
            dev_principal_header=request.headers.get("x-dev-principal"),
            settings=settings,
        )
    try:
        claims = verify_clerk_token(bearer_token(request.headers.get("authorization")), settings)
        return await _resolve_clerk_identity(claims)
    except ApiException as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail={"code": exc.code.value, "message": exc.message},
        ) from exc


def require_scope(
    scope: str,
) -> Callable[[Principal], Coroutine[Any, Any, Principal]]:
    """Dependency factory: enforces that the resolved Principal carries the named scope."""

    async def _checker(principal: Principal = Depends(get_principal)) -> Principal:
        if scope not in principal.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": ForbiddenRoleError(required=scope).code.value,
                    "message": f"Required scope: {scope}",
                    "requiredScope": scope,
                },
            )
        return principal

    return _checker


async def get_session() -> AsyncIterator[AsyncSession]:
    """RLS-bypass session: NO tenant GUC is set, so under the `app_runtime` role every
    tenant-scoped table reads zero rows (fail closed). Reserve for genuinely cross-tenant /
    platform-table callers; authenticated tenant-scoped routes MUST use `get_tenant_session`
    so Postgres RLS (ADR-0016) enforces the tenant boundary at the engine layer."""
    async with session_scope() as session:
        yield session


async def get_tenant_session(
    principal: Principal = Depends(get_principal),
) -> AsyncIterator[AsyncSession]:
    """Per-request session with the RLS tenant GUC set from the resolved Principal (ADR-0016).

    `session_scope()` opens the transaction; `set_tenant_guc` issues `SET LOCAL
    app.current_tenant_id = <principal.tenant_id>` inside it (transaction-scoped, never
    `SET SESSION` — ADR-0016 Rule 6). Under the `app_runtime` role this makes the
    `tenant_isolation_policy` enforce the boundary; if this dependency is ever omitted on a
    tenant route, the unset GUC means zero rows (fail closed) rather than a cross-tenant leak.
    """
    async with session_scope() as session:
        await set_tenant_guc(session, principal.tenant_id)
        yield session


# Process-singleton Redis client (lazily created).
_redis: Redis | None = None


def get_redis(settings: Settings = Depends(get_settings_dep)) -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=False)
    return _redis


async def shutdown_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def get_response_cache(redis: Redis = Depends(get_redis)) -> ResponseCache:
    return ResponseCache(redis=redis)


_cipher: SensitiveLogCipher | None = None


def get_sensitive_log_cipher(
    settings: Settings = Depends(get_settings_dep),
) -> SensitiveLogCipher | None:
    """Lazy-build the cipher from settings. Returns None if no key is configured
    (development without sensitive-log capture); callers must handle that case."""
    global _cipher
    if _cipher is not None:
        return _cipher
    if not settings.sensitive_log_data_key_base64:
        return None
    keys = load_key_map_from_env(
        settings.sensitive_log_data_key_base64,
        settings.sensitive_log_key_version,
    )
    _cipher = SensitiveLogCipher(keys=keys, active_version=settings.sensitive_log_key_version)
    return _cipher


# ---- Query path dependencies (T-003 / T-004) -----------------------------------------

_safety_config: SafetyConfig | None = None
_pastoral_config: PastoralConfig | None = None
_embedding_provider: LLMProvider | None = None
_anthropic_provider: AnthropicProvider | None = None
_vector_store: QdrantStore | None = None
_sparse_embedder: Bm25SparseEmbedder | None = None


def get_safety_config(settings: Settings = Depends(get_settings_dep)) -> SafetyConfig:
    global _safety_config
    if _safety_config is None:
        _safety_config = load_sensitivity_keywords(settings.sensitivity_keywords_path)
    return _safety_config


def get_pastoral_config(
    settings: Settings = Depends(get_settings_dep),
) -> PastoralConfig:
    global _pastoral_config
    if _pastoral_config is None:
        _pastoral_config = load_pastoral_filters(settings.pastoral_filters_path)
    return _pastoral_config


def get_embedding_provider(
    settings: Settings = Depends(get_settings_dep),
) -> LLMProvider:
    global _embedding_provider
    if _embedding_provider is None:
        _embedding_provider = OpenAIProvider(settings=settings, model="text-embedding-3-small")
    return _embedding_provider


def _get_anthropic_provider(settings: Settings) -> LLMProvider:
    global _anthropic_provider
    if _anthropic_provider is None:
        _anthropic_provider = AnthropicProvider(settings=settings)
    return _anthropic_provider


def get_query_analyzer_provider(
    settings: Settings = Depends(get_settings_dep),
) -> LLMProvider:
    return _get_anthropic_provider(settings)


def get_composer_provider(
    settings: Settings = Depends(get_settings_dep),
) -> LLMProvider:
    return _get_anthropic_provider(settings)


def get_verifier_provider(
    settings: Settings = Depends(get_settings_dep),
) -> LLMProvider | None:
    """Returns the certified judge provider when `ACTIVE_MODEL_ROUTE_VERIFIER` is non-empty;
    otherwise returns None and A6 runs deterministic checks only (F-08)."""
    if not settings.active_model_route_verifier:
        return None
    return _get_anthropic_provider(settings)


def get_vector_store(settings: Settings = Depends(get_settings_dep)) -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = QdrantStore(
            embedding_dimension=embedding_dimension_for("text-embedding-3-small"),
            settings=settings,
        )
    return _vector_store


def get_sparse_embedder() -> Bm25SparseEmbedder:
    global _sparse_embedder
    if _sparse_embedder is None:
        _sparse_embedder = Bm25SparseEmbedder()
    return _sparse_embedder


def build_query_analyzer(
    *,
    provider: LLMProvider,
    safety_config: SafetyConfig,
    settings: Settings,
) -> QueryAnalyzer:
    return QueryAnalyzer(
        provider=provider,
        safety_config=safety_config,
        prompt_version=settings.active_prompt_version_a1a2,
        model_route_id=settings.active_model_route_a1a2,
    )


def build_retriever(
    *,
    embedding_provider: LLMProvider,
    vector_store: VectorStore,
    sparse_embedder: Bm25SparseEmbedder,
    settings: Settings,
) -> Retriever:
    return Retriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        sparse_embedder=sparse_embedder,
        embedding_route_id=settings.active_model_route_embedding,
    )


def build_evidence_packager(*, settings: Settings) -> EvidencePackager:
    return EvidencePackager(corpus_version=settings.active_schema_version)


def build_composer(*, provider: LLMProvider, settings: Settings) -> Composer:
    return Composer(
        provider=provider,
        prompt_version=settings.active_prompt_version_a5,
        model_route_id=settings.active_model_route_a5,
    )


def build_verifier(
    *,
    pastoral_config: PastoralConfig,
    settings: Settings,
    judge_provider: LLMProvider | None,
) -> Verifier:
    return Verifier(
        pastoral_config=pastoral_config,
        config=VerifierConfig(
            verifier_version=settings.active_verifier_version,
            schema_version=settings.active_schema_version,
            judge_route_id=settings.active_model_route_verifier,
        ),
        judge_provider=judge_provider,
    )


async def shutdown_query_resources() -> None:
    global _vector_store
    if _vector_store is not None:
        await _vector_store.close()
        _vector_store = None


# Used by tests to drop caches when a different stub config or vector-store is needed.
def _reset_query_caches() -> None:
    global _safety_config, _pastoral_config, _embedding_provider, _anthropic_provider
    global _vector_store, _sparse_embedder
    _safety_config = None
    _pastoral_config = None
    _embedding_provider = None
    _anthropic_provider = None
    _vector_store = None
    _sparse_embedder = None


def _reset_cipher_cache() -> None:
    """Test hook: drop the cipher singleton so a different key can be injected."""
    global _cipher
    _cipher = None


__all__ = [
    "build_composer",
    "build_evidence_packager",
    "build_query_analyzer",
    "build_retriever",
    "build_verifier",
    "get_composer_provider",
    "get_embedding_provider",
    "get_pastoral_config",
    "get_principal",
    "get_query_analyzer_provider",
    "get_redis",
    "get_response_cache",
    "get_safety_config",
    "get_sensitive_log_cipher",
    "get_session",
    "get_settings_dep",
    "get_sparse_embedder",
    "get_tenant_session",
    "get_vector_store",
    "get_verifier_provider",
    "require_scope",
    "shutdown_query_resources",
    "shutdown_redis",
]
