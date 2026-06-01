"""Retention worker: deletes expired raw_sensitive_logs rows.

Phase-1→2 exit criterion #8 says the retention cleanup must have executed at least once
successfully. The contract is:

- Emit `worker.retention.started` then `worker.retention.completed`.
- The completed event must carry `deleted_count` (int) and `next_run_at` (ISO 8601).
- Both events must emit even when `deleted_count == 0` so the exit criterion is observable
  on every scheduled run, not only the first run that catches rows.

The function is split so CI tests can call `run_retention_cleanup(session=...)` directly
without spinning up arq. Production runs `retention_cleanup_task` via arq cron, which
opens a fresh session and delegates here.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.logging import get_logger
from app.domain.repositories._base import init_engine, session_scope
from app.domain.repositories.audit_repository import AuditRepository
from app.domain.repositories.raw_sensitive_log_repository import (
    RawSensitiveLogRepository,
)

logger = get_logger(__name__)

# Platform sentinel (migration 0006): the retention sweep is global and actorless, but
# audit_entries requires a tenant + actor (NOT NULL, FK), so the retention_purged row is attributed
# to the platform tenant / system user. actor_role is the descriptive free-text 'system'.
_PLATFORM_TENANT_ID = "tn_platform"
_SYSTEM_USER_ID = "usr_system"


def _next_run_at(now: datetime, cron_minute: int = 5) -> datetime:
    """Compute the next scheduled run time given a `minute N of every hour` cron.

    Phase-1 retention cron is `5 * * * *` — minute 5 of every hour. We mirror that here
    without pulling in a full cron parser; if the schedule changes substantially in
    Phase 2 we will adopt `croniter` and parse the full cron expression.
    """
    candidate = now.replace(minute=cron_minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(hours=1)
    return candidate


async def run_retention_cleanup(
    *,
    session_factory: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Delete expired raw_sensitive_logs and emit the contract log events.

    `session_factory` is callable returning an async session context manager. Defaults to
    the application's `session_scope`. CI tests inject a fixture-bound session_factory so
    the worker runs against the test DB without involving arq.
    """
    when = now or datetime.now(UTC)
    started = time.perf_counter()

    logger.info(
        "worker.retention.started",
        target_table="raw_sensitive_logs",
    )

    next_run = _next_run_at(when)
    factory = session_factory or session_scope
    deleted_count = 0
    async with factory() as session:
        repo = RawSensitiveLogRepository(session)
        deleted_count = await repo.delete_expired(now=when)

        # Persist the DB-visible signal for Phase-1→2 exit criterion #8c. Written every run (even
        # deleted_count == 0), mirroring the always-emitted completed log event, so the criterion
        # is observable on any scheduled run. Same session as the delete → commits atomically.
        await AuditRepository(session).insert(
            tenant_id=_PLATFORM_TENANT_ID,
            actor_user_id=_SYSTEM_USER_ID,
            actor_role="system",
            action="retention_purged",
            resource_type="raw_sensitive_logs",
            resource_id="retention_sweep",
            details={
                "deleted_count": deleted_count,
                "next_run_at": next_run.isoformat(),
            },
        )

    duration_ms = int((time.perf_counter() - started) * 1000)

    logger.info(
        "worker.retention.completed",
        target_table="raw_sensitive_logs",
        deleted_count=deleted_count,
        duration_ms=duration_ms,
        next_run_at=next_run.isoformat(),
    )

    return {
        "deleted_count": deleted_count,
        "duration_ms": duration_ms,
        "next_run_at": next_run.isoformat(),
    }


async def retention_cleanup_task(ctx: dict[str, Any]) -> None:
    """arq task entry-point. Wired in `app/workers/retention_worker.py:WorkerSettings`."""
    del ctx  # arq context isn't needed; we open our own session
    init_engine()
    try:
        await run_retention_cleanup()
    except Exception as exc:  # noqa: BLE001 — worker failure must log + re-raise
        logger.error(
            "worker.retention.failed",
            code="RETENTION_CLEANUP_FAILED",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        raise


__all__ = ["retention_cleanup_task", "run_retention_cleanup"]
