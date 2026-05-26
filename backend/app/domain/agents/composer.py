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

from app.adapters.providers.base import LLMProvider, StructuredResult
from app.core.errors import ProviderInvalidResponseError, ProviderRefusedError
from app.core.logging import get_logger
from app.domain.models.classified_query import ClassifiedQuery
from app.domain.models.evidence_packet import EvidencePacket
from app.domain.prompts.composer_a5 import build_messages, composer_output_schema

logger = get_logger(__name__)


@dataclass(frozen=True)
class ComposerOutput:
    answer: str
    cited_chunk_ids: list[str]
    prompt_tokens: int
    completion_tokens: int
    model_route_id: str
    raw_text: str


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

        result: StructuredResult = await self._provider.generate_structured(
            messages=messages,
            schema=composer_output_schema(),
            route_id=self._model_route_id,
            tenant_id=packet.tenant_id,
            run_id=run_id,
            max_output_tokens=self._max_output_tokens,
        )

        if result.finish_reason == "refusal":
            raise ProviderRefusedError("A5 composer refused")

        answer = result.data.get("answer")
        cited_raw = result.data.get("citedChunkIds")
        if not isinstance(answer, str) or not isinstance(cited_raw, list):
            raise ProviderInvalidResponseError(
                "A5 payload missing answer / citedChunkIds keys"
            )
        cited_chunk_ids = [str(c) for c in cited_raw if isinstance(c, str)]

        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "query.composed",
            run_id=run_id,
            tenant_id=packet.tenant_id,
            stage="a5_composer",
            answer_length=len(answer),
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
        )


__all__ = ["Composer", "ComposerOutput"]
