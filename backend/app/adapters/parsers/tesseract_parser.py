"""Scanned PDF parser via Tesseract OCR (ADR-0008, parser-interface.md).

Used by the dispatcher when pdfplumber yields < 50 chars/page on average — typical of scanned-image
PDFs without an embedded text layer. Greek (`grc`, `ell`) and English language packs are required;
the dispatcher confirms availability before fan-out. Emits `block_type="paragraph"` and
`font_size=None` / `bbox=None` (typography not reliable from OCR).

Forbidden outside this module: `import pytesseract`. See `scaffold-contract.md`.
"""

from __future__ import annotations

import io
from typing import Any

import pdf2image
import pytesseract
from PIL import Image
from pytesseract import TesseractError

from app.adapters.parsers.base import ParsedBlock, ParsedPage
from app.core.config import get_settings
from app.core.errors import (
    ParserCorruptFileError,
    ParserExtractionError,
    ParserTimeoutError,
)

_TESSERACT_LANG = "grc+ell+eng"
_TESSERACT_CONFIG = "--psm 1"   # auto page segmentation with orientation/script detection
_OCR_DPI = 200


def _group_words_into_paragraphs(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group OCR words by Tesseract's (block_num, par_num) grouping."""
    groups: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for w in words:
        key = (int(w.get("block_num", 0)), int(w.get("par_num", 0)))
        groups.setdefault(key, []).append(w)
    return [groups[k] for k in sorted(groups.keys())]


def _paragraph_text(words: list[dict[str, Any]]) -> str:
    by_line: dict[tuple[int, int, int], list[dict[str, Any]]] = {}
    for w in words:
        key = (
            int(w.get("block_num", 0)),
            int(w.get("par_num", 0)),
            int(w.get("line_num", 0)),
        )
        by_line.setdefault(key, []).append(w)
    lines: list[str] = []
    for key in sorted(by_line.keys()):
        line_words = sorted(by_line[key], key=lambda x: int(x.get("left", 0)))
        line_text = " ".join(str(w["text"]) for w in line_words if str(w.get("text", "")).strip())
        if line_text:
            lines.append(line_text)
    return "\n".join(lines).strip()


def _classify(text: str) -> str:
    """Rule B heading detection from parser-interface.md: ALL-CAPS and short."""
    stripped = text.strip()
    if not stripped:
        return "other"
    word_count = len(stripped.split())
    if stripped.isupper() and word_count <= 8:
        return "heading"
    return "paragraph"


def _ocr_image(image: Image.Image) -> list[dict[str, Any]]:
    try:
        data = pytesseract.image_to_data(
            image,
            lang=_TESSERACT_LANG,
            config=_TESSERACT_CONFIG,
            output_type=pytesseract.Output.DICT,
            timeout=60,
        )
    except RuntimeError as exc:
        # pytesseract raises RuntimeError on `--timeout` expiry.
        raise ParserTimeoutError(str(exc)) from exc
    except TesseractError as exc:
        raise ParserExtractionError(str(exc)) from exc

    words: list[dict[str, Any]] = []
    n = len(data.get("text", []))
    for i in range(n):
        text = str(data["text"][i]).strip()
        if not text:
            continue
        words.append(
            {
                "text": text,
                "block_num": data["block_num"][i],
                "par_num": data["par_num"][i],
                "line_num": data["line_num"][i],
                "left": data["left"][i],
                "top": data["top"][i],
                "width": data["width"][i],
                "height": data["height"][i],
            }
        )
    return words


class TesseractParser:
    name = "tesseract"

    @property
    def supports_typography(self) -> bool:
        return False

    async def parse(self, *, file_bytes: bytes, mime_type: str) -> list[ParsedPage]:
        del mime_type
        if not file_bytes:
            raise ParserCorruptFileError("empty PDF byte stream")
        settings = get_settings()
        # pytesseract reads the binary path from this module-level attribute.
        if settings.tesseract_binary_path:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_binary_path

        try:
            images = pdf2image.convert_from_bytes(file_bytes, dpi=_OCR_DPI)
        except Exception as exc:
            raise ParserCorruptFileError(f"pdf2image failed: {exc}") from exc
        if not images:
            raise ParserExtractionError("pdf2image yielded zero pages")

        pages: list[ParsedPage] = []
        for idx, image in enumerate(images, start=1):
            words = _ocr_image(image)
            paragraphs = _group_words_into_paragraphs(words)
            blocks: list[ParsedBlock] = []
            for para_words in paragraphs:
                text = _paragraph_text(para_words)
                if not text:
                    continue
                blocks.append(
                    ParsedBlock(
                        text=text,
                        block_type=_classify(text),  # type: ignore[arg-type]
                        font_size=None,
                        bold=False,
                        bbox=None,
                        page_num=idx,
                    )
                )
            pages.append(ParsedPage(page_num=idx, blocks=blocks))

        if not pages:
            raise ParserExtractionError("tesseract yielded zero pages")
        return pages


# Convenience helper used by tests / dispatcher to read PDF bytes via a stream.
def _open_bytes(file_bytes: bytes) -> io.BytesIO:
    return io.BytesIO(file_bytes)


__all__ = ["TesseractParser"]
