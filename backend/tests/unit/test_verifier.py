"""Tests for `app.domain.agents.verifier.Verifier` (A6)."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.domain.agents.composer import ComposerOutput
from app.domain.agents.verifier import Verifier, VerifierConfig
from app.domain.models.classified_query import ClassifiedQuery
from app.domain.models.evidence_packet import AdmittedChunk, EvidencePacket
from app.domain.services.safety_config import load_pastoral_filters

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PASTORAL_PATH = _REPO_ROOT / "config" / "pastoral_filters.yaml"

SHA = "sha256:" + "b" * 64


@pytest.fixture()
def pastoral_config():
    return load_pastoral_filters(_PASTORAL_PATH)


def _verifier(
    pastoral_config,
    *,
    judge_route_id: str = "",
    judge_provider=None,
) -> Verifier:
    return Verifier(
        pastoral_config=pastoral_config,
        config=VerifierConfig(
            verifier_version="a6_verify@2026-05-01.1",
            schema_version="2026-05-01.1",
            judge_route_id=judge_route_id,
        ),
        judge_provider=judge_provider,
    )


def _packet(chunks: list[AdmittedChunk] | None = None) -> EvidencePacket:
    chunks = chunks or [
        AdmittedChunk(
            chunk_id="ch_1",
            source_id="src_1",
            title="On Prayer",
            text=(
                "Saint Basil writes that prayer requires patience and steadfastness. "
                "He teaches us to ask, seek, and knock without despair."
            ),
            score=0.85,
            visibility="member",
            source_hash=SHA,
            chunk_hash=SHA,
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


def _classified() -> ClassifiedQuery:
    return ClassifiedQuery(
        raw_query="What does Saint Basil teach about prayer?",
        answer_mode="consensus",
        sensitivity_primary="normal",
        risk_flags=[],
        handling="answer",
        preliminary_confidence_tier="YELLOW",
    )


def _composer_output(
    *,
    answer: str = (
        "Saint Basil writes that prayer requires patience and steadfastness."
    ),
    cited: list[str] | None = None,
) -> ComposerOutput:
    return ComposerOutput(
        answer=answer,
        cited_chunk_ids=cited or ["ch_1"],
        prompt_tokens=10,
        completion_tokens=20,
        model_route_id="a5_compose_anthropic@2026-05-01.1",
        raw_text="<fake>",
    )


async def test_passes_on_supported_answer(pastoral_config) -> None:
    verifier = _verifier(pastoral_config)
    response = await verifier.verify(
        composer_output=_composer_output(),
        packet=_packet(),
        classified=_classified(),
        run_id="r1",
    )
    assert response.verification.passed is True
    assert response.handling == "answer"
    assert len(response.citations) == 1
    assert response.citations[0].chunk_id == "ch_1"


async def test_rejects_citation_to_absent_chunk(pastoral_config) -> None:
    verifier = _verifier(pastoral_config)
    response = await verifier.verify(
        composer_output=_composer_output(cited=["ch_does_not_exist"]),
        packet=_packet(),
        classified=_classified(),
        run_id="r2",
    )
    assert response.verification.passed is False
    assert response.handling == "insufficient_evidence"
    assert "unknown_chunk_ids" in (response.verification.failure_reason or "")


async def test_rejects_low_overlap_claim(pastoral_config) -> None:
    """If the model invents a claim that doesn't overlap any cited chunk, A6 must reject."""
    verifier = _verifier(pastoral_config)
    # The cited chunk talks about prayer, but the answer makes a completely off-topic claim.
    response = await verifier.verify(
        composer_output=_composer_output(
            answer=(
                "The liturgy begins with the great litany, followed by the antiphons "
                "and the small entrance with the gospel book held high."
            ),
            cited=["ch_1"],
        ),
        packet=_packet(),
        classified=_classified(),
        run_id="r3",
    )
    assert response.verification.passed is False
    assert "quote_overlap_below_threshold" in (
        response.verification.failure_reason or ""
    )


async def test_rejects_lineage_claim_without_evidence(pastoral_config) -> None:
    """Phase 1 has no approved edges, so any lineage claim must fail."""
    verifier = _verifier(pastoral_config)
    response = await verifier.verify(
        composer_output=_composer_output(
            answer=(
                "Saint Basil writes that prayer requires patience and steadfastness. "
                "Basil builds on Origen here."
            ),
            cited=["ch_1"],
        ),
        packet=_packet(),
        classified=_classified(),
        run_id="r4",
    )
    assert response.verification.passed is False
    assert "lineage_claim_without_evidence" in (
        response.verification.failure_reason or ""
    )


async def test_pastoral_filter_reject_marks_failure(pastoral_config) -> None:
    """If the composed answer matches a `reject_answer` pastoral filter rule, A6 fails."""
    verifier = _verifier(pastoral_config)
    # The pastoral_filters.yaml stub has `pf_electoral_guidance_en_001` matching "vote for".
    response = await verifier.verify(
        composer_output=_composer_output(
            answer="The Fathers say you should vote for the candidate of moral virtue.",
            cited=["ch_1"],
        ),
        packet=_packet(),
        classified=_classified(),
        run_id="r5",
    )
    assert response.verification.passed is False
    assert "pastoral_filter:pf_electoral_guidance_en_001" in (
        response.verification.failure_reason or ""
    )


async def test_judge_disabled_when_route_empty_f08(pastoral_config) -> None:
    """F-08: empty `active_model_route_verifier` disables the optional judge cleanly;
    deterministic checks still run."""
    verifier = _verifier(pastoral_config, judge_route_id="", judge_provider=None)
    response = await verifier.verify(
        composer_output=_composer_output(),
        packet=_packet(),
        classified=_classified(),
        run_id="r_f08",
    )
    assert response.verification.passed is True


async def test_judge_can_downgrade_green_to_yellow(pastoral_config) -> None:
    """An active judge that flags a soft inconsistency downgrades GREEN→YELLOW."""

    class StubJudge:
        async def generate_structured(self, **kwargs):  # type: ignore[no-untyped-def]
            from app.adapters.providers.base import StructuredResult

            return StructuredResult(
                data={"consistent": False, "reason": "drift"},
                raw_text="<fake>",
                prompt_tokens=5,
                completion_tokens=5,
                model_route_id=kwargs.get("route_id", "judge@1"),
                finish_reason="stop",
            )

    verifier = _verifier(
        pastoral_config,
        judge_route_id="verifier_judge_anthropic@1",
        judge_provider=StubJudge(),
    )
    green_packet = _packet()
    green_packet = green_packet.model_copy(update={"confidence_tier": "GREEN"})
    response = await verifier.verify(
        composer_output=_composer_output(),
        packet=green_packet,
        classified=_classified(),
        run_id="r_judge",
    )
    assert response.verification.passed is True
    assert response.confidence_tier == "YELLOW"


async def test_verified_response_validates_against_schema_shape(pastoral_config) -> None:
    """Round-trip the response through Pydantic to mirror the schema validation that the
    /query endpoint applies on serialization."""
    verifier = _verifier(pastoral_config)
    response = await verifier.verify(
        composer_output=_composer_output(),
        packet=_packet(),
        classified=_classified(),
        run_id="r_rt",
    )
    payload = response.model_dump(by_alias=True, mode="json")
    revived = type(response).model_validate(payload)
    assert revived.model_dump(by_alias=True, mode="json") == payload
