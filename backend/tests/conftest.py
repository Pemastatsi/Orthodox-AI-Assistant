"""Pytest fixtures for the backend.

Tests fall into two tiers:
  - Unit tests under `tests/unit/` run with no external services.
  - Integration tests under `tests/integration/` need Postgres (and sometimes Qdrant / Redis);
    fixtures here detect availability at collection time and skip cleanly when the services
    aren't reachable so CI selectors stay simple.
"""

from __future__ import annotations

import asyncio
import os
import socket
from collections.abc import AsyncIterator
from urllib.parse import urlparse

import pytest
import pytest_asyncio

os.environ.setdefault("AUTH_PROVIDER", "dev")
os.environ.setdefault("APP_ENV", "development")


def _can_connect(host: str, port: int, *, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _parse_host_port(url: str, default_port: int) -> tuple[str, int]:
    parsed = urlparse(url)
    return parsed.hostname or "localhost", parsed.port or default_port


@pytest.fixture(scope="session")
def postgres_available() -> bool:
    from app.core.config import get_settings

    host, port = _parse_host_port(get_settings().database_url, 5432)
    return _can_connect(host, port)


@pytest.fixture(scope="session")
def qdrant_available() -> bool:
    from app.core.config import get_settings

    qdrant_url = get_settings().qdrant_url or "http://localhost:6333"
    host, port = _parse_host_port(qdrant_url, 6333)
    return _can_connect(host, port)


@pytest.fixture(scope="session")
def redis_available() -> bool:
    from app.core.config import get_settings

    host, port = _parse_host_port(get_settings().redis_url, 6379)
    return _can_connect(host, port)


@pytest_asyncio.fixture()
async def db_engine(postgres_available: bool) -> AsyncIterator[object]:
    if not postgres_available:
        pytest.skip("Postgres not reachable; integration test skipped")
    from app.domain.repositories._base import dispose_engine, init_engine

    engine = init_engine()
    try:
        yield engine
    finally:
        await dispose_engine()


@pytest_asyncio.fixture()
async def clean_tables(db_engine: object) -> AsyncIterator[None]:
    """Truncate all tenant-scoped tables before each integration test."""
    from app.domain.repositories._base import get_sessionmaker
    from sqlalchemy import text

    sm = get_sessionmaker()
    async with sm() as session:
        # Truncate in FK-safe order.
        await session.execute(
            text(
                "TRUNCATE TABLE audit_entries, flagged_queries, raw_sensitive_logs, "
                "run_traces, ingest_jobs, sessions, billing_usage, chunks, sources, "
                "users, tenants RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()
    yield
    async with sm() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE audit_entries, flagged_queries, raw_sensitive_logs, "
                "run_traces, ingest_jobs, sessions, billing_usage, chunks, sources, "
                "users, tenants RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()


@pytest_asyncio.fixture()
async def seed_tenant(clean_tables: None) -> AsyncIterator[tuple[str, str]]:
    """Insert a (tenant, user) pair so FK constraints on sources/chunks pass."""
    from app.domain.repositories._base import get_sessionmaker
    from sqlalchemy import text

    tenant_id = "tn_test"
    user_id = "usr_test"
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(
            text(
                "INSERT INTO tenants (tenant_id, name, clerk_org_id, status, data_region) "
                "VALUES (:t, 'Test Tenant', 'clerk_org_test', 'active', 'us')"
            ),
            {"t": tenant_id},
        )
        await session.execute(
            text(
                "INSERT INTO users (user_id, clerk_user_id, tenant_id, role, status) "
                "VALUES (:u, 'clerk_usr_test', :t, 'content_manager', 'active')"
            ),
            {"u": user_id, "t": tenant_id},
        )
        await session.commit()
    yield tenant_id, user_id


@pytest_asyncio.fixture()
async def qdrant_test_store(qdrant_available: bool):
    if not qdrant_available:
        pytest.skip("Qdrant not reachable; integration test skipped")
    import contextlib

    from app.adapters.providers.openai_provider import embedding_dimension_for
    from app.adapters.vector_store.base import VectorFilter
    from app.adapters.vector_store.qdrant_store import QdrantStore

    store = QdrantStore(embedding_dimension=embedding_dimension_for("text-embedding-3-small"))
    try:
        yield store
        # Drop any test points we created.
        with contextlib.suppress(Exception):
            await store.delete_by_filter(filters=VectorFilter(tenant_id="tn_test"))
    finally:
        await store.close()


@pytest_asyncio.fixture()
async def redis_client(redis_available: bool):
    if not redis_available:
        pytest.skip("Redis not reachable; integration test skipped")
    from app.core.config import get_settings
    from redis.asyncio import Redis

    client = Redis.from_url(get_settings().redis_url, decode_responses=False)
    try:
        yield client
    finally:
        await client.aclose()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Make sure asyncio is the default mode (mirrors pytest.ini)."""
    for item in items:
        if asyncio.iscoroutinefunction(getattr(item, "function", None)):
            item.add_marker(pytest.mark.asyncio)
