"""FlaggedQuery repository — `flagged_queries` table (db-schema.md).

A flagged_queries row carries the redacted query text and optional FK pointer to a
raw_sensitive_logs row holding the encrypted plaintext.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import ulid
from sqlalchemy import text

from app.domain.models.flagged_query import FlaggedQuery
from app.domain.repositories._base import AsyncSession, assert_tenant


def _row_to_flagged(row: Any) -> FlaggedQuery:
    return FlaggedQuery(
        flagged_query_id=row["flagged_query_id"],
        tenant_id=row["tenant_id"],
        user_id=row["user_id"],
        run_id=row.get("run_id"),
        query_text_redacted=row["query_text_redacted"],
        raw_sensitive_log_id=row.get("raw_sensitive_log_id"),
        flag_reason=row["flag_reason"],
        sensitivity_primary=row.get("sensitivity_primary"),
        risk_flags=list(row.get("risk_flags", [])),
        embedding=list(row["embedding"]) if row.get("embedding") is not None else None,
        embedding_model=row.get("embedding_model"),
        cluster_id=row.get("cluster_id"),
        created_at=row["created_at"],
    )


class FlaggedQueryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(
        self,
        *,
        tenant_id: str,
        user_id: str,
        query_text_redacted: str,
        flag_reason: str,
        run_id: str | None = None,
        raw_sensitive_log_id: str | None = None,
        sensitivity_primary: str | None = None,
        risk_flags: list[str] | None = None,
    ) -> str:
        assert_tenant(tenant_id)
        flagged_query_id = f"flq_{ulid.new()!s}"
        await self._session.execute(
            text(
                """
                INSERT INTO flagged_queries (
                    flagged_query_id, tenant_id, user_id, run_id, query_text_redacted,
                    raw_sensitive_log_id, flag_reason, sensitivity_primary, risk_flags,
                    created_at
                ) VALUES (
                    :flagged_query_id, :tenant_id, :user_id, :run_id, :query_text_redacted,
                    :raw_sensitive_log_id, :flag_reason, :sensitivity_primary, :risk_flags,
                    :created_at
                )
                """
            ),
            {
                "flagged_query_id": flagged_query_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "run_id": run_id,
                "query_text_redacted": query_text_redacted,
                "raw_sensitive_log_id": raw_sensitive_log_id,
                "flag_reason": flag_reason,
                "sensitivity_primary": sensitivity_primary,
                "risk_flags": risk_flags or [],
                "created_at": datetime.now(UTC),
            },
        )
        return flagged_query_id

    async def get(self, *, tenant_id: str, flagged_query_id: str) -> FlaggedQuery | None:
        assert_tenant(tenant_id)
        result = await self._session.execute(
            text(
                "SELECT * FROM flagged_queries "
                "WHERE tenant_id = :tenant_id AND flagged_query_id = :flagged_query_id"
            ),
            {"tenant_id": tenant_id, "flagged_query_id": flagged_query_id},
        )
        row = result.mappings().one_or_none()
        return _row_to_flagged(row) if row else None

    async def list_by_tenant(
        self,
        *,
        tenant_id: str,
        cursor: str | None = None,
        limit: int = 25,
        flag_reason: str | None = None,
    ) -> tuple[list[FlaggedQuery], str | None]:
        """Keyset pagination by `flagged_query_id DESC` (ULIDs are time-sortable).
        Returns up to `limit` rows + nextCursor when more remain."""
        assert_tenant(tenant_id)
        clauses = ["tenant_id = :tenant_id"]
        params: dict[str, Any] = {"tenant_id": tenant_id, "limit": limit + 1}
        if cursor:
            clauses.append("flagged_query_id < :cursor")
            params["cursor"] = cursor
        if flag_reason is not None:
            clauses.append("flag_reason = :flag_reason")
            params["flag_reason"] = flag_reason
        sql = (
            "SELECT * FROM flagged_queries WHERE "
            + " AND ".join(clauses)
            + " ORDER BY flagged_query_id DESC LIMIT :limit"
        )
        result = await self._session.execute(text(sql), params)
        rows = list(result.mappings().all())
        items = [_row_to_flagged(r) for r in rows[:limit]]
        next_cursor = (
            rows[limit - 1]["flagged_query_id"] if len(rows) > limit else None
        )
        return items, next_cursor


__all__ = ["FlaggedQueryRepository"]
