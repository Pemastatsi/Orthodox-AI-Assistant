"""Re-export shared backend test fixtures for the integration tests in this directory.

Lives in `tests/integration/` (not the shared `tests/` root) on purpose: this re-export
pulls in backend dependencies, and scoping it here keeps lightweight suites like
`tests/safety/` runnable with pytest alone (the CI safety-suite-fixtures job installs
pytest only).

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
