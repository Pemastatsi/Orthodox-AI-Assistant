#!/usr/bin/env python3
"""Embedding backfill driver (T-009 Phase-A — gated item #3 prep).

Implements `docs/contracts/embedding-upgrade-sop.md` §Stage 2 (backfill the new index) +
§Step 2.2 (verify completeness) as a runnable operator command. Re-embeds every **approved** chunk
for a tenant under a candidate embedding route and upserts into a target Qdrant collection (the
candidate's dual-index space) — then asserts row-count parity between Postgres and the new
collection.

PAID + INFRA-GATED — DRY RUN BY DEFAULT. Without `--execute` it makes **no** embedding calls and
**no** Qdrant writes: it counts the approved chunks, estimates the work, and prints the plan. Only
`--execute` (a founder action, requiring a reachable corpus DB + Qdrant + the candidate provider's
API budget) performs the paid backfill. The bge candidate errors clearly until its runtime dep
lands (gated item #2).

Run from `backend/`:

    # dry run — free, shows the plan + chunk/estimate counts (needs the DB to count)
    uv run python ../scripts/run_embedding_backfill.py \
        --tenant-id tn_orthodoxethos --route-id embedding_openai_large@2026-05-29.1

    # live backfill — paid; founder action
    uv run python ../scripts/run_embedding_backfill.py \
        --tenant-id tn_orthodoxethos --route-id embedding_openai_large@2026-05-29.1 \
        --collection chunks_cand_large --execute --verify

SOP alignment: honors the Contextual Retrieval prefix (§"Embedding input contract" — embed
`contextPrefix + "\n\n" + text` when set), reads canonical text from Postgres (not the old
payload), and emits progress every 100 chunks. The §Step 2.2 sampled-payload check and the
founder sign-off audit row are owner steps documented in the certification runbook.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.adapters.providers.openai_provider import OpenAIProvider  # noqa: E402
from app.adapters.sparse.bm25_embedder import Bm25SparseEmbedder  # noqa: E402
from app.adapters.vector_store.base import ChunkPayload  # noqa: E402
from app.adapters.vector_store.qdrant_store import QdrantStore  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.domain.models.model_route import ModelRoute  # noqa: E402
from app.domain.repositories._base import (  # noqa: E402
    dispose_engine,
    init_engine,
    session_scope,
)
from app.domain.repositories.chunk_repository import ChunkRepository  # noqa: E402
from app.domain.repositories.model_route_repository import (  # noqa: E402
    ModelRouteRepository,
)
from app.domain.repositories.source_repository import SourceRepository  # noqa: E402

_EMBED_INPUT_SEP = "\n\n"  # SOP §Embedding input contract: contextPrefix + "\n\n" + text
_PROGRESS_EVERY = 100


def _embedder_for(route: ModelRoute) -> OpenAIProvider:
    """The candidate provider. openai is runnable; bge is gated (item #2)."""
    if route.provider == "bge":
        raise SystemExit(
            "error: the bge candidate (BGE-M3) is not runnable yet — its runtime dependency is a "
            "deferred, founder-/budget-gated decision (see docs/adr/0017). Run the openai "
            "candidate, or land the bge dependency first."
        )
    if route.provider != "openai":
        raise SystemExit(
            f"error: backfill supports the openai/bge embedding candidates; got "
            f"provider={route.provider!r} for {route.route_id}"
        )
    return OpenAIProvider(settings=get_settings(), model=route.model)


def _embed_input(text: str, context_prefix: str | None) -> str:
    return f"{context_prefix}{_EMBED_INPUT_SEP}{text}" if context_prefix else text


async def _iter_approved_chunks(tenant_id: str):
    """Yield approved chunks for the tenant, paginated by chunk_id (ChunkRepository keyset)."""
    cursor: str | None = None
    while True:
        async with session_scope() as session:
            items, cursor = await ChunkRepository(session).list_by_tenant(
                tenant_id=tenant_id, approved=True, cursor=cursor, limit=100
            )
        for chunk in items:
            yield chunk
        if cursor is None:
            return


async def _count_approved(tenant_id: str) -> int:
    from sqlalchemy import text

    async with session_scope() as session:
        result = await session.execute(
            text(
                "SELECT COUNT(*) AS n FROM chunks "
                "WHERE tenant_id = :t AND approved = true"
            ),
            {"t": tenant_id},
        )
        return int(result.mappings().one()["n"])


async def _backfill(
    *,
    route: ModelRoute,
    tenant_id: str,
    collection: str,
    execute: bool,
    verify: bool,
) -> int:
    settings = get_settings()
    init_engine(settings)
    try:
        approved_count = await _count_approved(tenant_id)
        provider = _embedder_for(route)
        dim = provider.embedding_dimension

        print()
        print("Embedding Backfill — SOP §Stage 2")
        print("=" * 72)
        print(f"tenant     : {tenant_id}")
        print(f"route      : {route.route_id}  ({route.provider}:{route.model}, {dim}d)")
        print(f"collection : {collection}")
        print(f"approved chunks to re-embed: {approved_count}")
        print(f"mode       : {'EXECUTE (paid)' if execute else 'DRY RUN (no spend)'}")
        print("-" * 72)

        if not execute:
            print(
                f"DRY RUN: would embed {approved_count} chunks via {route.provider}:{route.model} "
                f"and upsert into '{collection}'. Re-run with --execute to perform the paid "
                "backfill (founder action). No embedding calls or Qdrant writes were made."
            )
            return 0

        store = QdrantStore(
            embedding_dimension=dim, settings=settings, collection=collection
        )
        sparse = Bm25SparseEmbedder()
        source_hash_cache: dict[str, str] = {}
        done = 0
        try:
            async for chunk in _iter_approved_chunks(tenant_id):
                if chunk.source_id not in source_hash_cache:
                    async with session_scope() as session:
                        src = await SourceRepository(session).get(
                            tenant_id=tenant_id, source_id=chunk.source_id
                        )
                    source_hash_cache[chunk.source_id] = src.source_hash if src else ""
                embed_text = _embed_input(chunk.text, chunk.context_prefix)
                vectors = await provider.embed_texts(
                    texts=[embed_text],
                    route_id=route.route_id,
                    tenant_id=tenant_id,
                    run_id=f"backfill-{route.route_id}",
                )
                sparse_vec = sparse.embed([embed_text])[0]
                payload = ChunkPayload(
                    chunk_id=chunk.chunk_id,
                    tenant_id=tenant_id,
                    source_id=chunk.source_id,
                    source_hash=source_hash_cache[chunk.source_id],
                    chunk_hash=chunk.chunk_hash,
                    text=chunk.text,
                    section_path=list(chunk.section_path),
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    parent_chunk_id=chunk.parent_chunk_id,
                    approved=chunk.approved,
                    visibility=chunk.visibility,
                    embedding_model=f"{route.provider}:{route.model}@{route.route_id.split('@')[-1]}",
                    embedding_dimension=dim,
                    corpus_version=chunk.corpus_version,
                    embedding=vectors[0],
                    sparse_embedding=sparse_vec,
                )
                await store.upsert(payloads=[payload])
                done += 1
                if done % _PROGRESS_EVERY == 0:
                    print(f"  embedding_backfill_progress: {done}/{approved_count}")

            print(f"backfilled {done} chunks into '{collection}'.")

            if verify:
                # SOP §Step 2.2: row-count parity between Postgres and the new collection.
                count = await _count_in_collection(store, tenant_id=tenant_id)
                print("-" * 72)
                print(f"SOP §2.2 parity: postgres approved={approved_count}  qdrant={count}")
                if count != approved_count:
                    print(
                        "  FAIL: counts differ — re-run the backfill for the missing chunks; do "
                        "NOT proceed to Stage 3 with a partial index."
                    )
                    return 1
                print("  PASS: row-count parity holds.")
        finally:
            await store.close()
        return 0
    finally:
        await dispose_engine()


async def _count_in_collection(store: QdrantStore, *, tenant_id: str) -> int:
    """Count approved points for the tenant in the target collection (SOP §2.2 parity numerator)."""
    from qdrant_client.http import models as qmodels  # noqa: PLC0415

    qfilter = qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="tenant_id", match=qmodels.MatchValue(value=tenant_id)
            ),
            qmodels.FieldCondition(
                key="approved", match=qmodels.MatchValue(value=True)
            ),
        ]
    )
    resp = await store._client.count(  # type: ignore[attr-defined]
        collection_name=store.collection_name, count_filter=qfilter, exact=True
    )
    return int(resp.count)


async def _amain(args: argparse.Namespace) -> int:
    settings = get_settings()
    init_engine(settings)
    try:
        async with session_scope() as session:
            route = await ModelRouteRepository(session).get(args.route_id)
    except OSError as exc:
        await dispose_engine()
        raise SystemExit(
            f"error: cannot reach the corpus database ({exc}). This driver needs Postgres + "
            "Qdrant + the candidate provider's API budget — it is the founder-/infra-gated "
            "Stage-2 backfill, not a free local op."
        ) from exc
    if route is None:
        await dispose_engine()
        raise SystemExit(
            f"error: route {args.route_id} not found. Seed the candidate route first "
            "(migration 0004 seeds the two T-009 candidates)."
        )
    await dispose_engine()

    if route.purpose != "embedding":
        raise SystemExit(
            f"error: {args.route_id} has purpose={route.purpose!r}; "
            "backfill is for embedding routes."
        )

    collection = args.collection or f"{settings.qdrant_collection_prefix}_candidate"
    return await _backfill(
        route=route,
        tenant_id=args.tenant_id,
        collection=collection,
        execute=args.execute,
        verify=args.verify,
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Re-embed a tenant's approved chunks under a candidate embedding route into a target "
            "Qdrant collection (SOP §Stage 2). Dry run by default; --execute performs the paid "
            "backfill."
        )
    )
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument(
        "--route-id", required=True, help="Candidate embedding ModelRoute.routeId."
    )
    parser.add_argument(
        "--collection",
        default=None,
        help="Target Qdrant collection (the candidate's dual-index space).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform the paid backfill (founder action). Omit for a free dry run.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="After --execute, assert SOP §2.2 row-count parity (postgres approved == qdrant).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_amain(_parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
