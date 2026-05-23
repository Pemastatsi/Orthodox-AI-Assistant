"""Phase 2 LLM-with-vision parser. Always raises NotImplementedError in Phase 1 (ADR-0008)."""

from __future__ import annotations

from app.adapters.parsers.base import ParsedPage


class VisionParser:
    name = "vision"

    def __init__(self) -> None:
        raise NotImplementedError("VisionParser is a Phase 2 stub per ADR-0008")

    @property
    def supports_typography(self) -> bool:
        return False

    async def parse(self, *, file_bytes: bytes, mime_type: str) -> list[ParsedPage]:
        del file_bytes, mime_type
        raise NotImplementedError("VisionParser is a Phase 2 stub per ADR-0008")
