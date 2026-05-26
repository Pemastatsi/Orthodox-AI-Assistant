"""Re-export shared backend test fixtures so integration tests under `tests/` can use them.

The actual fixture definitions live in `backend/tests/conftest.py`. Without this re-export,
tests in `tests/integration/` that reference `postgres_available`, `qdrant_available`,
`clean_tables`, etc. error at runtime with "fixture not found".
"""

from __future__ import annotations

from backend.tests.conftest import (
    clean_tables,
    db_engine,
    postgres_available,
    qdrant_available,
    qdrant_test_store,
    redis_available,
    redis_client,
    seed_tenant,
)

__all__ = [
    "clean_tables",
    "db_engine",
    "postgres_available",
    "qdrant_available",
    "qdrant_test_store",
    "redis_available",
    "redis_client",
    "seed_tenant",
]
