"""FastAPI dependencies shared by the v1 router modules."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis

from app.core.auth import resolve_principal
from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenRoleError
from app.domain.models.principal import Principal
from app.domain.repositories._base import AsyncSession, session_scope


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


__all__ = [
    "get_principal",
    "get_redis",
    "get_session",
    "get_settings_dep",
    "require_scope",
    "shutdown_redis",
]
