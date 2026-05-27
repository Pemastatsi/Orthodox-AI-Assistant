"""arq WorkerSettings for the retention worker.

Schedules `retention_cleanup_task` on the cron expression from
`settings.retention_worker_cron` (default `5 * * * *` — minute 5 of every hour).

Run with:
    arq app.workers.retention_worker.WorkerSettings

The retention worker connects under the `DATABASE_ADMIN_URL` (falling back to
`DATABASE_URL`) so that — when RLS is provisioned and `app_admin` exists — it sweeps
expired rows across every tenant without needing a per-tenant GUC.
"""

from __future__ import annotations

from typing import Any

from arq.cron import cron

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.domain.repositories._base import init_engine
from app.workers.tasks.retention_cleanup import retention_cleanup_task


def _parse_cron(expr: str) -> dict[str, Any]:
    """Parse a 5-field cron expression into the kwargs `arq.cron.cron` expects.

    Phase-1 only supports the trivial `M * * * *` form (any minute, every hour, every day).
    More expressive cron syntax is deferred to Phase 2 alongside `croniter` adoption.
    """
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError(f"unsupported cron expression: {expr!r}")
    minute_field = fields[0]
    if not minute_field.isdigit():
        raise ValueError(f"unsupported cron minute field: {minute_field!r}")
    return {"minute": {int(minute_field)}}


class WorkerSettings:
    cron_jobs = [cron(retention_cleanup_task, **_parse_cron(get_settings().retention_worker_cron))]
    redis_settings: Any = None  # populated by arq from settings.redis_url at runtime

    @staticmethod
    async def on_startup(ctx: dict[str, Any]) -> None:
        del ctx
        configure_logging()
        init_engine()


__all__ = ["WorkerSettings"]
