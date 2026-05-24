"""FastAPI dependencies shared by the v1 router modules."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis

from app.adapters.providers.base import LLMProvider
from app.adapters.providers.openai_provider import (
    OpenAIProvider,
    embedding_dimension_for,
)
from app.adapters.sparse.bm25_embedder import Bm25SparseEmbedder
from app.adapters.vector_store.base import VectorStore
from app.adapters.vector_store.qdrant_store import QdrantStore
from app.core.auth import resolve_principal
from app.core.config import Settings, get_settings
from app.core.errors import ApiErrorCode, ForbiddenRoleError
from app.domain.agents.query_analyzer import QueryAnalyzer
from app.domain.models.principal import Principal
from app.domain.repositories._base import AsyncSession, session_scope
from app.domain.services.retriever import Retriever
from app.domain.services.safety_config import (
    SafetyConfig,
    load_sensitivity_keywords,
)


def get_settings_dep() -> Settings:
    return get_settings()


async def get_principal(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
) -> Principal:
    authorization = request.headers.get("authorization")
    dev_header = request.headers.get("x-dev-principal")
    try:
        return resolve_principal(
            authorization=authorization,
            dev_principal_header=dev_header,
            settings=settings,
        )
    except NotImplementedError as exc:  # AUTH_PROVIDER=clerk before T-005 lands
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "auth_provider_unavailable", "message": str(exc)},
        ) from exc


def require_scope(scope: str):
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
    async with session_scope() as session:
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


# ---- Query path dependencies (T-003) -------------------------------------------------

_safety_config: SafetyConfig | None = None
_embedding_provider: LLMProvider | None = None
_vector_store: QdrantStore | None = None
_sparse_embedder: Bm25SparseEmbedder | None = None


def get_safety_config(settings: Settings = Depends(get_settings_dep)) -> SafetyConfig:
    global _safety_config
    if _safety_config is None:
        _safety_config = load_sensitivity_keywords(settings.sensitivity_keywords_path)
    return _safety_config


def get_embedding_provider(
    settings: Settings = Depends(get_settings_dep),
) -> LLMProvider:
    global _embedding_provider
    if _embedding_provider is None:
        _embedding_provider = OpenAIProvider(
            settings=settings, model="text-embedding-3-small"
        )
    return _embedding_provider


class _DeferredQueryAnalyzerProvider:
    """Placeholder LLMProvider whose `generate_structured` raises an HTTPException.

    T-001 shipped the `LLMProvider` Protocol; the real Anthropic adapter lands in T-004.
    Until then, queries that would invoke A1/A2 over the LLM return 503 feature_deferred.
    Hard-trigger queries never reach `generate_structured` and therefore work in production.
    Tests override `get_query_analyzer_provider` with `FakeStructuredProvider`.
    """

    name = "deferred"

    async def generate_structured(self, **kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": ApiErrorCode.FEATURE_DEFERRED.value,
                "message": (
                    "A1/A2 LLM provider is not yet wired (Anthropic adapter lands in T-004)."
                ),
            },
        )

    async def generate_text(self, **kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        raise NotImplementedError

    def stream_text(self, **kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        raise NotImplementedError

    async def count_tokens(self, **kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        raise NotImplementedError

    async def embed_texts(self, **kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        raise NotImplementedError

    @property
    def supports_prompt_cache(self) -> bool:
        return False

    @property
    def supports_batch(self) -> bool:
        return False

    @property
    def supports_json_mode(self) -> bool:
        return False

    @property
    def supports_embeddings(self) -> bool:
        return False


_deferred_provider = _DeferredQueryAnalyzerProvider()


def get_query_analyzer_provider() -> LLMProvider:
    return _deferred_provider  # type: ignore[return-value]


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


async def shutdown_query_resources() -> None:
    global _vector_store
    if _vector_store is not None:
        await _vector_store.close()
        _vector_store = None


# Used by tests to drop caches when a different stub config or vector-store is needed.
def _reset_query_caches() -> None:
    global _safety_config, _embedding_provider, _vector_store, _sparse_embedder
    _safety_config = None
    _embedding_provider = None
    _vector_store = None
    _sparse_embedder = None


__all__ = [
    "build_query_analyzer",
    "build_retriever",
    "get_embedding_provider",
    "get_principal",
    "get_query_analyzer_provider",
    "get_redis",
    "get_safety_config",
    "get_session",
    "get_settings_dep",
    "get_sparse_embedder",
    "get_vector_store",
    "require_scope",
    "shutdown_query_resources",
    "shutdown_redis",
]
