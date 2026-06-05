"""A5 closed-corpus composer.

Receives an `EvidencePacket` and produces an answer plus the list of `chunkId`s the model
actually used to support it. A5 NEVER receives external knowledge or non-evidence content;
the prompt is built from the packet alone. A5 returns structured output (`generate_structured`)
so A6 can map cited chunks back to admitted chunks deterministically.

Per `provider-interface.md` §Refusal Handling: refusals raise `ProviderRefusedError` which
the caller turns into a bounded `insufficient_evidence` fallback. A5 never returns a
"sanitized refusal" string to the user.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from app.adapters.providers.base import LLMProvider, StructuredResult
from app.core.errors import ProviderInvalidResponseError, ProviderRefusedError
from app.core.logging import get_logger
from app.domain.models.classified_query import ClassifiedQuery
from app.domain.models.evidence_packet import EvidencePacket
from app.domain.prompts.composer_a5 import (
    build_messages,
    composer_dispute_output_schema,
    composer_output_schema,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class ComposerPosition:
    """One competing position emitted by A5 for a scholarly_dispute (pre-verification).

    `cited_chunk_ids` are the chunks supporting THIS position only; A6 verifies each
    position's thesis against these chunks independently."""

    name: str
    thesis: str
    cited_chunk_ids: list[str]


@dataclass(frozen=True)
class ComposerOutput:
    answer: str
    cited_chunk_ids: list[str]
    prompt_tokens: int
    completion_tokens: int
    model_route_id: str
    raw_text: str
    # Populated only for scholarly_dispute; None for every other answer mode. When set, A6
    # verifies each position independently and emits `VerifiedResponse.positions`. `answer`
    # is then empty — the user-facing dispute lede is a fixed constant supplied by A6.
    positions: list[ComposerPosition] | None = None


class Composer:
    def __init__(
        self,
        *,
        provider: LLMProvider,
        prompt_version: str,
        model_route_id: str,
        max_output_tokens: int = 1024,
    ) -> None:
        self._provider = provider
        self._prompt_version = prompt_version
        self._model_route_id = model_route_id
        self._max_output_tokens = max_output_tokens

    async def compose(
        self,
        *,
        packet: EvidencePacket,
        classified: ClassifiedQuery,
        run_id: str,
    ) -> ComposerOutput:
        start = time.perf_counter()
        messages = build_messages(packet=packet, classified=classified)
        is_dispute = classified.answer_mode == "scholarly_dispute"
        schema = (
            composer_dispute_output_schema() if is_dispute else composer_output_schema()
        )

        result: StructuredResult = await self._provider.generate_structured(
            messages=messages,
            schema=schema,
            route_id=self._model_route_id,
            tenant_id=packet.tenant_id,
            run_id=run_id,
            max_output_tokens=self._max_output_tokens,
        )

        if result.finish_reason == "refusal":
            raise ProviderRefusedError("A5 composer refused")

        positions: list[ComposerPosition] | None
        if is_dispute:
            answer = ""
            parsed = _parse_positions(result.data)
            positions = parsed
            # Order-preserving union of every column's cited chunks (logging + usage only;
            # A6 re-derives the per-column scoping from each position's own ids).
            cited_chunk_ids = list(
                dict.fromkeys(cid for p in parsed for cid in p.cited_chunk_ids)
            )
        else:
            positions = None
            answer_raw = result.data.get("answer")
            cited_raw = result.data.get("citedChunkIds")
            if not isinstance(answer_raw, str) or not isinstance(cited_raw, list):
                raise ProviderInvalidResponseError(
                    "A5 payload missing answer / citedChunkIds keys"
                )
            answer = answer_raw
            cited_chunk_ids = [str(c) for c in cited_raw if isinstance(c, str)]

        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "query.composed",
            run_id=run_id,
            tenant_id=packet.tenant_id,
            stage="a5_composer",
            answer_mode=classified.answer_mode,
            answer_length=len(answer),
            position_count=len(positions) if positions is not None else 0,
            citation_count=len(cited_chunk_ids),
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            model_route_id=self._model_route_id,
            prompt_version=self._prompt_version,
            duration_ms=duration_ms,
        )
        return ComposerOutput(
            answer=answer,
            cited_chunk_ids=cited_chunk_ids,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            model_route_id=result.model_route_id or self._model_route_id,
            raw_text=result.raw_text,
            positions=positions,
        )


def _parse_positions(data: dict[str, Any]) -> list[ComposerPosition]:
    """Parse the dispute structured payload into `ComposerPosition`s.

    Raises `ProviderInvalidResponseError` (→ bounded fallback in the caller) on any
    structural defect, so a malformed dispute payload never reaches the user."""
    raw = data.get("positions")
    if not isinstance(raw, list) or not raw:
        raise ProviderInvalidResponseError("A5 dispute payload missing positions")
    positions: list[ComposerPosition] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ProviderInvalidResponseError("A5 dispute position is not an object")
        name = item.get("name")
        thesis = item.get("thesis")
        cited = item.get("citedChunkIds")
        if (
            not isinstance(name, str)
            or not isinstance(thesis, str)
            or not isinstance(cited, list)
        ):
            raise ProviderInvalidResponseError(
                "A5 dispute position missing name / thesis / citedChunkIds"
            )
        cited_ids = [str(c) for c in cited if isinstance(c, str)]
        if not cited_ids:
            raise ProviderInvalidResponseError("A5 dispute position has no citedChunkIds")
        positions.append(
            ComposerPosition(name=name, thesis=thesis, cited_chunk_ids=cited_ids)
        )
    return positions


__all__ = ["Composer", "ComposerOutput", "ComposerPosition"]
