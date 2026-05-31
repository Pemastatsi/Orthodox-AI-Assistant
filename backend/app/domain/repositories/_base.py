"""Async SQLAlchemy engine + session lifecycle for the repository layer.

Per `code-gen-guide.md` §Layering: repositories are the only place that writes raw SQL. Everything
above the repository layer hands the repo a `tenant_id` (sourced from the request Principal) and
the repo unconditionally adds `WHERE tenant_id = :tenant_id` to every read and write.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_engine(settings: Settings | None = None, *, admin: bool = False) -> AsyncEngine:
    """Idempotent engine init. Call once per process (e.g., FastAPI startup, worker startup).

    `admin=True` selects the `database_admin_url` (the `app_admin` BYPASSRLS role) for
    intentionally cross-tenant processes — migrations, seeders, and the retention/ingestion
    workers (ADR-0016 Rules 3 & 5). It falls back to `database_url` when no admin URL is
    configured, so dev (single superuser URL) keeps working. The request path uses the default
    (`admin=False`) → the `app_runtime` role, which is subject to RLS.
    """
    global _engine, _sessionmaker
    if _engine is not None:
        return _engine
    cfg = settings or get_settings()
    url = (cfg.database_admin_url or cfg.database_url) if admin else cfg.database_url
    _engine = create_async_engine(
        url,
        future=True,
        echo=False,
        pool_pre_ping=True,
    )
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine


def get_engine() -> AsyncEngine:
    if _engine is None:
        return init_engine()
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        init_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def dispose_engine() -> None:
    """Close the pool. Call once per process at shutdown."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Open a session with `begin()` semantics — commits on success, rolls back on error."""
    sm = get_sessionmaker()
    async with sm() as session, session.begin():
        yield session


def assert_tenant(tenant_id: str | None) -> str:
    """Repository invariant: every public method requires a non-empty tenant_id."""
    if not tenant_id or not tenant_id.strip():
        raise ValueError("tenant_id required")
    return tenant_id


def to_jsonb(value: Any) -> Any:
    """Helper: SQLAlchemy text() parameter binding doesn't coerce dicts to jsonb on its own.

    asyncpg accepts a Python dict directly for jsonb columns; this function is here for symmetry
    so call sites can be explicit.
    """
    return value


__all__ = [
    "AsyncSession",
    "assert_tenant",
    "dispose_engine",
    "get_engine",
    "get_sessionmaker",
    "init_engine",
    "session_scope",
    "to_jsonb",
]
