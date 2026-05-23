"""Source model — `docs/schemas/source.schema.json`."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.domain.models._base import WireModel

SourceType = Literal["pdf", "txt", "md", "docx"]
SourceLanguage = Literal["en", "el", "mixed"]
DigitizationProvenance = Literal[
    "manuscript",
    "manuscript_facsimile",
    "critical_edition",
    "scholarly_edition",
    "paperback",
    "hardcover",
    "publisher_pdf",
    "scanned_pdf",
    "web_html",
    "born_digital",
    "audio_transcript",
    "video_transcript",
    "unknown",
]


class Source(WireModel):
    source_id: str
    tenant_id: str
    title: str = Field(min_length=1)
    source_type: SourceType
    source_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    extraction_method: str
    approved: bool = False
    corpus_version: str
    created_at: datetime
    father: str | None = None
    work: str | None = None
    language: SourceLanguage = "en"
    corpus_origin: str | None = None
    digitization_provenance: DigitizationProvenance | None = None
    approval_note: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
