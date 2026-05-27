"""F-23 (exit #8): retention worker deletes expired raw_sensitive_logs.

Two invocations are exercised: one against a seeded expired row, one against no rows.
Both runs must emit `worker.retention.completed` with the correct `deleted_count`. The
log assertions use structlog's capture utility so we don't depend on stdout serialisation.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
import structlog
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


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
