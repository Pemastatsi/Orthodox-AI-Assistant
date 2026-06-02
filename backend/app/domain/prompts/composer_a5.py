"""A5 composer prompt — closed-corpus answer composition.

The prompt text is loaded from the `/prompts` registry
(`prompts/a5_composer/en/<version>.j2`), selected by `Settings.active_prompt_version_a5`. The
composer receives ONLY the
`EvidencePacket.admittedChunks` (plus the user's reframed query when present). No
tenant config, no model knowledge primers, no chain-of-thought, no external corpora.
See `AGENTS.md §Closed-Corpus Rules` and ADR-0001.
"""

from __future__ import annotations

import json
from typing import Any

from app.adapters.providers.base import ChatMessage
from app.core.config import get_settings
from app.domain.models.classified_query import ClassifiedQuery
from app.domain.models.evidence_packet import EvidencePacket
from app.domain.services.prompt_loader import load_prompt

_STAGE, _LANGUAGE = "a5_composer", "en"
# A5 system prompt — canonical text lives in the /prompts registry (GS-3), not inline;
# selected by Settings.active_prompt_version_a5. See /prompts/README.md.
_PROMPT_VERSION = get_settings().active_prompt_version_a5
_SYSTEM_PROMPT = load_prompt(_STAGE, _LANGUAGE, _PROMPT_VERSION.split("@", 1)[-1])


def composer_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["answer", "citedChunkIds"],
        "properties": {
            "answer": {"type": "string", "minLength": 1},
            "citedChunkIds": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "minItems": 0,
            },
        },
    }


def _serialize_admitted_chunks(packet: EvidencePacket) -> list[dict[str, Any]]:
    """Project AdmittedChunk to the minimal payload the composer needs.

    We intentionally exclude `score` and integrity hashes from the LLM-visible payload —
    they are not useful for composition and only add token cost and prompt-injection
    surface.
    """
    return [
        {
            "chunkId": chunk.chunk_id,
            "title": chunk.title,
            "work": chunk.work,
            "father": chunk.father,
            "page": chunk.page,
            "timestamp": chunk.timestamp,
            "text": chunk.text,
        }
        for chunk in packet.admitted_chunks
    ]


def build_messages(
    *,
    packet: EvidencePacket,
    classified: ClassifiedQuery,
) -> list[ChatMessage]:
    """Build the (system, user) message pair for the A5 structured call.

    The user query passed to the LLM is `classified.reframed_query ?? classified.raw_query`,
    matching ADR-0007's semantic-query invariant. The model never sees the raw query when
    the analyzer reframed it.
    """
    user_question = classified.reframed_query or classified.raw_query
    evidence = _serialize_admitted_chunks(packet)
    user_payload = {
        "question": user_question,
        "answerMode": classified.answer_mode,
        "confidenceTier": packet.confidence_tier,
        "evidenceChunks": evidence,
    }
    return [
        ChatMessage(role="system", content=_SYSTEM_PROMPT),
        ChatMessage(role="user", content=json.dumps(user_payload, ensure_ascii=False)),
    ]


__all__ = ["build_messages", "composer_output_schema"]
