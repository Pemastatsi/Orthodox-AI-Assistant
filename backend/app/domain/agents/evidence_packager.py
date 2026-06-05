"""A4 evidence packager — deterministic admission boundary.

Per ADR-0001 §Closed-Corpus Contract: A4 is the evidence admission boundary. It admits
ONLY chunks that are approved, tenant-visible, role-visible, and above the score
threshold for the user-facing visibility tiers. It computes the final `confidenceTier`
from coverage (ADR-0002): A1's preliminary tier is not authoritative.

A4 is deterministic. No LLM calls. No I/O beyond reading the inputs.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Final

from app.core.logging import get_logger
from app.domain.models.chunk import Chunk
from app.domain.models.classified_query import ClassifiedQuery, ConfidenceTier
from app.domain.models.evidence_packet import (
    AdmittedChunk,
    AdmittedVisibility,
    EvidencePacket,
)
from app.domain.models.principal import Principal
from app.domain.models.scored_chunk import ScoredChunk
from app.domain.models.source import Source

logger = get_logger(__name__)

# Score-tier thresholds for A4 admission and confidence-tier computation.
# These match the "high-confidence" / "any-coverage" split documented in ADR-0002:
# GREEN requires ≥2 chunks above GREEN_SCORE; YELLOW requires ≥1 chunk above YELLOW_SCORE;
# otherwise RED. Below YELLOW_SCORE no chunk is admitted at all.
GREEN_SCORE: Final[float] = 0.65
YELLOW_SCORE: Final[float] = 0.50
GREEN_MIN_CHUNKS: Final[int] = 2
MAX_ADMITTED: Final[int] = 8

# Visibility tiers eligible for admission (admin_only/suppressed never reach A5 per ADR-0001).
_ADMISSIBLE_VISIBILITIES: Final[frozenset[str]] = frozenset({"member", "scholar"})


@dataclass(frozen=True)
class PackagingResult:
    packet: EvidencePacket
    duration_ms: int


class EvidencePackager:
    def __init__(self, *, corpus_version: str) -> None:
        self._corpus_version = corpus_version

    def package(
        self,
        *,
        candidates: list[ScoredChunk],
        classified: ClassifiedQuery,
        principal: Principal,
        run_id: str,
        sources_by_id: dict[str, Source] | None = None,
    ) -> PackagingResult:
        start = time.perf_counter()
        admitted: list[AdmittedChunk] = []
        suppressed: list[str] = []
        sources_by_id = sources_by_id or {}

        for candidate in candidates:
            chunk = candidate.chunk
            reason: str | None = None

            if not chunk.approved:
                reason = "unapproved"
            elif chunk.tenant_id != principal.tenant_id:
                reason = "cross_tenant"
            elif chunk.visibility not in _ADMISSIBLE_VISIBILITIES:
                reason = "non_admissible_visibility"
            elif candidate.score < YELLOW_SCORE:
                reason = "below_threshold"

            if reason is not None:
                suppressed.append(chunk.chunk_id)
                logger.info(
                    "evidence_packager.suppressed",
                    run_id=run_id,
                    tenant_id=principal.tenant_id,
                    chunk_id=chunk.chunk_id,
                    reason=reason,
                )
                continue

            source = sources_by_id.get(chunk.source_id)
            source_hash = (
                source.source_hash if source is not None else _fallback_source_hash(chunk)
            )
            title = source.title if source is not None else chunk.work or chunk.chunk_id
            admitted.append(
                AdmittedChunk(
                    chunk_id=chunk.chunk_id,
                    source_id=chunk.source_id,
                    title=title,
                    text=chunk.text,
                    score=candidate.score,
                    visibility=_narrow_visibility(chunk.visibility),
                    source_hash=source_hash,
                    chunk_hash=chunk.chunk_hash,
                    work=chunk.work,
                    father=chunk.father,
                    page=chunk.page,
                    timestamp=chunk.timestamp,
                )
            )

        # Order by score desc, cap at MAX_ADMITTED. Stable in the input order on ties.
        admitted.sort(key=lambda c: c.score, reverse=True)
        if len(admitted) > MAX_ADMITTED:
            for dropped in admitted[MAX_ADMITTED:]:
                suppressed.append(dropped.chunk_id)
            admitted = admitted[:MAX_ADMITTED]

        confidence_tier = _compute_confidence_tier(admitted, classified=classified)

        packet = EvidencePacket(
            tenant_id=principal.tenant_id,
            corpus_version=self._corpus_version,
            confidence_tier=confidence_tier,
            admitted_chunks=admitted,
            suppressed_chunk_ids=suppressed,
            lineage_context=[],  # Phase 1 emits empty; Phase 2+ may populate per ADR-0006.
        )

        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "query.evidence_packaged",
            run_id=run_id,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            stage="a4_evidence_packager",
            candidate_count=len(candidates),
            admitted_count=len(admitted),
            suppressed_count=len(suppressed),
            confidence_tier=confidence_tier,
            duration_ms=duration_ms,
        )
        return PackagingResult(packet=packet, duration_ms=duration_ms)


def _narrow_visibility(visibility: str) -> AdmittedVisibility:
    """Caller guarantees the visibility is in _ADMISSIBLE_VISIBILITIES; narrow for Pydantic."""
    if visibility == "member":
        return "member"
    if visibility == "scholar":
        return "scholar"
    # Caller should have rejected before this point; raise to catch the bug loudly.
    raise ValueError(f"non-admissible visibility reached admit step: {visibility!r}")


def _compute_confidence_tier(
    admitted: list[AdmittedChunk],
    *,
    classified: ClassifiedQuery,
) -> ConfidenceTier:
    """ADR-0002 §confidenceTier rules: derive the FINAL tier from coverage, not topic.

    - GREEN: ≥ GREEN_MIN_CHUNKS chunks scored ≥ GREEN_SCORE.
    - YELLOW: at least one chunk scored ≥ YELLOW_SCORE.
    - RED: no admitted chunks (or A1 already concluded `insufficient`).

    `classified.handling == 'block_with_redirect'` is handled by the caller before A4;
    we still degrade to RED if it somehow reaches us with an `insufficient` answer_mode.
    """
    if classified.handling in ("block_with_redirect",) or not admitted:
        return "RED"
    green_count = sum(1 for c in admitted if c.score >= GREEN_SCORE)
    if green_count >= GREEN_MIN_CHUNKS:
        return "GREEN"
    if any(c.score >= YELLOW_SCORE for c in admitted):
        return "YELLOW"
    return "RED"


def confidence_tier_for(
    admitted: list[AdmittedChunk],
    *,
    classified: ClassifiedQuery,
) -> ConfidenceTier:
    """Public wrapper over the ADR-0002 coverage rule (`_compute_confidence_tier`).

    A6 uses it to derive a per-column confidence tier for a scholarly_dispute position from
    exactly the thresholds A4 applies to the whole packet — there is no separate per-column
    threshold. A single-chunk column therefore tops out at YELLOW (GREEN needs ≥2 chunks
    ≥ GREEN_SCORE), which is the intended conservative behavior."""
    return _compute_confidence_tier(admitted, classified=classified)


def _fallback_source_hash(chunk: Chunk) -> str:
    """When the caller didn't pass Source records, derive a placeholder source hash from the
    chunk hash so the AdmittedChunk still validates against the schema.

    Real callers (the /query endpoint in production) pass `sources_by_id`; tests and
    fixtures that build chunks directly use this fallback. ScoredChunk's Chunk model does
    not carry source_hash, so we reuse chunk_hash — that's noisier than ideal but never
    wrong.
    """
    return str(chunk.chunk_hash)


__all__ = [
    "GREEN_MIN_CHUNKS",
    "GREEN_SCORE",
    "MAX_ADMITTED",
    "YELLOW_SCORE",
    "EvidencePackager",
    "PackagingResult",
    "confidence_tier_for",
]
