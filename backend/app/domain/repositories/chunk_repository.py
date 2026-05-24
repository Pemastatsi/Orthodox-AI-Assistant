"""Chunk repository — owns `chunks` table writes.

Approving a chunk on an unapproved parent source MUST auto-approve the parent source in the same
transaction (db-schema.md cross-table invariant #3). The cascade copies `approved_by` /
`approved_at` to `sources` and writes an auto-approval note. Listing is tenant-scoped.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import ulid
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.domain.models.chunk import Chunk
from app.domain.repositories._base import AsyncSession, assert_tenant
from app.domain.repositories.source_repository import SourceRepository


def compute_chunk_hash(*, source_hash: str, text_value: str, section_path: list[str]) -> str:
    """Deterministic chunk hash. Same `(source_hash, text, section_path)` always hashes the same."""
    h = hashlib.sha256()
    h.update(source_hash.encode("utf-8"))
    h.update(b"\x1f")
    h.update("/".join(section_path).encode("utf-8"))
    h.update(b"\x1f")
    h.update(text_value.encode("utf-8"))
    return "sha256:" + h.hexdigest()


class ChunkRepositoryError(Exception):
    pass


class ChunkNotFoundError(ChunkRepositoryError):
    pass


class ChunkDuplicateError(ChunkRepositoryError):
    pass


@dataclass(frozen=True)
class ChunkInsert:
    tenant_id: str
    source_id: str
    text: str
    chunk_hash: str
    embedding_model: str
    embedding_dimension: int
    corpus_version: str
    section_path: list[str]
    page_start: int | None = None
    page_end: int | None = None
    parent_chunk_id: str | None = None
    father: str | None = None
    work: str | None = None
    page: str | None = None
    language: str = "en"
    visibility: str = "admin_only"
    categories: list[str] | None = None


def _row_to_chunk(row: Any) -> Chunk:
    return Chunk(
        chunk_id=row["chunk_id"],
        source_id=row["source_id"],
        tenant_id=row["tenant_id"],
        text=row["text"],
        chunk_hash=row["chunk_hash"],
        approved=row["approved"],
        visibility=row["visibility"],
        father=row.get("father"),
        work=row.get("work"),
        page=row.get("page"),
        timestamp=row.get("timestamp"),
        language=row.get("language", "en"),
        categories=list(row.get("categories", [])),
        section_path=list(row.get("section_path", [])),
        page_start=row.get("page_start"),
        page_end=row.get("page_end"),
        parent_chunk_id=row.get("parent_chunk_id"),
        embedding_model=row["embedding_model"],
        embedding_dimension=row["embedding_dimension"],
        corpus_version=row["corpus_version"],
        review_note=row.get("review_note"),
        created_at=row["created_at"],
    )


class ChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_insert(self, *, chunks: list[ChunkInsert]) -> list[str]:
        """Insert many chunks for a single tenant. Returns the assigned chunk_ids."""
        if not chunks:
            return []
        tenant_id = chunks[0].tenant_id
        assert_tenant(tenant_id)
        if any(c.tenant_id != tenant_id for c in chunks):
            raise ValueError("mixed-tenant chunk batch")

        chunk_ids: list[str] = []
        for c in chunks:
            chunk_id = f"chk_{ulid.new()!s}"
            chunk_ids.append(chunk_id)
            try:
                await self._session.execute(
                    text(
                        """
                        INSERT INTO chunks (
                            chunk_id, source_id, tenant_id, text, chunk_hash, approved,
                            visibility, father, work, page, language, categories, section_path,
                            page_start, page_end, parent_chunk_id, embedding_model,
                            embedding_dimension, corpus_version, created_at
                        ) VALUES (
                            :chunk_id, :source_id, :tenant_id, :text, :chunk_hash, false,
                            :visibility, :father, :work, :page, :language, :categories,
                            :section_path, :page_start, :page_end, :parent_chunk_id,
                            :embedding_model, :embedding_dimension, :corpus_version, now()
                        )
                        """
                    ),
                    {
                        "chunk_id": chunk_id,
                        "source_id": c.source_id,
                        "tenant_id": c.tenant_id,
                        "text": c.text,
                        "chunk_hash": c.chunk_hash,
                        "visibility": c.visibility,
                        "father": c.father,
                        "work": c.work,
                        "page": c.page,
                        "language": c.language,
                        "categories": c.categories or [],
                        "section_path": c.section_path,
                        "page_start": c.page_start,
                        "page_end": c.page_end,
                        "parent_chunk_id": c.parent_chunk_id,
                        "embedding_model": c.embedding_model,
                        "embedding_dimension": c.embedding_dimension,
                        "corpus_version": c.corpus_version,
                    },
                )
            except IntegrityError as exc:
                if _is_unique_violation(exc):
                    raise ChunkDuplicateError(
                        f"chunk_hash collision: {c.chunk_hash}"
                    ) from exc
                raise
        return chunk_ids

    async def get(self, *, tenant_id: str, chunk_id: str) -> Chunk | None:
        assert_tenant(tenant_id)
        result = await self._session.execute(
            text(
                "SELECT * FROM chunks "
                "WHERE tenant_id = :tenant_id AND chunk_id = :chunk_id"
            ),
            {"tenant_id": tenant_id, "chunk_id": chunk_id},
        )
        row = result.mappings().one_or_none()
        return _row_to_chunk(row) if row else None

    async def list_by_tenant(
        self,
        *,
        tenant_id: str,
        approved: bool | None = None,
        visibility: str | None = None,
        source_id: str | None = None,
        cursor: str | None = None,
        limit: int = 25,
    ) -> tuple[list[Chunk], str | None]:
        """Paginated by `chunk_id` (ULID, sortable). Returns `(items, next_cursor)`."""
        assert_tenant(tenant_id)
        limit = max(1, min(100, limit))
        params: dict[str, Any] = {"tenant_id": tenant_id, "limit": limit + 1}
        clauses = ["tenant_id = :tenant_id"]
        if approved is not None:
            clauses.append("approved = :approved")
            params["approved"] = approved
        if visibility is not None:
            clauses.append("visibility = :visibility")
            params["visibility"] = visibility
        if source_id is not None:
            clauses.append("source_id = :source_id")
            params["source_id"] = source_id
        if cursor:
            clauses.append("chunk_id > :cursor")
            params["cursor"] = cursor
        sql = (
            "SELECT * FROM chunks WHERE "
            + " AND ".join(clauses)
            + " ORDER BY chunk_id ASC LIMIT :limit"
        )
        result = await self._session.execute(text(sql), params)
        rows = list(result.mappings().all())
        items = [_row_to_chunk(r) for r in rows[:limit]]
        next_cursor = rows[limit - 1]["chunk_id"] if len(rows) > limit else None
        return items, next_cursor

    async def mark_approved(
        self,
        *,
        tenant_id: str,
        chunk_id: str,
        approved_by_user_id: str,
        approval_note: str | None,
    ) -> Chunk:
        """Approve a chunk; cascade-approves the parent source per invariant #3."""
        assert_tenant(tenant_id)
        chunk = await self.get(tenant_id=tenant_id, chunk_id=chunk_id)
        if not chunk:
            raise ChunkNotFoundError(chunk_id)

        when = datetime.now(UTC)

        source_repo = SourceRepository(self._session)
        parent = await source_repo.get(tenant_id=tenant_id, source_id=chunk.source_id)
        if parent is None:
            raise ChunkRepositoryError(
                f"parent source missing for chunk {chunk_id} (data integrity)"
            )
        if not parent.approved:
            await source_repo.mark_approved(
                tenant_id=tenant_id,
                source_id=chunk.source_id,
                approved_by_user_id=approved_by_user_id,
                approval_note="auto-approved via first-chunk approval",
                approved_at=when,
            )

        result = await self._session.execute(
            text(
                """
                UPDATE chunks SET
                    approved = true,
                    review_note = COALESCE(:review_note, review_note)
                WHERE tenant_id = :tenant_id AND chunk_id = :chunk_id
                RETURNING *
                """
            ),
            {
                "tenant_id": tenant_id,
                "chunk_id": chunk_id,
                "review_note": approval_note,
            },
        )
        row = result.mappings().one_or_none()
        if not row:
            raise ChunkNotFoundError(chunk_id)
        return _row_to_chunk(row)

    async def set_visibility(
        self,
        *,
        tenant_id: str,
        chunk_id: str,
        visibility: str,
        review_note: str | None = None,
    ) -> Chunk:
        assert_tenant(tenant_id)
        result = await self._session.execute(
            text(
                """
                UPDATE chunks SET
                    visibility = :visibility,
                    review_note = COALESCE(:review_note, review_note)
                WHERE tenant_id = :tenant_id AND chunk_id = :chunk_id
                RETURNING *
                """
            ),
            {
                "tenant_id": tenant_id,
                "chunk_id": chunk_id,
                "visibility": visibility,
                "review_note": review_note,
            },
        )
        row = result.mappings().one_or_none()
        if not row:
            raise ChunkNotFoundError(chunk_id)
        return _row_to_chunk(row)


def _is_unique_violation(exc: IntegrityError) -> bool:
    orig = getattr(exc, "orig", None)
    sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    return sqlstate == "23505"


__all__ = [
    "ChunkDuplicateError",
    "ChunkInsert",
    "ChunkNotFoundError",
    "ChunkRepository",
    "ChunkRepositoryError",
    "compute_chunk_hash",
]
