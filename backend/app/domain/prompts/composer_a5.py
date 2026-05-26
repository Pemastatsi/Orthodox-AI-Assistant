"""A5 composer prompt — closed-corpus answer composition.

Versioned via `Settings.active_prompt_version_a5`. The composer receives ONLY the
`EvidencePacket.admittedChunks` (plus the user's reframed query when present). No
tenant config, no model knowledge primers, no chain-of-thought, no external corpora.
See `AGENTS.md §Closed-Corpus Rules` and ADR-0001.
"""

from __future__ import annotations

import json
from typing import Any

from app.adapters.providers.base import ChatMessage
from app.domain.models.classified_query import ClassifiedQuery
from app.domain.models.evidence_packet import EvidencePacket

_SYSTEM_PROMPT = """\
You are the Orthodox AI Assistant's closed-corpus composer. You answer the user's question
using ONLY the evidence chunks provided below. You MUST follow these rules:

1. You may only state claims that are directly supported by one or more of the provided
   chunks. If the chunks do not support an answer, return an `answer` that explicitly says
   so in one or two sentences. NEVER use general knowledge, training data, or anything
   outside the provided chunks.
2. Every substantive claim in your answer must be supportable by one of the cited chunks.
   In `citedChunkIds` you list the `chunkId`s you actually used. List every chunk you relied
   on; do not list chunks you did not use.
3. Do not invent or attribute statements. Do not quote a Father without anchoring the quote
   to a chunk in `citedChunkIds`.
4. Do not claim lineage relations ("X quotes Y", "X builds on Y", "X is a translation of
   Y") unless the chunks themselves contain that relation in their text. Lineage edges are
   not provided as separate metadata in Phase 1.
5. Do not give personal advice, medical diagnosis, or electoral guidance. Present the
   library's teaching only.
6. Keep the answer concise (target 3 short paragraphs at most). Use plain prose.
7. Output a JSON object with exactly two keys: `answer` (string) and `citedChunkIds`
   (array of strings, each appearing in the provided evidence).
"""


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
