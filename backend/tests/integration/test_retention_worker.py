"""F-23 (exit #8): retention worker deletes expired raw_sensitive_logs.

Two invocations are exercised: one against a seeded expired row, one against no rows.
Both runs must emit `worker.retention.completed` with the correct `deleted_count`. The
log assertions use structlog's capture utility so we don't depend on stdout serialisation.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
import structlog
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _reset_structlog() -> Iterator[None]:
    """Isolate structlog config per test so LogCapture assertions are deterministic.

    `app.core.logging.configure_logging()` (run by any earlier test that starts the app via
    TestClient) sets `cache_logger_on_first_use=True`. With caching on, the module-level `logger`
    proxy in `retention_cleanup` caches a bound logger wired to the *first* test's LogCapture, so a
    later test's fresh `structlog.configure(processors=[cap])` is ignored and `cap.entries` stays
    empty. `reset_defaults()` turns caching back off (and clears global config) before each test so
    every call re-resolves the active processors; we reset again afterwards so this file does not
    leak its own structlog state into later tests.
    """
    structlog.reset_defaults()
    try:
        yield
    finally:
        structlog.reset_defaults()


@pytest_asyncio.fixture()
async def session_factory(seed_tenant: tuple[str, str]):
    """Inject the standard session_scope as the retention worker's session_factory."""
    del seed_tenant
    from app.domain.repositories._base import session_scope

    return session_scope


@pytest.mark.asyncio
async def test_deletes_expired_row_and_emits_count_1(
    seed_tenant: tuple[str, str], session_factory
) -> None:
    tenant_id, user_id = seed_tenant
    expired = datetime.now(UTC) - timedelta(hours=1)
    log_id = "rsl_expired_1"

    from app.domain.repositories._base import session_scope

    async with session_scope() as session:
        await session.execute(
            text(
                """
                INSERT INTO raw_sensitive_logs (
                    log_id, tenant_id, user_id, ciphertext, key_version, nonce,
                    expires_at, created_at
                ) VALUES (:l, :t, :u, :ct, 'v1', :n, :exp, now())
                """
            ),
            {
                "l": log_id,
                "t": tenant_id,
                "u": user_id,
                "ct": b"\x00" * 17,
                "n": b"\x01" * 12,
                "exp": expired,
            },
        )
        await session.commit()

    cap = structlog.testing.LogCapture()
    structlog.configure(processors=[cap])
    from app.workers.tasks.retention_cleanup import run_retention_cleanup

    result = await run_retention_cleanup(session_factory=session_factory)

    assert result["deleted_count"] == 1
    assert "next_run_at" in result

    events = [e for e in cap.entries if e["event"].startswith("worker.retention.")]
    completed = [e for e in events if e["event"] == "worker.retention.completed"]
    started = [e for e in events if e["event"] == "worker.retention.started"]
    assert len(started) == 1
    assert len(completed) == 1
    assert completed[0]["deleted_count"] == 1
    assert completed[0]["target_table"] == "raw_sensitive_logs"
    assert "next_run_at" in completed[0]

    async with session_scope() as session:
        row = await session.execute(
            text("SELECT 1 FROM raw_sensitive_logs WHERE log_id = :l"),
            {"l": log_id},
        )
        assert row.one_or_none() is None


@pytest.mark.asyncio
async def test_no_expired_rows_still_emits_count_0(
    seed_tenant: tuple[str, str], session_factory
) -> None:
    del seed_tenant
    cap = structlog.testing.LogCapture()
    structlog.configure(processors=[cap])
    from app.workers.tasks.retention_cleanup import run_retention_cleanup

    result = await run_retention_cleanup(session_factory=session_factory)

    assert result["deleted_count"] == 0
    completed = [
        e
        for e in cap.entries
        if e.get("event") == "worker.retention.completed"
    ]
    assert len(completed) == 1
    assert completed[0]["deleted_count"] == 0


@pytest.mark.asyncio
async def test_non_expired_row_is_preserved(
    seed_tenant: tuple[str, str], session_factory
) -> None:
    """A row whose `expires_at` is in the future must survive the sweep."""
    tenant_id, user_id = seed_tenant
    future = datetime.now(UTC) + timedelta(days=29)
    log_id = "rsl_future_1"

    from app.domain.repositories._base import session_scope

    async with session_scope() as session:
        await session.execute(
            text(
                """
                INSERT INTO raw_sensitive_logs (
                    log_id, tenant_id, user_id, ciphertext, key_version, nonce,
                    expires_at, created_at
                ) VALUES (:l, :t, :u, :ct, 'v1', :n, :exp, now())
                """
            ),
            {
                "l": log_id,
                "t": tenant_id,
                "u": user_id,
                "ct": b"\x00" * 17,
                "n": b"\x01" * 12,
                "exp": future,
            },
        )
        await session.commit()

    from app.workers.tasks.retention_cleanup import run_retention_cleanup

    result = await run_retention_cleanup(session_factory=session_factory)
    assert result["deleted_count"] == 0

    async with session_scope() as session:
        row = await session.execute(
            text("SELECT 1 FROM raw_sensitive_logs WHERE log_id = :l"),
            {"l": log_id},
        )
        assert row.one_or_none() is not None


@pytest.mark.asyncio
async def test_writes_retention_purged_audit_row(
    seed_tenant: tuple[str, str], session_factory
) -> None:
    """Every run writes one `retention_purged` audit row attributed to the platform sentinel —
    the DB-visible signal exit criterion #8c reads. Asserted on a no-expired-rows run so the row
    is shown to be unconditional (deleted_count == 0), mirroring the always-emitted log event."""
    del seed_tenant
    from app.domain.repositories._base import session_scope
    from app.workers.tasks.retention_cleanup import run_retention_cleanup

    result = await run_retention_cleanup(session_factory=session_factory)
    assert result["deleted_count"] == 0

    async with session_scope() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT tenant_id, actor_user_id, actor_role, resource_type, resource_id,
                           details
                    FROM audit_entries
                    WHERE action = 'retention_purged'
                    ORDER BY occurred_at DESC
                    LIMIT 1
                    """
                )
            )
        ).mappings().one_or_none()

    assert row is not None, "retention_purged audit row must be written every run"
    assert row["tenant_id"] == "tn_platform"
    assert row["actor_user_id"] == "usr_system"
    assert row["actor_role"] == "system"
    assert row["resource_type"] == "raw_sensitive_logs"
    assert row["details"]["deleted_count"] == 0
    assert "next_run_at" in row["details"]
