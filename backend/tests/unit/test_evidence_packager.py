"""Tests for `app.domain.agents.evidence_packager.EvidencePackager` (A4)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.auth import make_dev_principal
from app.domain.agents.evidence_packager import (
    GREEN_MIN_CHUNKS,
    GREEN_SCORE,
    MAX_ADMITTED,
    YELLOW_SCORE,
    EvidencePackager,
)
from app.domain.models.chunk import Chunk
from app.domain.models.classified_query import ClassifiedQuery
from app.domain.models.scored_chunk import ScoredChunk

NOW = datetime(2026, 5, 26, 12, 0, 0, tzinfo=UTC)
SHA = "sha256:" + "f" * 64


def _chunk(
    *,
    chunk_id: str = "ch_1",
    tenant_id: str = "tn_test",
    approved: bool = True,
    visibility: str = "member",
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        source_id=f"src-{chunk_id}",
        tenant_id=tenant_id,
        text=f"text of {chunk_id}",
        chunk_hash=SHA,
        approved=approved,
        visibility=visibility,
        embedding_model="text-embedding-3-small",
        embedding_dimension=1536,
        corpus_version="fixture-2026-05-01",
        created_at=NOW,
    )


def _scored(chunk: Chunk, score: float) -> ScoredChunk:
    return ScoredChunk(chunk=chunk, score=score)


def _classified(handling: str = "answer") -> ClassifiedQuery:
    return ClassifiedQuery(
        raw_query="benign question",
        answer_mode="consensus",
        sensitivity_primary="normal",
        risk_flags=[],
        handling=handling,
        preliminary_confidence_tier="YELLOW",
    )


def _principal(tenant_id: str = "tn_test", role: str = "member"):
    return make_dev_principal(tenant_id=tenant_id, role=role)


def test_admits_approved_tenant_chunks() -> None:
    packager = EvidencePackager(corpus_version="2026-05-01")
    candidates = [
        _scored(_chunk(chunk_id="c1"), 0.9),
        _scored(_chunk(chunk_id="c2"), 0.7),
    ]
    result = packager.package(
        candidates=candidates,
        classified=_classified(),
        principal=_principal(),
        run_id="run_1",
    )
    chunk_ids = {c.chunk_id for c in result.packet.admitted_chunks}
    assert chunk_ids == {"c1", "c2"}
    assert result.packet.suppressed_chunk_ids == []
    assert result.packet.lineage_context == []  # Phase 1 invariant


def test_drops_unapproved_chunks() -> None:
    packager = EvidencePackager(corpus_version="2026-05-01")
    result = packager.package(
        candidates=[
            _scored(_chunk(chunk_id="bad", approved=False), 0.9),
            _scored(_chunk(chunk_id="ok"), 0.9),
        ],
        classified=_classified(),
        principal=_principal(),
        run_id="r",
    )
    chunk_ids = [c.chunk_id for c in result.packet.admitted_chunks]
    assert chunk_ids == ["ok"]
    assert "bad" in result.packet.suppressed_chunk_ids


def test_drops_cross_tenant_chunks() -> None:
    packager = EvidencePackager(corpus_version="2026-05-01")
    result = packager.package(
        candidates=[
            _scored(_chunk(chunk_id="foreign", tenant_id="tn_other"), 0.9),
            _scored(_chunk(chunk_id="mine"), 0.9),
        ],
        classified=_classified(),
        principal=_principal(),
        run_id="r",
    )
    chunk_ids = [c.chunk_id for c in result.packet.admitted_chunks]
    assert chunk_ids == ["mine"]
    assert "foreign" in result.packet.suppressed_chunk_ids


def test_drops_admin_only_chunks_per_schema() -> None:
    """ADR-0001 + evidence-packet.schema.json: only `member`/`scholar` visibilities are
    admittable. Even an admin viewing admin_only content cannot pull that content into
    user-facing evidence."""
    packager = EvidencePackager(corpus_version="2026-05-01")
    result = packager.package(
        candidates=[_scored(_chunk(chunk_id="adm", visibility="admin_only"), 0.95)],
        classified=_classified(),
        principal=_principal(role="owner"),
        run_id="r",
    )
    assert result.packet.admitted_chunks == []
    assert "adm" in result.packet.suppressed_chunk_ids


def test_drops_below_yellow_threshold() -> None:
    packager = EvidencePackager(corpus_version="2026-05-01")
    low_score = YELLOW_SCORE - 0.01
    result = packager.package(
        candidates=[_scored(_chunk(chunk_id="low"), low_score)],
        classified=_classified(),
        principal=_principal(),
        run_id="r",
    )
    assert result.packet.admitted_chunks == []
    assert "low" in result.packet.suppressed_chunk_ids
    assert result.packet.confidence_tier == "RED"


def test_green_tier_requires_min_chunks_above_green_score() -> None:
    packager = EvidencePackager(corpus_version="2026-05-01")
    scores = [GREEN_SCORE + 0.01] * GREEN_MIN_CHUNKS
    candidates = [
        _scored(_chunk(chunk_id=f"c{i}"), score) for i, score in enumerate(scores)
    ]
    result = packager.package(
        candidates=candidates,
        classified=_classified(),
        principal=_principal(),
        run_id="r",
    )
    assert result.packet.confidence_tier == "GREEN"


def test_yellow_tier_when_above_yellow_below_green() -> None:
    packager = EvidencePackager(corpus_version="2026-05-01")
    candidates = [_scored(_chunk(chunk_id="c"), (GREEN_SCORE + YELLOW_SCORE) / 2)]
    result = packager.package(
        candidates=candidates,
        classified=_classified(),
        principal=_principal(),
        run_id="r",
    )
    assert result.packet.confidence_tier == "YELLOW"


def test_caps_admitted_chunks_at_max() -> None:
    packager = EvidencePackager(corpus_version="2026-05-01")
    candidates = [
        _scored(_chunk(chunk_id=f"c{i}"), 0.9 - i * 0.001)
        for i in range(MAX_ADMITTED + 3)
    ]
    result = packager.package(
        candidates=candidates,
        classified=_classified(),
        principal=_principal(),
        run_id="r",
    )
    assert len(result.packet.admitted_chunks) == MAX_ADMITTED
    # The lowest-scored 3 should be suppressed.
    assert len(result.packet.suppressed_chunk_ids) == 3


def test_block_with_redirect_yields_red_tier() -> None:
    packager = EvidencePackager(corpus_version="2026-05-01")
    result = packager.package(
        candidates=[_scored(_chunk(chunk_id="c"), 0.9)],
        classified=_classified(handling="block_with_redirect"),
        principal=_principal(),
        run_id="r",
    )
    # Even when hits exist, a block_with_redirect classification forces RED.
    assert result.packet.confidence_tier == "RED"


def test_empty_candidates_yield_red_tier() -> None:
    packager = EvidencePackager(corpus_version="2026-05-01")
    result = packager.package(
        candidates=[],
        classified=_classified(),
        principal=_principal(),
        run_id="r",
    )
    assert result.packet.confidence_tier == "RED"
    assert result.packet.admitted_chunks == []
