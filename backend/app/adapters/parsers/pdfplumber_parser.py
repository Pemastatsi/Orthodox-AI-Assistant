"""Born-digital PDF parser via pdfplumber (ADR-0008, parser-interface.md).

Walks each page's character stream, groups characters into lines using y-coordinate proximity,
then assembles lines into paragraph-level `ParsedBlock`s on whitespace gaps. Font size and bold
flag are inherited from the dominant character run in each block so the chunking service can apply
heading detection Rule A (typography) without re-opening the PDF.

Forbidden outside this module: `import pdfplumber`. See `scaffold-contract.md` §forbidden imports.
"""

from __future__ import annotations

import io
import statistics
from typing import Any

import pdfplumber

from app.adapters.parsers.base import ParsedBlock, ParsedPage
from app.core.errors import (
    ParserCorruptFileError,
    ParserExtractionError,
    ParserPasswordProtectedError,
)

_PARAGRAPH_GAP_RATIO = 1.4   # y-gap > this * line height starts a new block
_LINE_TOLERANCE = 3.0        # px tolerance when grouping chars into lines


def _group_chars_into_lines(
    chars: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    """Group characters by y-coordinate (top edge), tolerant of font-baseline noise."""
    if not chars:
        return []
    by_top = sorted(chars, key=lambda c: (round(c["top"], 1), c["x0"]))
    lines: list[list[dict[str, Any]]] = []
    current_top = by_top[0]["top"]
    current: list[dict[str, Any]] = []
    for ch in by_top:
        if abs(ch["top"] - current_top) > _LINE_TOLERANCE:
            if current:
                lines.append(sorted(current, key=lambda c: c["x0"]))
            current = [ch]
            current_top = ch["top"]
        else:
            current.append(ch)
    if current:
        lines.append(sorted(current, key=lambda c: c["x0"]))
    return lines


def _line_text(line: list[dict[str, Any]]) -> str:
    """Reconstruct line text, inserting spaces where char gaps exceed half a glyph width."""
    if not line:
        return ""
    parts: list[str] = [line[0]["text"]]
    for prev, ch in zip(line, line[1:], strict=False):
        gap = ch["x0"] - prev["x1"]
        glyph = max(prev["width"], 1.0)
        if gap > glyph * 0.3:
            parts.append(" ")
        parts.append(ch["text"])
    return "".join(parts).strip()


def _dominant_font_size(chars: list[dict[str, Any]]) -> float | None:
    sizes = [round(float(c.get("size", 0.0)), 1) for c in chars if c.get("size")]
    if not sizes:
        return None
    return statistics.median(sizes)


def _is_bold(chars: list[dict[str, Any]]) -> bool:
    if not chars:
        return False
    bold_chars = sum(1 for c in chars if "bold" in str(c.get("fontname", "")).lower())
    return bold_chars * 2 >= len(chars)


def _bbox_of(chars: list[dict[str, Any]]) -> tuple[float, float, float, float] | None:
    if not chars:
        return None
    x0 = min(float(c["x0"]) for c in chars)
    x1 = max(float(c["x1"]) for c in chars)
    top = min(float(c["top"]) for c in chars)
    bottom = max(float(c["bottom"]) for c in chars)
    return (x0, top, x1, bottom)


def _classify_block(
    *,
    text: str,
    font_size: float | None,
    is_bold: bool,
    median_body: float | None,
    page_height: float,
    block_top: float,
) -> str:
    """Light-touch block_type hint; the chunking service makes the final call."""
    stripped = text.strip()
    if not stripped:
        return "other"
    if page_height and block_top > page_height * 0.85 and len(stripped) < 200:
        # Bottom-of-page short blocks are likely footnotes.
        return "footnote"
    if median_body and font_size and font_size > median_body * 1.3 and len(stripped) <= 120:
        return "heading"
    if is_bold and len(stripped) <= 120:
        return "heading"
    return "paragraph"


def _page_to_blocks(page: Any, page_num: int) -> list[ParsedBlock]:
    chars: list[dict[str, Any]] = list(page.chars or [])
    if not chars:
        return []

    lines = _group_chars_into_lines(chars)
    if not lines:
        return []

    line_heights = [
        max(float(c["bottom"]) - float(c["top"]) for c in line) for line in lines if line
    ]
    median_line_height = statistics.median(line_heights) if line_heights else 12.0
    page_median_size = _dominant_font_size(chars)
    page_height = float(page.height or 0.0)

    blocks: list[ParsedBlock] = []
    current_chars: list[dict[str, Any]] = []
    current_lines: list[list[dict[str, Any]]] = []
    last_bottom: float | None = None

    def flush() -> None:
        if not current_chars or not current_lines:
            return
        text = "\n".join(_line_text(line) for line in current_lines if line).strip()
        if not text:
            return
        font_size = _dominant_font_size(current_chars)
        is_bold = _is_bold(current_chars)
        bbox = _bbox_of(current_chars)
        block_top = float(min(c["top"] for c in current_chars))
        block_type = _classify_block(
            text=text,
            font_size=font_size,
            is_bold=is_bold,
            median_body=page_median_size,
            page_height=page_height,
            block_top=block_top,
        )
        blocks.append(
            ParsedBlock(
                text=text,
                block_type=block_type,  # type: ignore[arg-type]
                font_size=font_size,
                bold=is_bold,
                bbox=bbox,
                page_num=page_num,
            )
        )

    for line in lines:
        if not line:
            continue
        line_top = float(min(c["top"] for c in line))
        if last_bottom is not None and (line_top - last_bottom) > median_line_height * _PARAGRAPH_GAP_RATIO:  # noqa: E501
            flush()
            current_chars = []
            current_lines = []
        current_chars.extend(line)
        current_lines.append(line)
        last_bottom = float(max(c["bottom"] for c in line))

    flush()
    return blocks


class PdfplumberParser:
    name = "pdfplumber"

    @property
    def supports_typography(self) -> bool:
        return True

    async def parse(self, *, file_bytes: bytes, mime_type: str) -> list[ParsedPage]:
        del mime_type  # pdfplumber inspects the byte stream itself
        if not file_bytes:
            raise ParserCorruptFileError("empty PDF byte stream")
        try:
            stream = io.BytesIO(file_bytes)
            pages: list[ParsedPage] = []
            with pdfplumber.open(stream) as pdf:
                for idx, page in enumerate(pdf.pages, start=1):
                    blocks = _page_to_blocks(page, page_num=idx)
                    pages.append(ParsedPage(page_num=idx, blocks=blocks))
            if not pages:
                raise ParserExtractionError("pdfplumber yielded zero pages")
            return pages
        except (ParserCorruptFileError, ParserExtractionError, ParserPasswordProtectedError):
            raise
        except Exception as exc:  # pdfplumber wraps lower-level errors heterogeneously
            message = str(exc).lower()
            if "password" in message or "encrypt" in message:
                raise ParserPasswordProtectedError(str(exc)) from exc
            raise ParserCorruptFileError(f"pdfplumber failed to open document: {exc}") from exc


__all__ = ["PdfplumberParser"]
