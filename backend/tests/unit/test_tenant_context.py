"""set_tenant_guc input validation."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from app.core.tenant_context import set_tenant_guc


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tenant_id", ["tn_test", "tn_01HZX7", "tenant-abc_123", "abc"]
)
async def test_accepts_valid_tenant_ids(tenant_id: str) -> None:
    session = AsyncMock()
    await set_tenant_guc(session, tenant_id)
    session.execute.assert_awaited_once()
    sql = str(session.execute.await_args.args[0])
    assert tenant_id in sql
    assert sql.startswith("SET LOCAL app.current_tenant_id =")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad",
    [
        "",
        "tn'inject",
        'tn"inject',
        "tn\\inject",
        "tn;DROP TABLE tenants",
        "tn with space",
        "tn\nnewline",
    ],
)
async def test_rejects_invalid_tenant_ids(bad: str) -> None:
    session = AsyncMock()
    with pytest.raises(ValueError):
        await set_tenant_guc(session, bad)
    session.execute.assert_not_called()
