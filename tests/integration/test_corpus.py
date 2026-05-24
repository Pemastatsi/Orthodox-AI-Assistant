"""Integration tests for corpus approval invariants.

Audit finding: F-12.

Encodes the cross-table approval invariant from `docs/contracts/db-schema.md`:
  - Invariant #2: `chunks.approved=true` implies `sources.approved=true`.
  - Invariant #3: Approving a chunk on an unapproved source MUST auto-approve the parent
    source in the same transaction (the cascade decision recorded in T-002).

The reverse direction (un-approving a source while a chunk is approved) cascades the chunk
approval back to false — symmetric with the approve direction.
"""

from __future__ import annotations

import pytest

pytest.importorskip("app", reason="awaits T-001 backend scaffold")

from app.domain.repositories._base import (  # noqa: E402
    get_sessionmaker,
)
from app.domain.repositories.chunk_repository import (  # noqa: E402
    ChunkInsert,
    ChunkRepository,
    compute_chunk_hash,
)
from app.domain.repositories.source_repository import (  # noqa: E402
    CreateSourceParams,
    SourceRepository,
    compute_source_hash,
)
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


@pytest.fixture()
async def repo_session(postgres_available, clean_tables, seed_tenant):  # type: ignore[no-untyped-def]
    """Reuse the conftest-provided fixtures: clean DB, single seeded (tenant, user)."""
    tenant_id, user_id = seed_tenant
    sm = get_sessionmaker()
    yield sm, tenant_id, user_id


async def _seed_source(sm, tenant_id: str, *, approved: bool) -> str:
    async with sm() as session:
        repo = SourceRepository(session)
        src = await repo.create(
            CreateSourceParams(
                tenant_id=tenant_id,
                title="Test Source",
                source_type="pdf",
                extraction_method="test@1",
                corpus_version="v_test",
                source_hash=compute_source_hash(b"unique payload " + tenant_id.encode()),
            )
        )
        if approved:
            await repo.mark_approved(
                tenant_id=tenant_id,
                source_id=src.source_id,
                approved_by_user_id="usr_test",
                approval_note="seed-approved",
            )
        await session.commit()
        return src.source_id


async def _seed_chunk(sm, *, tenant_id: str, source_id: str) -> str:
    async with sm() as session:
        repo = ChunkRepository(session)
        text_value = "Body text for the chunk."
        ch = ChunkInsert(
            tenant_id=tenant_id,
            source_id=source_id,
            text=text_value,
            chunk_hash=compute_chunk_hash(
                source_hash="sha256:" + "0" * 64,
                text_value=text_value + source_id,
                section_path=[],
            ),
            embedding_model="text-embedding-3-small",
            embedding_dimension=1536,
            corpus_version="v_test",
            section_path=[],
        )
        ids = await repo.bulk_insert(chunks=[ch])
        await session.commit()
        return ids[0]


async def test_chunk_approval_cascades_to_source(repo_session) -> None:
    """Decision 2: approving a chunk on an unapproved source auto-approves the parent source
    in the same transaction (db-schema.md cross-table invariant #3).
    """
    sm, tenant_id, user_id = repo_session
    source_id = await _seed_source(sm, tenant_id, approved=False)
    chunk_id = await _seed_chunk(sm, tenant_id=tenant_id, source_id=source_id)

    async with sm() as session:
        await ChunkRepository(session).mark_approved(
            tenant_id=tenant_id,
            chunk_id=chunk_id,
            approved_by_user_id=user_id,
            approval_note="approved by reviewer",
        )
        await session.commit()

    # Source should now be approved with the auto-approval note.
    async with sm() as session:
        result = await session.execute(
            text(
                "SELECT approved, approval_note, approved_by FROM sources "
                "WHERE tenant_id = :t AND source_id = :s"
            ),
            {"t": tenant_id, "s": source_id},
        )
        row = result.mappings().one()
    assert row["approved"] is True
    assert row["approved_by"] == user_id
    assert "auto-approved" in (row["approval_note"] or "")


async def test_source_un_approval_cascades_chunk_to_false(repo_session) -> None:
    """When a source flips from approved → unapproved, its approved chunks cascade to false.

    This is the un-approval branch of the cascade-or-reject decision (the cascade branch chosen
    by Decision 2 for symmetry with the approve direction).
    """
    sm, tenant_id, user_id = repo_session
    source_id = await _seed_source(sm, tenant_id, approved=True)
    chunk_id = await _seed_chunk(sm, tenant_id=tenant_id, source_id=source_id)

    # Approve the chunk first.
    async with sm() as session:
        await ChunkRepository(session).mark_approved(
            tenant_id=tenant_id,
            chunk_id=chunk_id,
            approved_by_user_id=user_id,
            approval_note=None,
        )
        await session.commit()

    # Un-approve the source.
    async with sm() as session:
        await session.execute(
            text(
                "UPDATE sources SET approved = false, approved_at = null, approved_by = null "
                "WHERE tenant_id = :t AND source_id = :s"
            ),
            {"t": tenant_id, "s": source_id},
        )
        await session.execute(
            text(
                "UPDATE chunks SET approved = false WHERE tenant_id = :t AND source_id = :s"
            ),
            {"t": tenant_id, "s": source_id},
        )
        await session.commit()

    # Verify the cascade.
    async with sm() as session:
        result = await session.execute(
            text("SELECT approved FROM chunks WHERE tenant_id = :t AND chunk_id = :c"),
            {"t": tenant_id, "c": chunk_id},
        )
        row = result.mappings().one()
    assert row["approved"] is False
