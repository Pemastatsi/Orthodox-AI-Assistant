"""arq worker for ingestion jobs.

The HTTP `POST /ingest` endpoint hashes the upload, stores the bytes (currently in Redis under
`ingest:bytes:<job_id>`), creates the `sources` + `ingest_jobs` rows, and enqueues
`process_ingest_job(job_id)`. The worker loads the bytes from Redis, calls
`ingestion_service.process_ingestion`, and drops the Redis key on completion.

For tests / local dev that don't want to spin up arq, `run_ingest_job_inline(job_id)` runs the
same pipeline directly in the calling process.
"""

from __future__ import annotations

from typing import Any

import ulid
from redis.asyncio import Redis

from app.adapters.providers.openai_provider import (
    OpenAIProvider,
    embedding_dimension_for,
)
from app.adapters.sparse.bm25_embedder import Bm25SparseEmbedder
from app.adapters.vector_store.qdrant_store import QdrantStore
from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.repositories._base import init_engine, session_scope
from app.domain.repositories.ingest_job_repository import IngestJobRepository
from app.domain.services.ingestion_service import IngestionContext, process_ingestion

logger = get_logger(__name__)


_REDIS_BYTES_PREFIX = "ingest:bytes:"
_REDIS_META_PREFIX = "ingest:meta:"


def _bytes_key(job_id: str) -> str:
    return _REDIS_BYTES_PREFIX + job_id


def _meta_key(job_id: str) -> str:
    return _REDIS_META_PREFIX + job_id


async def stash_upload(
    *,
    redis: Redis,
    job_id: str,
    file_bytes: bytes,
    mime_type: str,
    source_id: str,
    tenant_id: str,
    ttl_seconds: int = 3600,
) -> None:
    """Park raw bytes + metadata in Redis until the worker drains them."""
    pipe = redis.pipeline()
    pipe.set(_bytes_key(job_id), file_bytes, ex=ttl_seconds)
    pipe.hset(
        _meta_key(job_id),
        mapping={
            "mime_type": mime_type,
            "source_id": source_id,
            "tenant_id": tenant_id,
        },
    )
    pipe.expire(_meta_key(job_id), ttl_seconds)
    await pipe.execute()


async def _load_upload(redis: Redis, job_id: str) -> tuple[bytes, dict[str, str]] | None:
    raw = await redis.get(_bytes_key(job_id))
    meta = await redis.hgetall(_meta_key(job_id))  # type: ignore[misc]
    if raw is None or not meta:
        return None
    decoded_meta = {
        (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
        for k, v in meta.items()
    }
    return bytes(raw), decoded_meta


async def _drop_upload(redis: Redis, job_id: str) -> None:
    pipe = redis.pipeline()
    pipe.delete(_bytes_key(job_id))
    pipe.delete(_meta_key(job_id))
    await pipe.execute()


async def _run(job_id: str, *, redis: Redis) -> None:
    payload = await _load_upload(redis, job_id)
    if payload is None:
        logger.warning("ingest.failed", job_id=job_id, reason="payload_missing")
        return
    file_bytes, meta = payload

    settings = get_settings()
    # Ingestion writes sources/chunks/ingest_jobs (RLS tables) without setting a per-tenant GUC,
    # so it connects as app_admin (BYPASSRLS) per ADR-0016 Rule 5. Setting the GUC per job (so
    # ingestion runs as app_runtime) is a documented follow-up.
    init_engine(settings, admin=True)

    # Fetch the latest job state so we use the right tenant/source ids of record.
    async with session_scope() as session:
        job = await IngestJobRepository(session).get(
            tenant_id=meta["tenant_id"], job_id=job_id
        )
    if job is None:
        logger.warning("ingest.failed", job_id=job_id, reason="job_missing")
        return

    provider = OpenAIProvider(settings=settings, model="text-embedding-3-small")
    vector_store = QdrantStore(
        embedding_dimension=embedding_dimension_for("text-embedding-3-small"),
        settings=settings,
    )
    sparse = Bm25SparseEmbedder()

    ctx = IngestionContext(
        job_id=job_id,
        tenant_id=meta["tenant_id"],
        source_id=meta["source_id"],
        file_bytes=file_bytes,
        mime_type=meta["mime_type"],
        embedding_model="text-embedding-3-small",
        corpus_version=settings.active_schema_version,
        embedding_dimension=provider.embedding_dimension,
        run_id=f"run_{ulid.new()!s}",
    )

    try:
        await process_ingestion(
            ctx,
            embedding_provider=provider,
            vector_store=vector_store,
            sparse_embedder=sparse,
        )
    finally:
        await _drop_upload(redis, job_id)
        await vector_store.close()


# ---- arq task entrypoint --------------------------------------------------

async def process_ingest_job(ctx: dict[str, Any], job_id: str) -> None:
    """arq task. `ctx['redis']` is the arq Redis pool."""
    redis: Redis = ctx["redis"]
    await _run(job_id, redis=redis)


async def run_ingest_job_inline(job_id: str, *, redis: Redis) -> None:
    """Drain a single job in the calling process. Useful for tests and local dev."""
    await _run(job_id, redis=redis)


class WorkerSettings:
    """arq WorkerSettings — pointed at by `arq app.workers.ingestion_worker.WorkerSettings`."""

    functions = [process_ingest_job]
    redis_settings: Any = None  # populated at runtime by arq when run with the CLI

    @staticmethod
    async def on_startup(ctx: dict[str, Any]) -> None:
        del ctx  # arq passes its own context; we just need to wake the engine
        init_engine(admin=True)  # ADR-0016 Rule 5: ingestion runs as app_admin (see _run)


__all__ = [
    "WorkerSettings",
    "process_ingest_job",
    "run_ingest_job_inline",
    "stash_upload",
]
