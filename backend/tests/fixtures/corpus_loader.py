"""Load `tests/fixtures/corpus/tiny_*_corpus.json` into Postgres and (optionally) Qdrant.

The fixture JSONs predate T-002 and contain pre-chunked content — no parsing or chunking is run.
This loader is the canonical way for integration tests to populate tenant data without
exercising the ingestion pipeline.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.adapters.vector_store.base import ChunkPayload, SparseVector, VectorStore
from app.domain.repositories._base import get_sessionmaker
from sqlalchemy import text

_REPO_ROOT = Path(__file__).resolve().parents[3]
TINY_APPROVED = _REPO_ROOT / "tests" / "fixtures" / "corpus" / "tiny_approved_corpus.json"
TINY_OTHER = _REPO_ROOT / "tests" / "fixtures" / "corpus" / "tiny_other_tenant_corpus.json"


@dataclass(frozen=True)
class LoadedTenant:
    tenant_id: str
    corpus_version: str
    source_ids: list[str]
    chunk_ids: list[str]
    chunk_hashes: list[str]


def _deterministic_embedding(seed: str, dim: int) -> list[float]:
    h = hashlib.sha256(seed.encode("utf-8")).digest()
    # Repeat the digest to fill the vector; normalize roughly to unit length.
    raw = (h * ((dim // len(h)) + 1))[:dim]
    return [(b - 128) / 128.0 for b in raw]


def _deterministic_sparse(seed: str) -> SparseVector:
    h = hashlib.sha256(seed.encode("utf-8")).digest()
    indices = [int(h[i]) * 256 + int(h[i + 1]) for i in range(0, len(h) - 1, 2)]
    values = [float((b + 1) / 256.0) for b in h[: len(indices)]]
    return SparseVector(indices=indices, values=values)


async def _ensure_tenant_user(*, tenant_id: str, user_id: str) -> None:
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(
            text(
                "INSERT INTO tenants (tenant_id, name, clerk_org_id, status, data_region) "
                "VALUES (:t, :name, :org, 'active', 'us') "
                "ON CONFLICT (tenant_id) DO NOTHING"
            ),
            {"t": tenant_id, "name": tenant_id, "org": f"clerk_{tenant_id}"},
        )
        await session.execute(
            text(
                "INSERT INTO users (user_id, clerk_user_id, tenant_id, role, status) "
                "VALUES (:u, :ck, :t, 'content_manager', 'active') "
                "ON CONFLICT (user_id) DO NOTHING"
            ),
            {"u": user_id, "ck": f"clerk_{user_id}", "t": tenant_id},
        )
        await session.commit()


async def load_corpus_fixture(
    *,
    fixture_path: Path,
    vector_store: VectorStore | None = None,
    embedding_model: str = "text-embedding-3-small",
    embedding_dimension: int = 1536,
) -> LoadedTenant:
    data: dict[str, Any] = json.loads(fixture_path.read_text())
    tenant_id: str = data["tenantId"]
    corpus_version: str = data["corpusVersion"]
    user_id = f"usr_fix_{tenant_id}"

    await _ensure_tenant_user(tenant_id=tenant_id, user_id=user_id)

    source_ids: list[str] = []
    chunk_ids: list[str] = []
    chunk_hashes: list[str] = []
    payloads: list[ChunkPayload] = []

    sm = get_sessionmaker()
    async with sm() as session:
        for src in data["sources"]:
            await session.execute(
                text(
                    """
                    INSERT INTO sources (
                        source_id, tenant_id, title, father, work, language, source_type,
                        source_hash, extraction_method, approved, corpus_version, created_at
                    ) VALUES (
                        :sid, :tid, :title, :father, :work, :language, 'txt',
                        :sh, :em, :approved, :cv, now()
                    )
                    ON CONFLICT (source_id) DO NOTHING
                    """
                ),
                {
                    "sid": src["sourceId"],
                    "tid": tenant_id,
                    "title": src["title"],
                    "father": src.get("father"),
                    "work": src.get("work"),
                    "language": src.get("language", "en"),
                    "sh": src["sourceHash"],
                    "em": src["extractionMethod"],
                    "approved": src["approved"],
                    "cv": corpus_version,
                },
            )
            source_ids.append(src["sourceId"])

            for chunk in src["chunks"]:
                await session.execute(
                    text(
                        """
                        INSERT INTO chunks (
                            chunk_id, source_id, tenant_id, text, chunk_hash,
                            approved, visibility, father, work, page, language,
                            embedding_model, embedding_dimension, corpus_version, created_at
                        ) VALUES (
                            :cid, :sid, :tid, :text, :ch, :approved, :vis, :father, :work,
                            :page, :language, :em, :ed, :cv, now()
                        )
                        ON CONFLICT (chunk_id) DO NOTHING
                        """
                    ),
                    {
                        "cid": chunk["chunkId"],
                        "sid": src["sourceId"],
                        "tid": tenant_id,
                        "text": chunk["text"],
                        "ch": chunk["chunkHash"],
                        "approved": chunk["approved"],
                        "vis": chunk.get("visibility", "member"),
                        "father": chunk.get("father"),
                        "work": chunk.get("work"),
                        "page": chunk.get("page"),
                        "language": chunk.get("language", "en"),
                        "em": embedding_model,
                        "ed": embedding_dimension,
                        "cv": corpus_version,
                    },
                )
                chunk_ids.append(chunk["chunkId"])
                chunk_hashes.append(chunk["chunkHash"])

                if vector_store is not None:
                    seed = f"{tenant_id}|{chunk['chunkId']}|{chunk['text']}"
                    payloads.append(
                        ChunkPayload(
                            chunk_id=chunk["chunkId"],
                            tenant_id=tenant_id,
                            source_id=src["sourceId"],
                            source_hash=src["sourceHash"],
                            chunk_hash=chunk["chunkHash"],
                            text=chunk["text"],
                            section_path=[],
                            page_start=None,
                            page_end=None,
                            parent_chunk_id=None,
                            approved=chunk["approved"],
                            visibility=chunk.get("visibility", "member"),
                            embedding_model=embedding_model,
                            embedding_dimension=embedding_dimension,
                            corpus_version=corpus_version,
                            embedding=_deterministic_embedding(seed, embedding_dimension),
                            sparse_embedding=_deterministic_sparse(seed),
                        )
                    )
        await session.commit()

    if vector_store is not None and payloads:
        await vector_store.upsert(payloads=payloads)

    return LoadedTenant(
        tenant_id=tenant_id,
        corpus_version=corpus_version,
        source_ids=source_ids,
        chunk_ids=chunk_ids,
        chunk_hashes=chunk_hashes,
    )


async def load_both_tenants(vector_store: VectorStore | None = None) -> tuple[LoadedTenant, LoadedTenant]:  # noqa: E501
    primary = await load_corpus_fixture(fixture_path=TINY_APPROVED, vector_store=vector_store)
    secondary = await load_corpus_fixture(fixture_path=TINY_OTHER, vector_store=vector_store)
    return primary, secondary


__all__ = [
    "LoadedTenant",
    "TINY_APPROVED",
    "TINY_OTHER",
    "load_both_tenants",
    "load_corpus_fixture",
]
