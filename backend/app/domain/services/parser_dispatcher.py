"""Parser dispatcher per `docs/contracts/parser-interface.md` (ADR-0008).

Heuristic: run `pdfplumber` first, measure `avg_chars_per_page`; if `< 50`, the file is almost
certainly a scanned PDF without an embedded text layer, so re-route to `tesseract`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.adapters.parsers.base import ParsedPage

_OCR_THRESHOLD_CHARS_PER_PAGE = 50


@dataclass(frozen=True)
class DispatchResult:
    pages: list[ParsedPage]
    parser_used: str


class _ParserLike(Protocol):
    name: str

    async def parse(self, *, file_bytes: bytes, mime_type: str) -> list[ParsedPage]: ...


def _avg_chars_per_page(pages: list[ParsedPage]) -> float:
    if not pages:
        return 0.0
    total = sum(sum(len(b.text) for b in p.blocks) for p in pages)
    return total / len(pages)


async def dispatch(
    *,
    file_bytes: bytes,
    mime_type: str,
    primary: _ParserLike,
    fallback: _ParserLike,
) -> DispatchResult:
    pages = await primary.parse(file_bytes=file_bytes, mime_type=mime_type)
    if _avg_chars_per_page(pages) >= _OCR_THRESHOLD_CHARS_PER_PAGE:
        return DispatchResult(pages=pages, parser_used=primary.name)
    fallback_pages = await fallback.parse(file_bytes=file_bytes, mime_type=mime_type)
    return DispatchResult(pages=fallback_pages, parser_used=fallback.name)


__all__ = ["DispatchResult", "dispatch"]
