"""ScoredChunk model — `docs/schemas/scored-chunk.schema.json`."""

from __future__ import annotations

from pydantic import Field

from app.domain.models._base import WireModel
from app.domain.models.chunk import Chunk


class ScoredChunk(WireModel):
    chunk: Chunk
    score: float = Field(ge=0.0, le=1.0)
    rerank_score: float | None = Field(default=None, ge=0.0, le=1.0)
