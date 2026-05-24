"""Dispatcher heuristic: < 50 chars/page → route to OCR fallback."""

from __future__ import annotations

import pytest
from app.adapters.parsers.base import ParsedBlock, ParsedPage
from app.domain.services.parser_dispatcher import dispatch


class _StubParser:
    def __init__(self, name: str, pages: list[ParsedPage]) -> None:
        self.name = name
        self._pages = pages
        self.calls = 0

    async def parse(self, *, file_bytes: bytes, mime_type: str) -> list[ParsedPage]:
        self.calls += 1
        return self._pages


def _make_pages(chars_per_page: int, page_count: int) -> list[ParsedPage]:
    return [
        ParsedPage(
            page_num=i + 1,
            blocks=(
                [
                    ParsedBlock(
                        text="x" * chars_per_page,
                        block_type="paragraph",
                        font_size=11.0,
                        bold=False,
                        bbox=None,
                        page_num=i + 1,
                    )
                ]
                if chars_per_page > 0
                else []
            ),
        )
        for i in range(page_count)
    ]


@pytest.mark.asyncio
async def test_dispatch_uses_primary_when_text_dense() -> None:
    primary = _StubParser("pdfplumber", _make_pages(200, 3))
    fallback = _StubParser("tesseract", _make_pages(0, 3))
    result = await dispatch(
        file_bytes=b"any", mime_type="application/pdf", primary=primary, fallback=fallback
    )
    assert result.parser_used == "pdfplumber"
    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_dispatch_falls_back_when_sparse_text() -> None:
    primary = _StubParser("pdfplumber", _make_pages(5, 4))
    fallback_pages = _make_pages(80, 4)
    fallback = _StubParser("tesseract", fallback_pages)
    result = await dispatch(
        file_bytes=b"any", mime_type="application/pdf", primary=primary, fallback=fallback
    )
    assert result.parser_used == "tesseract"
    assert fallback.calls == 1
    assert result.pages == fallback_pages


@pytest.mark.asyncio
async def test_dispatch_falls_back_when_primary_empty() -> None:
    primary = _StubParser("pdfplumber", [])
    fallback = _StubParser("tesseract", _make_pages(100, 1))
    result = await dispatch(
        file_bytes=b"any", mime_type="application/pdf", primary=primary, fallback=fallback
    )
    assert result.parser_used == "tesseract"
