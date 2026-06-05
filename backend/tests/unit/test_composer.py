"""Tests for `app.domain.agents.composer.Composer` (A5)."""

from __future__ import annotations

import pytest
from app.core.errors import ProviderInvalidResponseError, ProviderRefusedError
from app.domain.agents.composer import Composer
from app.domain.models.classified_query import ClassifiedQuery
from app.domain.models.evidence_packet import AdmittedChunk, EvidencePacket

from tests.fixtures.fakes import ComposerFakeProvider

SHA = "sha256:" + "a" * 64


def _packet(*, chunks: list[AdmittedChunk] | None = None) -> EvidencePacket:
    chunks = chunks or [
        AdmittedChunk(
            chunk_id="ch_1",
            source_id="src_1",
            title="On Prayer",
            text="Saint Basil writes that prayer requires patience and steadfastness.",
            score=0.85,
            visibility="member",
            source_hash=SHA,
            chunk_hash=SHA,
            father="Basil the Great",
            work="On Prayer",
        ),
    ]
    return EvidencePacket(
        tenant_id="tn_test",
        corpus_version="2026-05-01",
        confidence_tier="YELLOW",
        admitted_chunks=chunks,
        suppressed_chunk_ids=[],
        lineage_context=[],
    )


def _classified(*, reframed: str | None = None) -> ClassifiedQuery:
    return ClassifiedQuery(
        raw_query="What does Saint Basil teach about prayer?",
        answer_mode="consensus",
        sensitivity_primary="normal",
        risk_flags=[],
        handling="answer",
        preliminary_confidence_tier="YELLOW",
        reframed_query=reframed,
    )


def _composer(provider: ComposerFakeProvider) -> Composer:
    return Composer(
        provider=provider,
        prompt_version="a5_compose@2026-05-01.1",
        model_route_id="a5_compose_anthropic@2026-05-01.1",
    )


async def test_compose_returns_structured_output() -> None:
    provider = ComposerFakeProvider(
        answer="Saint Basil writes that prayer requires patience.",
        cited_chunk_ids=["ch_1"],
    )
    composer = _composer(provider)

    output = await composer.compose(
        packet=_packet(), classified=_classified(), run_id="run_1"
    )

    assert output.answer == "Saint Basil writes that prayer requires patience."
    assert output.cited_chunk_ids == ["ch_1"]
    assert output.model_route_id == "a5_compose_anthropic@2026-05-01.1"


async def test_compose_prompt_contains_only_admitted_chunks() -> None:
    """A5 must never see content outside the EvidencePacket. The user message MUST contain
    the admitted chunks AND the user's question text (raw or reframed) — and nothing else."""
    provider = ComposerFakeProvider(cited_chunk_ids=["ch_1"])
    composer = _composer(provider)

    await composer.compose(packet=_packet(), classified=_classified(), run_id="r")

    user_msg = next(m for m in provider.calls[0]["messages"] if m.role == "user")
    # The admitted-chunk text is present.
    assert "Saint Basil writes that prayer requires patience" in user_msg.content
    # The system prompt restricts the model to closed-corpus; the user payload is JSON.
    assert "evidenceChunks" in user_msg.content


async def test_compose_uses_reframed_query_when_set() -> None:
    """ADR-0007: when A1 reframes, the composer sees the reframed query, not the raw query."""
    provider = ComposerFakeProvider(cited_chunk_ids=["ch_1"])
    composer = _composer(provider)
    classified = _classified(reframed="What does the Church teach about marriage?")
    classified = classified.model_copy(
        update={"raw_query": "Should I divorce my wife"}
    )

    await composer.compose(packet=_packet(), classified=classified, run_id="r")

    user_msg = next(m for m in provider.calls[0]["messages"] if m.role == "user")
    assert "What does the Church teach about marriage?" in user_msg.content
    # The raw advice-seeking phrasing must NOT leak to the model when reframed.
    assert "Should I divorce my wife" not in user_msg.content


async def test_compose_propagates_refusal() -> None:
    """A5 refusal raises `ProviderRefusedError`; the caller turns it into a bounded fallback."""
    provider = ComposerFakeProvider(finish_reason="refusal")
    composer = _composer(provider)

    with pytest.raises(ProviderRefusedError):
        await composer.compose(packet=_packet(), classified=_classified(), run_id="r")


async def test_compose_rejects_invalid_payload() -> None:
    """If the provider somehow returns a non-dict for citedChunkIds, A5 raises invalid_response."""

    class BadProvider(ComposerFakeProvider):
        async def generate_structured(self, **kwargs):  # type: ignore[override, no-untyped-def]
            res = await super().generate_structured(**kwargs)
            res.data["citedChunkIds"] = "not-a-list"  # corrupt
            return res

    composer = _composer(BadProvider(cited_chunk_ids=["ch_1"]))
    with pytest.raises(ProviderInvalidResponseError):
        await composer.compose(packet=_packet(), classified=_classified(), run_id="r")


def _dispute_classified() -> ClassifiedQuery:
    return ClassifiedQuery(
        raw_query="Do the Fathers agree on the origin of the soul?",
        answer_mode="scholarly_dispute",
        sensitivity_primary="normal",
        risk_flags=[],
        handling="answer",
        preliminary_confidence_tier="YELLOW",
    )


async def test_compose_returns_positions_for_scholarly_dispute() -> None:
    """In scholarly_dispute mode A5 emits `positions[]`; `answer` is empty and the
    composer's `cited_chunk_ids` is the order-preserving union across columns."""
    provider = ComposerFakeProvider(
        positions=[
            {
                "name": "Creationism",
                "thesis": "The soul is created directly by God.",
                "citedChunkIds": ["ch_1"],
            },
            {
                "name": "Traducianism",
                "thesis": "The soul is transmitted with the body from the parents.",
                "citedChunkIds": ["ch_2", "ch_1"],
            },
        ],
    )
    composer = _composer(provider)

    output = await composer.compose(
        packet=_packet(), classified=_dispute_classified(), run_id="run_d"
    )

    assert output.positions is not None
    assert [p.name for p in output.positions] == ["Creationism", "Traducianism"]
    assert output.positions[0].cited_chunk_ids == ["ch_1"]
    assert output.positions[1].cited_chunk_ids == ["ch_2", "ch_1"]
    assert output.answer == ""
    # Union is order-preserving and de-duplicated (ch_1 cited by both columns appears once).
    assert output.cited_chunk_ids == ["ch_1", "ch_2"]


async def test_compose_dispute_rejects_payload_without_positions() -> None:
    """A scholarly_dispute payload missing `positions` is invalid → bounded fallback upstream."""
    provider = ComposerFakeProvider(answer="x", cited_chunk_ids=["ch_1"])
    composer = _composer(provider)
    with pytest.raises(ProviderInvalidResponseError):
        await composer.compose(
            packet=_packet(), classified=_dispute_classified(), run_id="r"
        )
