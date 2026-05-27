"""Per-request tenant context for Postgres RLS (ADR-0016).

The `tenant_isolation_policy` on every multi-tenant table reads
`current_setting('app.current_tenant_id', true)`. We set it via `SET LOCAL` inside the
request transaction so the GUC is scoped to that transaction only — a connection returned
to the pool never leaks a previous tenant's id.

Callers must run this inside an already-open transaction (`session.begin()` /
`session_scope()`). `SET LOCAL` outside a transaction is a no-op and silently fails
closed (every read returns zero rows).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_TENANT_ID_RE_CHARS = "_-"


def _validate_tenant_id(tenant_id: str) -> str:
    """Tenant IDs are application-controlled identifiers (ULID-prefixed strings).

    Reject anything that contains a quote or backslash so we never end up interpolating an
    attacker-controlled value into a `SET LOCAL` statement. Bind-parameters don't work for
    `SET LOCAL` in Postgres, so quoting is our defence.
    """
    if not tenant_id:
        raise ValueError("tenant_id required")
    for ch in tenant_id:
        if ch.isalnum() or ch in _TENANT_ID_RE_CHARS:
            continue
        raise ValueError(f"tenant_id contains invalid character: {ch!r}")
    return tenant_id


async def set_tenant_guc(session: AsyncSession, tenant_id: str) -> None:
    """Apply `SET LOCAL app.current_tenant_id = <tenant_id>` inside the current txn."""
    safe = _validate_tenant_id(tenant_id)
    await session.execute(text(f"SET LOCAL app.current_tenant_id = '{safe}'"))


__all__ = ["set_tenant_guc"]
