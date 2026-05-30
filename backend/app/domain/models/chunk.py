"""Chunk model — `docs/schemas/chunk.schema.json`."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.domain.models._base import WireModel

Visibility = Literal["member", "scholar", "admin_only", "suppressed"]
ChunkLanguage = Literal["en", "el", "mixed"]


class Chunk(WireModel):
    chunk_id: str
    source_id: str
    tenant_id: str
    text: str = Field(min_length=1)
    chunk_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    approved: bool = False
    visibility: Visibility
    father: str | None = None
    work: str | None = None
    page: str | None = None
    timestamp: str | None = None
    language: ChunkLanguage = "en"
    categories: list[str] = Field(default_factory=list)
    section_path: list[str] = Field(default_factory=list)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    parent_chunk_id: str | None = None
    context_prefix: str | None = Field(default=None, max_length=200)
    embedding_model: str
    embedding_dimension: int = Field(ge=1)
    corpus_version: str
    review_note: str | None = None
    created_at: datetime
