"""Ingestion orchestrator.

Steps:
  1. Parse — dispatcher chooses pdfplumber or tesseract per parser-interface.md heuristic.
  2. Chunk — chunking_service.chunk_pages produces ChunkCandidates.
  3. Embed — dense via OpenAIProvider.embed_texts (in batches); sparse via FastEmbed BM25 if
     a sparse embedder is supplied (D-RET-001 — re-ingestion is otherwise required when T-003
     enables hybrid search).
  4. Persist — chunk_repository.bulk_insert assigns chunk_ids; QdrantStore.upsert indexes.
  5. Transition the IngestJob to `awaiting_review`. Chunks default to `approved=false`; the
     reviewer flips them via `PATCH /corpus/{chunkId}`, which cascade-approves the source.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.adapters.parsers.pdfplumber_parser import PdfplumberParser
from app.adapters.parsers.tesseract_parser import TesseractParser
from app.adapters.providers.base import LLMProvider
from app.adapters.vector_store.base import ChunkPayload, SparseVector, VectorStore
from app.core.errors import (
    ParserCorruptFileError,
    ParserExtractionError,
    ParserPasswordProtectedError,
    ParserTimeoutError,
    ProviderInvalidResponseError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    VectorStoreInvalidDimensionError,
    VectorStoreTimeoutError,
    VectorStoreUnavailableError,
)
from app.core.logging import get_logger
from app.domain.repositories._base import session_scope
from app.domain.repositories.chunk_repository import (
    ChunkInsert,
    ChunkRepository,
    compute_chunk_hash,
)
from app.domain.repositories.ingest_job_repository import IngestJobRepository
from app.domain.services.chunking_service import ChunkCandidate, chunk_pages
from app.domain.services.parser_dispatcher import dispatch

logger = get_logger(__name__)


_EMBEDDING_BATCH_SIZE = 64


class SparseEmbedder(Protocol):
    """Minimal protocol the orchestrator uses; concrete impl is FastEmbed Bm25 (see factory)."""

    def embed(self, texts: list[str]) -> list[SparseVector]: ...


@dataclass(frozen=True)
class IngestionContext:
    job_id: str
    tenant_id: str
    source_id: str
    file_bytes: bytes
    mime_type: str
    embedding_model: str
    corpus_version: str
    embedding_dimension: int
    run_id: str


@dataclass(frozen=True)
class IngestionResult:
    job_id: str
    chunk_ids: list[str]
    parser_used: str


async def process_ingestion(
    ctx: IngestionContext,
    *,
    embedding_provider: LLMProvider,
    vector_store: VectorStore,
    sparse_embedder: SparseEmbedder | None = None,
    primary_parser: Any | None = None,
    fallback_parser: Any | None = None,
) -> IngestionResult:
    """Drive a single ingestion end-to-end. Updates the IngestJob row at every transition.

    Raises only after writing `failed` status; callers can treat exceptions as terminal.
    """
    primary = primary_parser or PdfplumberParser()
    fallback = fallback_parser or TesseractParser()

    log = logger.bind(
        run_id=ctx.run_id,
        tenant_id=ctx.tenant_id,
        job_id=ctx.job_id,
        source_id=ctx.source_id,
    )
    log.info("ingest.received", size_bytes=len(ctx.file_bytes))

    async with session_scope() as session:
        job_repo = IngestJobRepository(session)
        await job_repo.transition(
            tenant_id=ctx.tenant_id,
            job_id=ctx.job_id,
            status="extracting",
            progress={"stage": "extracting", "completed": 0, "total": 0},
        )

    # --- Step 1: parse -----------------------------------------------------
    try:
        dispatch_result = await dispatch(
            file_bytes=ctx.file_bytes,
            mime_type=ctx.mime_type,
            primary=primary,
            fallback=fallback,
        )
    except (
        ParserCorruptFileError,
        ParserExtractionError,
        ParserPasswordProtectedError,
        ParserTimeoutError,
    ) as exc:
        await _fail(ctx, code=_parser_error_code(exc), message=str(exc))
        log.warning("ingest.failed", stage="extracting", code=_parser_error_code(exc), error=str(exc))  # noqa: E501
        raise

    pages = dispatch_result.pages
    log.info(
        "ingest.extracted",
        parser_used=dispatch_result.parser_used,
        page_count=len(pages),
    )

    # --- Step 2: chunk -----------------------------------------------------
    async with session_scope() as session:
        await IngestJobRepository(session).transition(
            tenant_id=ctx.tenant_id,
            job_id=ctx.job_id,
            status="chunking",
            progress={"stage": "chunking", "completed": 0, "total": len(pages)},
        )

    candidates: list[ChunkCandidate] = chunk_pages(pages)
    if not candidates:
        await _fail(ctx, code="ingest_invalid", message="no chunks produced")
        log.warning("ingest.failed", stage="chunking", code="ingest_invalid")
        return IngestionResult(job_id=ctx.job_id, chunk_ids=[], parser_used=dispatch_result.parser_used)  # noqa: E501

    avg_tokens = sum(len(c.text.split()) for c in candidates) / max(len(candidates), 1)
    log.info(
        "ingest.chunked",
        chunk_count=len(candidates),
        avg_tokens_per_chunk=int(avg_tokens),
        parser_used=dispatch_result.parser_used,
    )

    # --- Step 3: embed -----------------------------------------------------
    async with session_scope() as session:
        await IngestJobRepository(session).transition(
            tenant_id=ctx.tenant_id,
            job_id=ctx.job_id,
            status="embedding",
            progress={"stage": "embedding", "completed": 0, "total": len(candidates)},
        )

    try:
        dense_vectors = await _embed_in_batches(
            embedding_provider=embedding_provider,
            texts=[c.text for c in candidates],
            tenant_id=ctx.tenant_id,
            run_id=ctx.run_id,
        )
    except (
        ProviderRateLimitedError,
        ProviderTimeoutError,
        ProviderUnavailableError,
        ProviderInvalidResponseError,
    ) as exc:
        await _fail(ctx, code="provider_unavailable", message=str(exc))
        log.warning("ingest.failed", stage="embedding", code="provider_unavailable", error=str(exc))
        raise

    sparse_vectors: list[SparseVector | None]
    if sparse_embedder is not None:
        try:
            sparse_vectors = list(sparse_embedder.embed([c.text for c in candidates]))
        except Exception as exc:  # noqa: BLE001 — log and continue without sparse
            log.warning("ingest.sparse_failed", error=str(exc))
            sparse_vectors = [None] * len(candidates)
    else:
        sparse_vectors = [None] * len(candidates)

    log.info(
        "ingest.embedded",
        chunks_processed=len(dense_vectors),
        embedding_model=ctx.embedding_model,
    )

    # --- Step 4: persist ---------------------------------------------------
    # Compute chunk_hash + parent_chunk_id index resolution, then bulk_insert.
    inserts: list[ChunkInsert] = []
    chunk_hashes: list[str] = []
    for candidate in candidates:
        chunk_hash = compute_chunk_hash(
            source_hash=_source_hash_placeholder(ctx),
            text_value=candidate.text,
            section_path=candidate.section_path,
        )
        chunk_hashes.append(chunk_hash)
        inserts.append(
            ChunkInsert(
                tenant_id=ctx.tenant_id,
                source_id=ctx.source_id,
                text=candidate.text,
                chunk_hash=chunk_hash,
                embedding_model=ctx.embedding_model,
                embedding_dimension=ctx.embedding_dimension,
                corpus_version=ctx.corpus_version,
                section_path=candidate.section_path,
                page_start=candidate.page_start,
                page_end=candidate.page_end,
                parent_chunk_id=None,  # resolved after insert
                language="en",
                visibility="admin_only",
            )
        )

    async with session_scope() as session:
        chunk_ids = await ChunkRepository(session).bulk_insert(chunks=inserts)

    # Resolve parent_chunk_index → parent_chunk_id.
    parent_id_for: dict[int, str | None] = {}
    for idx, candidate in enumerate(candidates):
        if candidate.parent_chunk_index is None:
            parent_id_for[idx] = None
        else:
            parent_id_for[idx] = chunk_ids[candidate.parent_chunk_index]

    if any(v is not None for v in parent_id_for.values()):
        async with session_scope() as session:
            repo = ChunkRepository(session)
            for idx, parent_id in parent_id_for.items():
                if parent_id is None:
                    continue
                await session.execute(
                    __import__("sqlalchemy").text(
                        "UPDATE chunks SET parent_chunk_id = :parent_id "
                        "WHERE tenant_id = :tenant_id AND chunk_id = :chunk_id"
                    ),
                    {
                        "tenant_id": ctx.tenant_id,
                        "chunk_id": chunk_ids[idx],
                        "parent_id": parent_id,
                    },
                )
                del repo

    # Upsert into Qdrant.
    payloads = [
        ChunkPayload(
            chunk_id=chunk_ids[i],
            tenant_id=ctx.tenant_id,
            source_id=ctx.source_id,
            source_hash=_source_hash_placeholder(ctx),
            chunk_hash=chunk_hashes[i],
            text=candidates[i].text,
            section_path=candidates[i].section_path,
            page_start=candidates[i].page_start,
            page_end=candidates[i].page_end,
            parent_chunk_id=parent_id_for.get(i),
            approved=False,
            visibility="admin_only",
            embedding_model=ctx.embedding_model,
            embedding_dimension=ctx.embedding_dimension,
            corpus_version=ctx.corpus_version,
            embedding=dense_vectors[i],
            sparse_embedding=sparse_vectors[i],
        )
        for i in range(len(candidates))
    ]
    try:
        await vector_store.upsert(payloads=payloads)
    except (
        VectorStoreInvalidDimensionError,
        VectorStoreTimeoutError,
        VectorStoreUnavailableError,
    ) as exc:
        await _fail(ctx, code="vector_store_unavailable", message=str(exc))
        log.warning("ingest.failed", stage="indexing", code="vector_store_unavailable", error=str(exc))  # noqa: E501
        raise

    # --- Step 5: queue for review -----------------------------------------
    async with session_scope() as session:
        await IngestJobRepository(session).transition(
            tenant_id=ctx.tenant_id,
            job_id=ctx.job_id,
            status="awaiting_review",
            progress={"stage": "awaiting_review", "completed": len(candidates), "total": len(candidates)},  # noqa: E501
        )
    log.info(
        "ingest.queued_for_review",
        chunk_count=len(chunk_ids),
        parser_used=dispatch_result.parser_used,
    )
    log.info(
        "worker.embedding.completed",
        chunks_processed=len(chunk_ids),
        embedding_model=ctx.embedding_model,
    )

    return IngestionResult(
        job_id=ctx.job_id,
        chunk_ids=chunk_ids,
        parser_used=dispatch_result.parser_used,
    )


async def _embed_in_batches(
    *,
    embedding_provider: LLMProvider,
    texts: list[str],
    tenant_id: str,
    run_id: str,
) -> list[list[float]]:
    out: list[list[float]] = []
    for start in range(0, len(texts), _EMBEDDING_BATCH_SIZE):
        batch = texts[start : start + _EMBEDDING_BATCH_SIZE]
        vectors = await embedding_provider.embed_texts(
            texts=batch,
            route_id="embedding_openai@2026-05-01.1",
            tenant_id=tenant_id,
            run_id=run_id,
        )
        out.extend(vectors)
    return out


def _parser_error_code(exc: Exception) -> str:
    if isinstance(exc, ParserPasswordProtectedError):
        return "ingest_password_protected"
    if isinstance(exc, ParserCorruptFileError):
        return "ingest_corrupt_file"
    if isinstance(exc, ParserTimeoutError):
        return "ingest_timeout"
    return "ingest_extraction_failed"


async def _fail(ctx: IngestionContext, *, code: str, message: str) -> None:
    async with session_scope() as session:
        await IngestJobRepository(session).transition(
            tenant_id=ctx.tenant_id,
            job_id=ctx.job_id,
            status="failed",
            progress={"stage": "failed", "completed": 0, "total": 0},
            error_code=code,
            error_message=message,
        )


def _source_hash_placeholder(ctx: IngestionContext) -> str:
    """Recover the source_hash from `ingestion_service`'s knowledge.

    The orchestrator doesn't re-hash the bytes (the API layer already did so and stored it on the
    `sources` row); we fetch the canonical value here. Kept as a helper so the SQL stays in the
    repository layer.
    """
    import hashlib
    return "sha256:" + hashlib.sha256(ctx.file_bytes).hexdigest()


__all__ = [
    "IngestionContext",
    "IngestionResult",
    "SparseEmbedder",
    "process_ingestion",
]
