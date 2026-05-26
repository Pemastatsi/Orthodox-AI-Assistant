"""EvidencePacket model — `docs/schemas/evidence-packet.schema.json` (A4 output)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.domain.models._base import WireModel

EvidenceConfidenceTier = Literal["GREEN", "YELLOW", "RED"]
# Per evidence-packet.schema.json, admitted evidence is restricted to user-facing tiers.
# admin_only and suppressed chunks are never admittable (ADR-0001).
AdmittedVisibility = Literal["member", "scholar"]


class AdmittedChunk(WireModel):
    chunk_id: str
    source_id: str
    title: str
    text: str
    score: float = Field(ge=0.0, le=1.0)
    approved: Literal[True] = True
    visibility: AdmittedVisibility
    source_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    chunk_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    work: str | None = None
    father: str | None = None
    page: str | None = None
    timestamp: str | None = None


class LineageEdge(WireModel):
    edge_id: str
    from_chunk_id: str
    to_chunk_id: str
    relation: str
    approved: Literal[True] = True


class EvidencePacket(WireModel):
    tenant_id: str
    corpus_version: str
    confidence_tier: EvidenceConfidenceTier
    admitted_chunks: list[AdmittedChunk]
    suppressed_chunk_ids: list[str] = Field(default_factory=list)
    lineage_context: list[LineageEdge] = Field(default_factory=list)
