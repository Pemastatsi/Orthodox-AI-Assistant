"""F-23 round-trip: A4 + A5 + A6 over a fixed evidence packet.

This is the integration-level acceptance test in T-004. It does not touch Postgres or
Qdrant — A4 receives pre-built ScoredChunks, A5 is driven by a `FakeStructuredProvider`,
and A6 runs the deterministic checks plus the (disabled-by-default) judge.

When this passes, the closed-corpus loop is verified end-to-end at the algorithmic level.
T-005 + T-006 add the cache, telemetry, and UI layers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.core.auth import make_dev_principal
from app.domain.agents.composer import Composer
from app.domain.agents.evidence_packager import EvidencePackager
from app.domain.agents.verifier import Verifier, VerifierConfig
from app.domain.models.chunk import Chunk
from app.domain.models.classified_query import ClassifiedQuery
from app.domain.models.scored_chunk import ScoredChunk
from app.domain.services.safety_config import load_pastoral_filters

from tests.fixtures.fakes import ComposerFakeProvider

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PASTORAL_PATH = _REPO_ROOT / "config" / "pastoral_filters.yaml"
NOW = datetime(2026, 5, 26, 12, 0, 0, tzinfo=UTC)
SHA = "sha256:" + "e" * 64


@pytest.fixture()
def pastoral_config():
    return load_pastoral_filters(_PASTORAL_PATH)


def _chunk(chunk_id: str, *, text: str, score_hint: float = 0.85) -> ScoredChunk:
    del score_hint  # score is set at ScoredChunk construction
    chunk = Chunk(
        chunk_id=chunk_id,
        source_id=f"src_{chunk_id}",
        tenant_id="tn_test",
        text=text,
        chunk_hash=SHA,
        approved=True,
        visibility="member",
        embedding_model="text-embedding-3-small",
        embedding_dimension=1536,
        corpus_version="2026-05-01",
        created_at=NOW,
    )
    return ScoredChunk(chunk=chunk, score=0.85)


async def test_admit_compose_verify_round_trip(pastoral_config) -> None:
    """F-23: a fixed EvidencePacket → A4 → A5 → A6 produces a passing VerifiedResponse."""
    candidates = [
        _chunk(
            "ch_basil_prayer_1",
            text=(
                "Saint Basil writes that prayer requires patience and steadfastness. "
                "He teaches us to ask, seek, and knock without despair."
            ),
        ),
        _chunk(
            "ch_basil_prayer_2",
            text=(
                "True prayer is rooted in humility and ceaseless attention. "
                "The Fathers warn against praying with a divided mind."
            ),
        ),
    ]
    classified = ClassifiedQuery(
        raw_query="What does Saint Basil teach about prayer?",
        answer_mode="consensus",
        sensitivity_primary="normal",
        risk_flags=[],
        handling="answer",
        preliminary_confidence_tier="YELLOW",
    )
    principal = make_dev_principal(tenant_id="tn_test", role="member")

    # ---- A4 -----------------------------------------------------------------------
    packager = EvidencePackager(corpus_version="2026-05-01")
    packaging = packager.package(
        candidates=candidates,
        classified=classified,
        principal=principal,
        run_id="run_e2e",
    )
    assert packaging.packet.confidence_tier in {"GREEN", "YELLOW"}
    assert len(packaging.packet.admitted_chunks) == 2

    # ---- A5 (fake provider returns an answer that overlaps chunk #1) ------------
    composer_provider = ComposerFakeProvider(
        answer="Saint Basil writes that prayer requires patience and steadfastness.",
        cited_chunk_ids=["ch_basil_prayer_1"],
    )
    composer = Composer(
        provider=composer_provider,
        prompt_version="a5_compose@2026-05-01.1",
        model_route_id="a5_compose_anthropic@2026-05-01.1",
    )
    composer_output = await composer.compose(
        packet=packaging.packet, classified=classified, run_id="run_e2e"
    )

    # ---- A6 (judge disabled per F-08 default) -----------------------------------
    verifier = Verifier(
        pastoral_config=pastoral_config,
        config=VerifierConfig(
            verifier_version="a6_verify@2026-05-01.1",
            schema_version="2026-05-01.1",
            judge_route_id="",  # F-08: empty disables judge cleanly
        ),
        judge_provider=None,
    )
    response = await verifier.verify(
        composer_output=composer_output,
        packet=packaging.packet,
        classified=classified,
        run_id="run_e2e",
    )

    # ---- Assertions --------------------------------------------------------------
    assert response.verification.passed is True
    assert response.handling == "answer"
    assert len(response.citations) == 1
    assert response.citations[0].chunk_id == "ch_basil_prayer_1"
    assert response.run_id == "run_e2e"
    # Schema round-trip: the response payload validates against the Pydantic model
    # (which mirrors verified-response.schema.json).
    payload = response.model_dump(by_alias=True, mode="json")
    assert payload["handling"] == "answer"
    assert payload["citations"][0]["chunkId"] == "ch_basil_prayer_1"
    assert payload["verification"]["passed"] is True


async def test_round_trip_rejects_off_topic_answer(pastoral_config) -> None:
    """If A5 invents an off-topic answer, A6 must reject and produce a bounded fallback."""
    candidates = [
        _chunk("ch_prayer", text="Saint Basil writes about prayer and humility."),
    ]
    classified = ClassifiedQuery(
        raw_query="What does Saint Basil teach about prayer?",
        answer_mode="consensus",
        sensitivity_primary="normal",
        risk_flags=[],
        handling="answer",
        preliminary_confidence_tier="YELLOW",
    )
    principal = make_dev_principal(tenant_id="tn_test", role="member")

    packager = EvidencePackager(corpus_version="2026-05-01")
    packaging = packager.package(
        candidates=candidates, classified=classified, principal=principal, run_id="r"
    )

    composer_provider = ComposerFakeProvider(
        answer=(
            "The liturgy begins with the great litany, followed by the antiphons and "
            "the small entrance with the gospel book held high before the altar."
        ),
        cited_chunk_ids=["ch_prayer"],
    )
    composer = Composer(
        provider=composer_provider,
        prompt_version="a5_compose@2026-05-01.1",
        model_route_id="a5_compose_anthropic@2026-05-01.1",
    )
    composer_output = await composer.compose(
        packet=packaging.packet, classified=classified, run_id="r"
    )

    verifier = Verifier(
        pastoral_config=pastoral_config,
        config=VerifierConfig(
            verifier_version="a6_verify@2026-05-01.1",
            schema_version="2026-05-01.1",
            judge_route_id="",
        ),
    )
    response = await verifier.verify(
        composer_output=composer_output,
        packet=packaging.packet,
        classified=classified,
        run_id="r",
    )

    assert response.verification.passed is False
    assert response.handling == "insufficient_evidence"
    assert response.citations == []
