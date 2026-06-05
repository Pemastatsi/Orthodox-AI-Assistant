"""A6 verifier.

Deterministic checks run unconditionally:

1. Every chunkId returned by A5 must exist in the EvidencePacket's admitted chunks.
2. Every claim (sentence-ish slice) in the answer must overlap one of the cited chunks
   at `quote_overlap >= QUOTE_OVERLAP_THRESHOLD` (0.70). See
   `docs/contracts/quote-overlap-algorithm.md`.
3. Lineage-style claims ("X quotes Y", "X builds on Y", ...) are rejected unless an
   approved edge in `EvidencePacket.lineage_context` supports them. Phase 1 always has
   empty lineage_context (ADR-0006), so any lineage claim fails.
4. Pastoral-filter rules (`config/pastoral_filters.yaml`) — first `reject_answer` match
   fails verification with `failure_reason = "pastoral_filter:" + rule_id`.

The optional certified-judge step (per ADR-0004) runs ONLY when
`settings.active_model_route_verifier` is non-empty (F-08). It may DOWNGRADE GREEN→YELLOW
on a soft inconsistency but cannot upgrade or override a deterministic miss.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.adapters.providers.base import LLMProvider
from app.core.config import get_settings
from app.core.errors import ProviderRefusedError
from app.core.logging import get_logger
from app.domain.agents.composer import ComposerOutput
from app.domain.agents.evidence_packager import confidence_tier_for
from app.domain.models.classified_query import ClassifiedQuery, ConfidenceTier, Handling
from app.domain.models.evidence_packet import AdmittedChunk, EvidencePacket
from app.domain.models.verified_response import (
    Citation,
    Position,
    Reframing,
    Verification,
    VerifiedResponse,
    VerifiedResponseUsage,
)
from app.domain.services.bounded_fallback import build_bounded_fallback
from app.domain.services.citation_formatter import format_citation
from app.domain.services.prompt_loader import load_prompt, registry_version
from app.domain.services.quote_overlap import (
    QUOTE_OVERLAP_THRESHOLD,
    quote_overlap,
)
from app.domain.services.safety_config import PastoralConfig, iter_pastoral_matches

logger = get_logger(__name__)

# Lineage-claim trigger patterns. ANY hit fails verification because Phase 1 has no
# approved edges (ADR-0006 §Rules item 6, 7).
_LINEAGE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:quotes|cites|references)\s+\w+", re.IGNORECASE),
    re.compile(r"\bbuilds on\b", re.IGNORECASE),
    re.compile(r"\bis a translation of\b", re.IGNORECASE),
    re.compile(r"\bcontrasts with\b", re.IGNORECASE),
    re.compile(r"\bsame passage as\b", re.IGNORECASE),
)

# A6 optional consistency-judge system prompt — canonical text lives in the /prompts
# registry (GS-3), selected by Settings.active_verifier_version. The judge is disabled by
# default (F-08); loaded at import so a misconfigured registry fails fast. See /prompts/README.md.
_JUDGE_SYSTEM_PROMPT = load_prompt(
    "a6_judge", "en", registry_version(get_settings().active_verifier_version)
)

# Tier severity for picking the most-conservative top-level tier across dispute columns.
_TIER_ORDER: dict[ConfidenceTier, int] = {"RED": 0, "YELLOW": 1, "GREEN": 2}

# Fixed, non-model-authored framing for a scholarly_dispute answer. A5 composes the
# positions; this top-level lede is a reviewed constant, so the user-facing framing can
# never phrase a genuine dispute as a consensus. Count-agnostic (holds for 2+ positions).
_DISPUTE_FRAMING: str = (
    "The approved library surfaces more than one position on this question. They are "
    "presented side by side below; the library does not adjudicate between them."
)


@dataclass(frozen=True)
class VerifierConfig:
    verifier_version: str
    schema_version: str
    judge_route_id: str = ""  # empty disables the optional judge (F-08)


class Verifier:
    def __init__(
        self,
        *,
        pastoral_config: PastoralConfig,
        config: VerifierConfig,
        judge_provider: LLMProvider | None = None,
    ) -> None:
        self._pastoral = pastoral_config
        self._config = config
        self._judge = judge_provider if config.judge_route_id else None

    async def verify(
        self,
        *,
        composer_output: ComposerOutput,
        packet: EvidencePacket,
        classified: ClassifiedQuery,
        run_id: str,
        original_query: str | None = None,
        reframed_query: str | None = None,
    ) -> VerifiedResponse:
        start = time.perf_counter()
        admitted_by_id = {c.chunk_id: c for c in packet.admitted_chunks}

        # Scholarly-dispute answers are composed per column; verify each position
        # independently and assemble VerifiedResponse.positions (fail-closed). See
        # _verify_dispute.
        if composer_output.positions is not None:
            return self._verify_dispute(
                composer_output=composer_output,
                packet=packet,
                classified=classified,
                run_id=run_id,
                admitted_by_id=admitted_by_id,
                original_query=original_query,
                reframed_query=reframed_query,
                start=start,
            )

        # Single-answer path: the deterministic checks run over the one claim set
        # (citation existence, pastoral filter, lineage, quote-overlap).
        passed, failure_reason, cited_chunks = self._verify_claim_set(
            answer=composer_output.answer,
            cited_chunk_ids=composer_output.cited_chunk_ids,
            packet=packet,
            admitted_by_id=admitted_by_id,
            run_id=run_id,
        )
        if not passed:
            return self._reject(
                run_id=run_id,
                composer_output=composer_output,
                failure_reason=failure_reason or "verification_failed",
                original_query=original_query,
                reframed_query=reframed_query,
            )

        # Optional certified judge. Skipped when judge_route_id is empty (F-08).
        final_tier = packet.confidence_tier
        if self._judge is not None:
            try:
                downgrade = await self._maybe_downgrade(
                    composer_output=composer_output,
                    packet=packet,
                    run_id=run_id,
                )
            except ProviderRefusedError:
                downgrade = False
            if downgrade and final_tier == "GREEN":
                final_tier = "YELLOW"
                logger.info(
                    "verifier.judge_downgrade",
                    run_id=run_id,
                    tenant_id=packet.tenant_id,
                    from_tier="GREEN",
                    to_tier="YELLOW",
                )

        citations = [format_citation(chunk) for chunk in cited_chunks]
        response = self._build_response(
            run_id=run_id,
            answer=composer_output.answer,
            citations=citations,
            confidence_tier=final_tier,
            handling=_handling_from_classified(classified),
            composer_output=composer_output,
            verifier_passed=True,
            failure_reason=None,
            original_query=original_query,
            reframed_query=reframed_query,
        )
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "query.verified",
            run_id=run_id,
            tenant_id=packet.tenant_id,
            stage="a6_verifier",
            verifier_passed=True,
            citation_count=len(citations),
            confidence_tier=final_tier,
            judge_active=self._judge is not None,
            duration_ms=duration_ms,
        )
        return response

    def _verify_claim_set(
        self,
        *,
        answer: str,
        cited_chunk_ids: list[str],
        packet: EvidencePacket,
        admitted_by_id: dict[str, AdmittedChunk],
        run_id: str,
    ) -> tuple[bool, str | None, list[AdmittedChunk]]:
        """Run the four deterministic checks over a single claim set.

        Returns ``(passed, failure_reason, cited_chunks)``. Shared by the single-answer path
        and every column of the scholarly-dispute path, so a dispute column is held to
        exactly the same citation-existence / pastoral / lineage / quote-overlap bar as a
        normal answer — and a column can only cite chunks A4 admitted."""
        # 1. Citation existence — any cited chunkId A4 did not admit fails immediately.
        unknown_ids = [cid for cid in cited_chunk_ids if cid not in admitted_by_id]
        if unknown_ids:
            return False, f"unknown_chunk_ids:{','.join(sorted(unknown_ids))}", []
        cited_chunks = [admitted_by_id[cid] for cid in cited_chunk_ids]

        # 2. Pastoral-filter rules — first reject_answer match fails verification.
        for match in iter_pastoral_matches(answer, self._pastoral):
            if match.action == "reject_answer":
                return False, f"pastoral_filter:{match.rule_id}", cited_chunks
            logger.info(
                "verifier.pastoral_warn",
                run_id=run_id,
                tenant_id=packet.tenant_id,
                rule_id=match.rule_id,
            )

        # 3. Lineage claims — Phase 1 has no approved edges, so any lineage claim fails.
        lineage_hit = _detect_lineage_claim(answer)
        if lineage_hit is not None and not packet.lineage_context:
            return False, f"lineage_claim_without_evidence:{lineage_hit}", cited_chunks

        # 4. Quote-overlap — every non-trivial claim must overlap a cited chunk at threshold.
        overlap_details: list[dict[str, Any]] = []
        unsupported_claims: list[str] = []
        for claim in _split_claims(answer):
            if not _is_meaningful_claim(claim):
                continue
            best_ratio = 0.0
            best_chunk_id: str | None = None
            for chunk in cited_chunks:
                ratio = quote_overlap(claim, chunk.text)
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_chunk_id = chunk.chunk_id
            overlap_details.append(
                {
                    "claim": claim,
                    "best_ratio": round(best_ratio, 4),
                    "best_chunk_id": best_chunk_id,
                }
            )
            if best_ratio < QUOTE_OVERLAP_THRESHOLD:
                unsupported_claims.append(claim)
        if unsupported_claims:
            logger.info(
                "verifier.unsupported_claims",
                run_id=run_id,
                tenant_id=packet.tenant_id,
                count=len(unsupported_claims),
                details=overlap_details,
            )
            return (
                False,
                f"quote_overlap_below_threshold:{len(unsupported_claims)}",
                cited_chunks,
            )
        return True, None, cited_chunks

    def _verify_dispute(
        self,
        *,
        composer_output: ComposerOutput,
        packet: EvidencePacket,
        classified: ClassifiedQuery,
        run_id: str,
        admitted_by_id: dict[str, AdmittedChunk],
        original_query: str | None,
        reframed_query: str | None,
        start: float,
    ) -> VerifiedResponse:
        """Verify each competing position independently and assemble the dispute response.

        Fail-closed: if ANY position fails the deterministic checks, or fewer than two
        positions survive, the whole response degrades to a bounded insufficient-evidence
        fallback — a half-verified or one-sided "dispute" is never shown. Citations are
        scoped per column (each Position.citation_ids lists only that column's chunks); the
        per-column verifier's citation-existence check makes cross-column citation
        impossible. The optional A6 judge is not run on the dispute path (off by default;
        per-column tiers are derived deterministically from coverage)."""
        assert composer_output.positions is not None  # guaranteed by caller
        citation_by_chunk: dict[str, Citation] = {}
        union_citations: list[Citation] = []
        positions_out: list[Position] = []
        column_tiers: list[ConfidenceTier] = []

        for pos in composer_output.positions:
            passed, failure_reason, cited_chunks = self._verify_claim_set(
                answer=pos.thesis,
                cited_chunk_ids=pos.cited_chunk_ids,
                packet=packet,
                admitted_by_id=admitted_by_id,
                run_id=run_id,
            )
            if not passed:
                return self._reject(
                    run_id=run_id,
                    composer_output=composer_output,
                    failure_reason=f"dispute_position:{pos.name}:{failure_reason}",
                    original_query=original_query,
                    reframed_query=reframed_query,
                )
            column_citation_ids: list[str] = []
            for chunk in cited_chunks:
                citation = citation_by_chunk.get(chunk.chunk_id)
                if citation is None:
                    citation = format_citation(chunk)
                    citation_by_chunk[chunk.chunk_id] = citation
                    union_citations.append(citation)
                column_citation_ids.append(citation.citation_id)
            tier = confidence_tier_for(cited_chunks, classified=classified)
            column_tiers.append(tier)
            positions_out.append(
                Position(
                    name=pos.name,
                    thesis=pos.thesis,
                    citation_ids=column_citation_ids,
                    confidence_tier=tier,
                )
            )

        # A "dispute" with fewer than two verified positions is not a dispute — fail closed.
        if len(positions_out) < 2:
            return self._reject(
                run_id=run_id,
                composer_output=composer_output,
                failure_reason=f"dispute_insufficient_positions:{len(positions_out)}",
                original_query=original_query,
                reframed_query=reframed_query,
            )

        top_tier = min(column_tiers, key=lambda t: _TIER_ORDER[t])
        was_reframed = reframed_query is not None and reframed_query != original_query
        response = VerifiedResponse(
            answer=_DISPUTE_FRAMING,
            confidence_tier=top_tier,
            handling=_handling_from_classified(classified),
            citations=union_citations,
            verification=Verification(
                passed=True,
                checked_at=datetime.now(UTC),
                verifier_version=self._config.verifier_version,
                failure_reason=None,
            ),
            reframing=Reframing(
                was_reframed=was_reframed,
                original_query=original_query if was_reframed else None,
                reframed_query=reframed_query if was_reframed else None,
                disclosure_text=None,
            ),
            usage=VerifiedResponseUsage(
                served_answer_count=1,
                fresh_model_run_count=1,
                model_route_id=composer_output.model_route_id,
                prompt_tokens=composer_output.prompt_tokens,
                completion_tokens=composer_output.completion_tokens,
            ),
            served_from_cache=False,
            schema_version=self._config.schema_version,
            run_id=run_id,
            positions=positions_out,
        )
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "query.verified",
            run_id=run_id,
            tenant_id=packet.tenant_id,
            stage="a6_verifier",
            mode="scholarly_dispute",
            verifier_passed=True,
            position_count=len(positions_out),
            citation_count=len(union_citations),
            confidence_tier=top_tier,
            judge_active=False,
            duration_ms=duration_ms,
        )
        return response

    def _reject(
        self,
        *,
        run_id: str,
        composer_output: ComposerOutput,
        failure_reason: str,
        original_query: str | None,
        reframed_query: str | None,
    ) -> VerifiedResponse:
        logger.info(
            "verifier.rejected",
            run_id=run_id,
            failure_reason=failure_reason,
            model_route_id=composer_output.model_route_id,
        )
        return build_bounded_fallback(
            case_class="a6_reject",
            handling="insufficient_evidence",
            run_id=run_id,
            model_route_id=composer_output.model_route_id,
            confidence_tier="RED",
            verifier_version=self._config.verifier_version,
            verifier_passed=False,
            schema_version=self._config.schema_version,
            failure_reason=failure_reason,
            original_query=original_query,
            reframed_query=reframed_query,
        )

    async def _maybe_downgrade(
        self,
        *,
        composer_output: ComposerOutput,
        packet: EvidencePacket,
        run_id: str,
    ) -> bool:
        """Optional certified low-cost consistency judge (ADR-0004). Returns True iff the
        judge says the answer drifts from the evidence enough to warrant a GREEN→YELLOW
        downgrade. The judge can NEVER upgrade or override a deterministic miss."""
        assert self._judge is not None  # checked by caller
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["consistent"],
            "properties": {
                "consistent": {"type": "boolean"},
                "reason": {"type": "string"},
            },
        }
        from app.adapters.providers.base import ChatMessage

        evidence_text = "\n\n".join(
            f"[{c.chunk_id}] {c.text}" for c in packet.admitted_chunks
        )
        messages = [
            ChatMessage(
                role="system",
                content=_JUDGE_SYSTEM_PROMPT,
            ),
            ChatMessage(
                role="user",
                content=f"EVIDENCE:\n{evidence_text}\n\nANSWER:\n{composer_output.answer}",
            ),
        ]
        result = await self._judge.generate_structured(
            messages=messages,
            schema=schema,
            route_id=self._config.judge_route_id,
            tenant_id=packet.tenant_id,
            run_id=run_id,
            max_output_tokens=128,
        )
        return not bool(result.data.get("consistent", True))

    def _build_response(
        self,
        *,
        run_id: str,
        answer: str,
        citations: list[Citation],
        confidence_tier: ConfidenceTier,
        handling: Handling,
        composer_output: ComposerOutput,
        verifier_passed: bool,
        failure_reason: str | None,
        original_query: str | None,
        reframed_query: str | None,
    ) -> VerifiedResponse:
        was_reframed = (
            reframed_query is not None and reframed_query != original_query
        )
        return VerifiedResponse(
            answer=answer,
            confidence_tier=confidence_tier,
            handling=handling,
            citations=citations,
            verification=Verification(
                passed=verifier_passed,
                checked_at=datetime.now(UTC),
                verifier_version=self._config.verifier_version,
                failure_reason=failure_reason,
            ),
            reframing=Reframing(
                was_reframed=was_reframed,
                original_query=original_query if was_reframed else None,
                reframed_query=reframed_query if was_reframed else None,
                disclosure_text=None,
            ),
            usage=VerifiedResponseUsage(
                served_answer_count=1,
                fresh_model_run_count=1,
                model_route_id=composer_output.model_route_id,
                prompt_tokens=composer_output.prompt_tokens,
                completion_tokens=composer_output.completion_tokens,
            ),
            served_from_cache=False,
            schema_version=self._config.schema_version,
            run_id=run_id,
        )


def _split_claims(answer: str) -> list[str]:
    """Split an answer into approximate claims for per-claim overlap checks.

    Sentence-final punctuation (`. ! ?` followed by whitespace or end-of-string) is the
    boundary. Short answers (no sentence punctuation) become one claim.
    """
    pieces = re.split(r"(?<=[.!?])\s+", answer.strip())
    return [p.strip() for p in pieces if p.strip()]


def _is_meaningful_claim(claim: str) -> bool:
    # Strip and check that there's at least one token. Single-word or empty fragments
    # often appear because of split artifacts and should not be checked individually —
    # they're absorbed into the adjacent claim semantically.
    return len(claim.split()) >= 3


def _detect_lineage_claim(answer: str) -> str | None:
    for pattern in _LINEAGE_PATTERNS:
        match = pattern.search(answer)
        if match:
            return match.group(0)
    return None


def _handling_from_classified(classified: ClassifiedQuery) -> Handling:
    """Map the A1 handling to the user-facing answer handling. A6 only reaches this point
    when the classification was a positive answer or a reframe; bounded handlings exited
    earlier. Defaults to `answer` if A1 hinted at something else (defense-in-depth)."""
    if classified.handling in (
        "answer",
        "answer_with_disclaimer",
        "reframe_to_teaching",
    ):
        return classified.handling
    return "answer"


__all__ = ["Verifier", "VerifierConfig"]
