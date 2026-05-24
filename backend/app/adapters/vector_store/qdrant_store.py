"""Qdrant-backed VectorStore.

Single shared collection per ADR-0013, with `tenant_id` payload filter on every query and a
mandatory `assert_single_tenant_batch` / `assert_tenant_filter` guard before any I/O leaves the
process. Dense vectors (cosine, sized to `embedding_dimension`) plus an optional named sparse
vector (`text_bm25`) per ADR-0011 — when both are present, search fuses them server-side via
Qdrant's RRF.

Forbidden outside this module: `import qdrant_client`. See `scaffold-contract.md`.
"""

from __future__ import annotations

import asyncio
from datetime import UTC
from typing import TYPE_CHECKING, Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.adapters.vector_store.base import (
    ChunkPayload,
    ScoredChunk,
    SparseVector,
    VectorFilter,
    assert_single_tenant_batch,
    assert_tenant_filter,
)
from app.core.config import Settings, get_settings
from app.core.errors import (
    VectorStoreInvalidDimensionError,
    VectorStoreTimeoutError,
    VectorStoreUnavailableError,
)

if TYPE_CHECKING:
    pass


_DENSE_VECTOR_NAME = "dense"
_SPARSE_VECTOR_NAME = "text_bm25"


def _build_filter(filters: VectorFilter) -> qmodels.Filter:
    must: list[qmodels.FieldCondition] = [
        qmodels.FieldCondition(
            key="tenant_id",
            match=qmodels.MatchValue(value=filters.tenant_id),
        ),
    ]
    if filters.approved is not None:
        must.append(
            qmodels.FieldCondition(
                key="approved",
                match=qmodels.MatchValue(value=filters.approved),
            )
        )
    if filters.visibility is not None:
        must.append(
            qmodels.FieldCondition(
                key="visibility",
                match=qmodels.MatchValue(value=filters.visibility),
            )
        )
    if filters.source_id is not None:
        must.append(
            qmodels.FieldCondition(
                key="source_id",
                match=qmodels.MatchValue(value=filters.source_id),
            )
        )
    return qmodels.Filter(must=must)


def _payload_for(p: ChunkPayload) -> dict[str, Any]:
    return {
        "chunk_id": p.chunk_id,
        "tenant_id": p.tenant_id,
        "source_id": p.source_id,
        "source_hash": p.source_hash,
        "chunk_hash": p.chunk_hash,
        "text": p.text,
        "section_path": list(p.section_path),
        "page_start": p.page_start,
        "page_end": p.page_end,
        "parent_chunk_id": p.parent_chunk_id,
        "approved": p.approved,
        "visibility": p.visibility,
        "embedding_model": p.embedding_model,
        "embedding_dimension": p.embedding_dimension,
        "corpus_version": p.corpus_version,
    }


def _point_vectors(p: ChunkPayload) -> dict[str, Any]:
    vectors: dict[str, Any] = {_DENSE_VECTOR_NAME: p.embedding}
    if p.sparse_embedding is not None:
        vectors[_SPARSE_VECTOR_NAME] = qmodels.SparseVector(
            indices=list(p.sparse_embedding.indices),
            values=list(p.sparse_embedding.values),
        )
    return vectors


class QdrantStore:
    name = "qdrant"

    def __init__(
        self,
        *,
        embedding_dimension: int,
        settings: Settings | None = None,
        client: AsyncQdrantClient | None = None,
    ) -> None:
        self._embedding_dimension = embedding_dimension
        cfg = settings or get_settings()
        self._collection = cfg.qdrant_collection_prefix or "chunks"
        if client is not None:
            self._client = client
        else:
            self._client = AsyncQdrantClient(
                url=cfg.qdrant_url or "http://localhost:6333",
                api_key=cfg.qdrant_api_key or None,
                prefer_grpc=False,
            )
        self._ensure_lock = asyncio.Lock()
        self._provisioned = False

    @property
    def embedding_dimension(self) -> int:
        return self._embedding_dimension

    @property
    def collection_name(self) -> str:
        return self._collection

    async def _ensure_collection(self) -> None:
        if self._provisioned:
            return
        async with self._ensure_lock:
            if self._provisioned:
                return
            try:
                exists = await self._client.collection_exists(self._collection)
                if not exists:
                    await self._client.create_collection(
                        collection_name=self._collection,
                        vectors_config={
                            _DENSE_VECTOR_NAME: qmodels.VectorParams(
                                size=self._embedding_dimension,
                                distance=qmodels.Distance.COSINE,
                            )
                        },
                        sparse_vectors_config={
                            _SPARSE_VECTOR_NAME: qmodels.SparseVectorParams(),
                        },
                    )
                    for key in ("tenant_id", "approved", "visibility", "source_id"):
                        schema = (
                            qmodels.PayloadSchemaType.BOOL
                            if key == "approved"
                            else qmodels.PayloadSchemaType.KEYWORD
                        )
                        await self._client.create_payload_index(
                            collection_name=self._collection,
                            field_name=key,
                            field_schema=schema,
                        )
                self._provisioned = True
            except (UnexpectedResponse, ResponseHandlingException) as exc:
                raise VectorStoreUnavailableError(str(exc)) from exc

    async def upsert(self, *, payloads: list[ChunkPayload]) -> None:
        assert_single_tenant_batch(payloads)
        if not payloads:
            return
        for p in payloads:
            if len(p.embedding) != self._embedding_dimension:
                raise VectorStoreInvalidDimensionError(
                    f"chunk {p.chunk_id}: embedding len {len(p.embedding)} != {self._embedding_dimension}"  # noqa: E501
                )
        await self._ensure_collection()

        points = [
            qmodels.PointStruct(
                id=p.chunk_id,
                vector=_point_vectors(p),
                payload=_payload_for(p),
            )
            for p in payloads
        ]
        try:
            await self._client.upsert(collection_name=self._collection, points=points, wait=True)
        except TimeoutError as exc:
            raise VectorStoreTimeoutError(str(exc)) from exc
        except (UnexpectedResponse, ResponseHandlingException) as exc:
            raise VectorStoreUnavailableError(str(exc)) from exc

    async def search(
        self,
        *,
        query_vector: list[float],
        sparse_query: SparseVector | None,
        filters: VectorFilter,
        top_k: int,
    ) -> list[ScoredChunk]:
        assert_tenant_filter(filters)
        if len(query_vector) != self._embedding_dimension:
            raise VectorStoreInvalidDimensionError(
                f"query embedding len {len(query_vector)} != {self._embedding_dimension}"
            )
        if top_k <= 0:
            return []
        await self._ensure_collection()
        qfilter = _build_filter(filters)

        try:
            if sparse_query is None:
                response = await self._client.query_points(
                    collection_name=self._collection,
                    query=list(query_vector),
                    using=_DENSE_VECTOR_NAME,
                    query_filter=qfilter,
                    limit=top_k,
                    with_payload=True,
                )
            else:
                prefetch_limit = max(top_k * 4, 20)
                response = await self._client.query_points(
                    collection_name=self._collection,
                    prefetch=[
                        qmodels.Prefetch(
                            query=list(query_vector),
                            using=_DENSE_VECTOR_NAME,
                            filter=qfilter,
                            limit=prefetch_limit,
                        ),
                        qmodels.Prefetch(
                            query=qmodels.SparseVector(
                                indices=list(sparse_query.indices),
                                values=list(sparse_query.values),
                            ),
                            using=_SPARSE_VECTOR_NAME,
                            filter=qfilter,
                            limit=prefetch_limit,
                        ),
                    ],
                    query=qmodels.FusionQuery(fusion=qmodels.Fusion.RRF),
                    query_filter=qfilter,
                    limit=top_k,
                    with_payload=True,
                )
        except TimeoutError as exc:
            raise VectorStoreTimeoutError(str(exc)) from exc
        except (UnexpectedResponse, ResponseHandlingException) as exc:
            raise VectorStoreUnavailableError(str(exc)) from exc

        return [_hydrate(point) for point in response.points]

    async def delete_by_filter(self, *, filters: VectorFilter) -> int:
        assert_tenant_filter(filters)
        await self._ensure_collection()
        qfilter = _build_filter(filters)

        # Count first so callers know how many points were removed.
        try:
            count_response = await self._client.count(
                collection_name=self._collection,
                count_filter=qfilter,
                exact=True,
            )
            deleted = count_response.count
            await self._client.delete(
                collection_name=self._collection,
                points_selector=qmodels.FilterSelector(filter=qfilter),
                wait=True,
            )
        except TimeoutError as exc:
            raise VectorStoreTimeoutError(str(exc)) from exc
        except (UnexpectedResponse, ResponseHandlingException) as exc:
            raise VectorStoreUnavailableError(str(exc)) from exc

        return int(deleted)

    async def close(self) -> None:
        await self._client.close()


def _hydrate(point: qmodels.ScoredPoint) -> ScoredChunk:
    """Materialize a `ScoredChunk` from the payload Qdrant returned.

    A4 may join against Postgres for fields not stored in the payload (e.g. `created_at`);
    in Phase 1 the payload is sufficient for retrieval-time decisions, so the join is deferred
    to A4 when it lands. For T-002's needs (proof that ingestion produces retrievable chunks),
    constructing the `Chunk` from the payload is enough.
    """
    from datetime import datetime

    from app.domain.models.chunk import Chunk

    payload = point.payload or {}
    chunk = Chunk(
        chunk_id=str(payload.get("chunk_id", point.id)),
        source_id=str(payload["source_id"]),
        tenant_id=str(payload["tenant_id"]),
        text=str(payload.get("text", "")) or "[hydrated]",
        chunk_hash=str(payload["chunk_hash"]),
        approved=bool(payload.get("approved", False)),
        visibility=payload.get("visibility", "admin_only"),
        section_path=list(payload.get("section_path", [])),
        page_start=payload.get("page_start"),
        page_end=payload.get("page_end"),
        parent_chunk_id=payload.get("parent_chunk_id"),
        embedding_model=str(payload.get("embedding_model", "text-embedding-3-small")),
        embedding_dimension=int(payload.get("embedding_dimension", 1536)),
        corpus_version=str(payload.get("corpus_version", "")),
        created_at=datetime.now(UTC),
    )
    return ScoredChunk(chunk=chunk, score=float(point.score))


__all__ = ["QdrantStore"]
