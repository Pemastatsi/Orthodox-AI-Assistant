"""Tenant isolation invariants per ADR-0010 / vector-store-interface.md."""

from __future__ import annotations

import pytest
from app.adapters.vector_store.base import (
    ChunkPayload,
    VectorFilter,
    assert_single_tenant_batch,
    assert_tenant_filter,
)


def _payload(tenant_id: str) -> ChunkPayload:
    return ChunkPayload(
        chunk_id="ch_1",
        tenant_id=tenant_id,
        source_id="s_1",
        source_hash="sha256:" + "a" * 64,
        chunk_hash="sha256:" + "b" * 64,
        text="text",
        section_path=[],
        page_start=None,
        page_end=None,
        parent_chunk_id=None,
        approved=True,
        visibility="member",
        embedding_model="text-embedding-3-small",
        embedding_dimension=1536,
        corpus_version="v1",
        embedding=[0.0] * 1536,
    )


def test_vector_filter_rejects_empty_tenant() -> None:
    with pytest.raises(ValueError, match="tenant_id required"):
        VectorFilter(tenant_id="")


def test_vector_filter_rejects_whitespace_tenant() -> None:
    with pytest.raises(ValueError, match="tenant_id required"):
        VectorFilter(tenant_id="   ")


def test_assert_tenant_filter_passes_with_real_tenant() -> None:
    assert_tenant_filter(VectorFilter(tenant_id="t_1"))


def test_assert_single_tenant_batch_rejects_mixed_tenants() -> None:
    with pytest.raises(ValueError, match="mixed-tenant upsert batch"):
        assert_single_tenant_batch([_payload("t_1"), _payload("t_2")])


def test_assert_single_tenant_batch_allows_homogeneous_tenants() -> None:
    assert_single_tenant_batch([_payload("t_1"), _payload("t_1")])
