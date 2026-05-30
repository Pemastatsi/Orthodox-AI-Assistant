"""Unit tests for the live-harness factory + the additive `QdrantStore(collection=…)` option.

All offline: construction of a live harness makes no network call (real I/O only happens when
`.run()` is awaited, which these tests never do), so this asserts wiring only — the openai candidate
constructs and the bge candidate errors clearly until its deferred dependency lands.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest

pytest.importorskip("app")

from app.adapters.vector_store.qdrant_store import QdrantStore  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.domain.models.model_route import ModelRoute  # noqa: E402

from tests.retrieval_eval.runner import build_live_harness  # noqa: E402


def _route(*, provider: str, model: str, route_id: str) -> ModelRoute:
    return ModelRoute(
        route_id=route_id,
        purpose="embedding",
        provider=provider,  # type: ignore[arg-type]
        model=model,
        prompt_version="embedding_none@2026-05-01.1",
        schema_version="1.0",
        certification_status="experiment",
        created_at=datetime.now(UTC),
    )


def test_qdrant_store_collection_override() -> None:
    store = QdrantStore(
        embedding_dimension=3072,
        collection="cand_large_2026_05_29",
        client=cast(Any, object()),  # avoid creating a real client; no network
    )
    assert store.collection_name == "cand_large_2026_05_29"


def test_qdrant_store_defaults_to_settings_collection() -> None:
    store = QdrantStore(embedding_dimension=1536, client=cast(Any, object()))
    assert store.collection_name == (get_settings().qdrant_collection_prefix or "chunks")


def test_build_live_harness_openai_constructs_offline() -> None:
    route = _route(
        provider="openai",
        model="text-embedding-3-large",
        route_id="embedding_openai_large@2026-05-29.1",
    )
    harness = build_live_harness(
        route=route,
        settings=get_settings(),
        collection="cand_large_2026_05_29",
        tenant_id="tenant_orthodox_ethos",
    )
    assert harness.principal.tenant_id == "tenant_orthodox_ethos"
    assert harness.retriever._store.collection_name == "cand_large_2026_05_29"
    assert harness.retriever._embedding_route_id == route.route_id
    # text-embedding-3-large is a 3072-dim model; the store is sized to match.
    assert harness.retriever._store.embedding_dimension == 3072


def test_build_live_harness_bge_errors_clearly() -> None:
    route = _route(
        provider="bge", model="bge-m3", route_id="embedding_bge_m3@2026-05-29.1"
    )
    with pytest.raises(NotImplementedError, match="bge candidate"):
        build_live_harness(
            route=route,
            settings=get_settings(),
            collection="cand_bge_2026_05_29",
            tenant_id="tenant_orthodox_ethos",
        )
