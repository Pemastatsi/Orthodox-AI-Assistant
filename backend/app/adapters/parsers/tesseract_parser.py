"""Scanned PDF parser via Tesseract OCR. Implementation lands in T-002 (ADR-0008)."""

from __future__ import annotations

from app.adapters.parsers.base import ParsedPage


class TesseractParser:
    name = "tesseract"

    @property
    def supports_typography(self) -> bool:
        return False

    async def parse(self, *, file_bytes: bytes, mime_type: str) -> list[ParsedPage]:
        del file_bytes, mime_type
        raise NotImplementedError("TesseractParser is implemented in T-002")
