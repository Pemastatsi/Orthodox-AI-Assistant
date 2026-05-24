"""Source repository — owns `sources` table writes.

Every method requires `tenant_id`. Insert computes `source_hash` from the raw file bytes
(`sha256:<hex>`) per `approved-decisions-register.md` row J. Duplicate inserts (same
`(tenant_id, source_hash)`) raise `SourceDuplicateError`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import ulid
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.domain.models.source import Source
from app.domain.repositories._base import AsyncSession, assert_tenant


def compute_source_hash(file_bytes: bytes) -> str:
    """`sha256:<lower-hex>` per approved-decisions-register.md row J."""
    return "sha256:" + hashlib.sha256(file_bytes).hexdigest()


class SourceRepositoryError(Exception):
    """Base for repository-layer errors that map to HTTP 4xx / domain errors."""


class SourceDuplicateError(SourceRepositoryError):
    """Same `(tenant_id, source_hash)` already exists."""


class SourceNotFoundError(SourceRepositoryError):
    pass


@dataclass(frozen=True)
class CreateSourceParams:
    tenant_id: str
    title: str
    source_type: str
    extraction_method: str
    corpus_version: str
    source_hash: str
    father: str | None = None
    work: str | None = None
    language: str = "en"
    corpus_origin: str | None = None
    digitization_provenance: str | None = None
    metadata: dict[str, Any] | None = None


def _row_to_source(row: Any) -> Source:
    return Source(
        source_id=row.source_id,
        tenant_id=row.tenant_id,
        title=row.title,
        source_type=row.source_type,
        source_hash=row.source_hash,
        extraction_method=row.extraction_method,
        approved=row.approved,
        corpus_version=row.corpus_version,
        created_at=row.created_at,
        father=row.father,
        work=row.work,
        language=row.language,
        corpus_origin=row.corpus_origin,
        digitization_provenance=row.digitization_provenance,
        approval_note=row.approval_note,
        approved_by=row.approved_by,
        approved_at=row.approved_at,
        metadata=row.metadata or {},
    )


class SourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, params: CreateSourceParams) -> Source:
        assert_tenant(params.tenant_id)
        source_id = f"src_{ulid.new()!s}"
        try:
            result = await self._session.execute(
                text(
                    """
                    INSERT INTO sources (
                        source_id, tenant_id, title, father, work, language, source_type,
                        source_hash, extraction_method, corpus_origin, digitization_provenance,
                        approved, corpus_version, metadata, created_at
                    ) VALUES (
                        :source_id, :tenant_id, :title, :father, :work, :language, :source_type,
                        :source_hash, :extraction_method, :corpus_origin, :digitization_provenance,
                        false, :corpus_version, CAST(:metadata AS jsonb), now()
                    )
                    RETURNING *
                    """
                ),
                {
                    "source_id": source_id,
                    "tenant_id": params.tenant_id,
                    "title": params.title,
                    "father": params.father,
                    "work": params.work,
                    "language": params.language,
                    "source_type": params.source_type,
                    "source_hash": params.source_hash,
                    "extraction_method": params.extraction_method,
                    "corpus_origin": params.corpus_origin,
                    "digitization_provenance": params.digitization_provenance,
                    "corpus_version": params.corpus_version,
                    "metadata": _jsonb(params.metadata or {}),
                },
            )
        except IntegrityError as exc:
            if _is_unique_violation(exc):
                raise SourceDuplicateError(
                    f"source already ingested for tenant {params.tenant_id}"
                ) from exc
            raise

        row = result.mappings().one()
        return _row_to_source(_RowView(row))

    async def get(self, *, tenant_id: str, source_id: str) -> Source | None:
        assert_tenant(tenant_id)
        result = await self._session.execute(
            text(
                "SELECT * FROM sources "
                "WHERE tenant_id = :tenant_id AND source_id = :source_id"
            ),
            {"tenant_id": tenant_id, "source_id": source_id},
        )
        row = result.mappings().one_or_none()
        return _row_to_source(_RowView(row)) if row else None

    async def get_by_hash(self, *, tenant_id: str, source_hash: str) -> Source | None:
        assert_tenant(tenant_id)
        result = await self._session.execute(
            text(
                "SELECT * FROM sources "
                "WHERE tenant_id = :tenant_id AND source_hash = :source_hash"
            ),
            {"tenant_id": tenant_id, "source_hash": source_hash},
        )
        row = result.mappings().one_or_none()
        return _row_to_source(_RowView(row)) if row else None

    async def mark_approved(
        self,
        *,
        tenant_id: str,
        source_id: str,
        approved_by_user_id: str,
        approval_note: str | None,
        approved_at: datetime | None = None,
    ) -> Source:
        """Set `approved=true`. Used by the cascade in `chunk_repository.mark_approved`."""
        assert_tenant(tenant_id)
        when = approved_at or datetime.now(UTC)
        result = await self._session.execute(
            text(
                """
                UPDATE sources SET
                    approved = true,
                    approved_by = :approved_by,
                    approved_at = :approved_at,
                    approval_note = COALESCE(approval_note, :approval_note)
                WHERE tenant_id = :tenant_id AND source_id = :source_id
                RETURNING *
                """
            ),
            {
                "tenant_id": tenant_id,
                "source_id": source_id,
                "approved_by": approved_by_user_id,
                "approved_at": when,
                "approval_note": approval_note,
            },
        )
        row = result.mappings().one_or_none()
        if not row:
            raise SourceNotFoundError(source_id)
        return _row_to_source(_RowView(row))


# -- helpers ----------------------------------------------------------------

def _is_unique_violation(exc: IntegrityError) -> bool:
    # asyncpg raises UniqueViolationError; psycopg2 sets sqlstate '23505'. Treat the SQLSTATE as
    # the source of truth.
    orig = getattr(exc, "orig", None)
    sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    return sqlstate == "23505"


def _jsonb(value: Any) -> str:
    import json
    return json.dumps(value, default=str)


class _RowView:
    """Adapter so `_row_to_source` can access fields via attribute syntax regardless of source."""

    def __init__(self, mapping: Any) -> None:
        self._m = mapping

    def __getattr__(self, name: str) -> Any:
        try:
            return self._m[name]
        except (KeyError, TypeError) as exc:
            raise AttributeError(name) from exc


__all__ = [
    "CreateSourceParams",
    "SourceDuplicateError",
    "SourceNotFoundError",
    "SourceRepository",
    "SourceRepositoryError",
    "compute_source_hash",
]
