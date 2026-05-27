"""RawSensitiveLog repository — `raw_sensitive_logs` table (db-schema.md).

Writes happen inside the request transaction (encrypted blob from SensitiveLogCipher).
The retention worker calls `delete_expired` running as `app_admin` (BYPASSRLS) so it can
sweep every tenant's expired rows in one pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import ulid
from sqlalchemy import text

from app.domain.repositories._base import AsyncSession, assert_tenant
from app.domain.services.encryption_service import EncryptedBlob


@dataclass(frozen=True)
class RawSensitiveLogRow:
    log_id: str
    tenant_id: str
    user_id: str
    run_id: str | None
    ciphertext: bytes
    nonce: bytes
    key_version: str
    expires_at: datetime
    created_at: datetime


def _row_to_obj(row: Any) -> RawSensitiveLogRow:
    return RawSensitiveLogRow(
        log_id=row["log_id"],
        tenant_id=row["tenant_id"],
        user_id=row["user_id"],
        run_id=row.get("run_id"),
        ciphertext=bytes(row["ciphertext"]),
        nonce=bytes(row["nonce"]),
        key_version=row["key_version"],
        expires_at=row["expires_at"],
        created_at=row["created_at"],
    )


class RawSensitiveLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(
        self,
        *,
        tenant_id: str,
        user_id: str,
        run_id: str | None,
        blob: EncryptedBlob,
        retention_days: int,
        now: datetime | None = None,
    ) -> str:
        assert_tenant(tenant_id)
        log_id = f"rsl_{ulid.new()!s}"
        when = now or datetime.now(UTC)
        expires_at = when + timedelta(days=retention_days)
        await self._session.execute(
            text(
                """
                INSERT INTO raw_sensitive_logs (
                    log_id, tenant_id, user_id, run_id, ciphertext, key_version, nonce,
                    expires_at, created_at
                ) VALUES (
                    :log_id, :tenant_id, :user_id, :run_id, :ciphertext, :key_version,
                    :nonce, :expires_at, :created_at
                )
                """
            ),
            {
                "log_id": log_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "run_id": run_id,
                "ciphertext": blob.ciphertext,
                "key_version": blob.key_version,
                "nonce": blob.nonce,
                "expires_at": expires_at,
                "created_at": when,
            },
        )
        return log_id

    async def get_for_admin(
        self, *, tenant_id: str, log_id: str
    ) -> RawSensitiveLogRow | None:
        """Tenant-scoped fetch for the admin-only raw-sensitive view UX.

        Callers must additionally write an `audit_entries` row recording the access.
        """
        assert_tenant(tenant_id)
        result = await self._session.execute(
            text(
                "SELECT * FROM raw_sensitive_logs "
                "WHERE tenant_id = :tenant_id AND log_id = :log_id"
            ),
            {"tenant_id": tenant_id, "log_id": log_id},
        )
        row = result.mappings().one_or_none()
        return _row_to_obj(row) if row else None

    async def delete_expired(self, *, now: datetime | None = None) -> int:
        """Retention worker entry-point. Deletes every expired row across tenants.

        MUST run under the `app_admin` role (BYPASSRLS); the GUC `app.current_tenant_id`
        is NOT set on the retention worker's connection.
        """
        cutoff = now or datetime.now(UTC)
        result = await self._session.execute(
            text("DELETE FROM raw_sensitive_logs WHERE expires_at < :cutoff"),
            {"cutoff": cutoff},
        )
        return int(getattr(result, "rowcount", 0) or 0)


__all__ = ["RawSensitiveLogRepository", "RawSensitiveLogRow"]
