"""Build user-facing `Citation` objects from `AdmittedChunk` entries.

Per `verified-response.schema.json`, Citation carries `corpusOrigin` (`tenant` or
`starter_corpus`). Phase 1 only serves the tenant's own corpus, so the default is
`tenant`; the optional `corpus_origin_by_source_id` map lets a future caller plumb
real provenance through when starter-corpus support lands in Phase 2.
"""

from __future__ import annotations

from collections.abc import Mapping

import ulid

from app.domain.models.evidence_packet import AdmittedChunk
from app.domain.models.verified_response import Citation, CorpusOrigin


def new_citation_id() -> str:
    return f"cit_{ulid.new()!s}"


def format_citation(
    chunk: AdmittedChunk,
    *,
    citation_id: str | None = None,
    corpus_origin: CorpusOrigin = "tenant",
    quote: str | None = None,
) -> Citation:
    return Citation(
        citation_id=citation_id or new_citation_id(),
        chunk_id=chunk.chunk_id,
        source_id=chunk.source_id,
        title=chunk.title,
        source_hash=chunk.source_hash,
        chunk_hash=chunk.chunk_hash,
        corpus_origin=corpus_origin,
        work=chunk.work,
        father=chunk.father,
        page=chunk.page,
        timestamp=chunk.timestamp,
        quote=quote,
    )


def format_citations(
    chunks: list[AdmittedChunk],
    *,
    corpus_origin_by_source_id: Mapping[str, CorpusOrigin] | None = None,
) -> list[Citation]:
    origin_map = corpus_origin_by_source_id or {}
    return [
        format_citation(
            chunk,
            corpus_origin=origin_map.get(chunk.source_id, "tenant"),
        )
        for chunk in chunks
    ]


__all__ = ["format_citation", "format_citations", "new_citation_id"]
