# Parser Interface

Status: Canonical
Date: 2026-05-11

This document defines the abstract interface every PDF parser adapter implements. Implemented in `app/adapters/parsers/base.py`. Concrete adapters: `pdfplumber_parser.py` (digital path), `tesseract_parser.py` (scanned path), `vision_parser.py` (Phase 2 stub — raises `NotImplementedError`). The decision to ship two paths behind a single Protocol is recorded in ADR-0008.

## Goals

- A single typed surface so the chunking service does not import `pdfplumber` or `pytesseract` directly.
- Predictable error mapping so the rest of the app deals only with codes from `docs/contracts/error-taxonomy.md`.
- Per-block typographic metadata (`font_size`, `bold`, `bbox`) sufficient for the heading-detection rules in `docs/contracts/chunking-contract.md` (ADR-0009).
- A clean seam for the Phase 2 `VisionParser` to slot in without touching the dispatch heuristic.

## Protocol

```python
from typing import Literal, Protocol, runtime_checkable
from dataclasses import dataclass

@runtime_checkable
class Parser(Protocol):
    name: str               # 'pdfplumber' | 'tesseract' | 'vision'

    async def parse(
        self,
        *,
        file_bytes: bytes,
        mime_type: str,
    ) -> list[ParsedPage]: ...

    @property
    def supports_typography(self) -> bool: ...
        # True when the parser populates font_size / bbox / bold reliably.
        # PdfplumberParser: True. TesseractParser: False. VisionParser: TBD.
```

`parse` is the only public method. Parsers are stateless; each call is independent. Implementations MUST be safe to call concurrently from multiple ingestion workers.

## `ParsedPage`

```python
@dataclass(frozen=True)
class ParsedPage:
    page_num: int                   # 1-indexed, matches PDF page numbering
    blocks: list[ParsedBlock]
```

Empty `blocks` is allowed (e.g., blank page in the source PDF). A document with zero `ParsedPage` entries means extraction failed; the parser MUST raise `ParserExtractionError` instead of returning an empty list.

## `ParsedBlock`

The shape that drives heading detection and chunk-page-anchoring in `chunking-contract.md`. The on-disk JSON shape is in `docs/schemas/parsed-block.schema.json`; the dataclass form is the in-memory equivalent.

```python
@dataclass(frozen=True)
class ParsedBlock:
    text: str
    block_type: Literal['heading', 'paragraph', 'footnote', 'caption', 'other']
    font_size: float | None         # None on OCR path (TesseractParser)
    bold: bool                       # False on OCR path
    bbox: tuple[float, float, float, float] | None
                                     # (x0, y0, x1, y1) in PDF points; None on OCR path
    page_num: int                   # mirrors enclosing ParsedPage.page_num for convenience
```

| Field | Required | Constraints |
|---|---|---|
| `text` | yes | Non-empty after stripping whitespace. Blocks with only whitespace MUST be omitted, not emitted with empty text. |
| `block_type` | yes | Enum exactly as above. `'other'` is the catch-all for content the parser cannot confidently classify (e.g., page numbers, running headers). |
| `font_size` | when `supports_typography` is `True` | Positive number in PDF points. `None` permitted only when the parser cannot determine font size (OCR path). |
| `bold` | yes | `False` is the safe default for parsers that cannot detect weight (OCR path). |
| `bbox` | when `supports_typography` is `True` | Four numbers `(x0, y0, x1, y1)`. `None` permitted only on the OCR path. |
| `page_num` | yes | Must match the enclosing `ParsedPage.page_num`. |

`block_type` classification is best-effort. `PdfplumberParser` distinguishes paragraphs from footnotes by font-size delta (footnote font is typically ≤ 80% of body font). `TesseractParser` cannot reliably distinguish footnotes; it emits everything as `'paragraph'` and footnote handling falls back to the chunking-service heuristic ("trailing short blocks at the bottom of a page with smaller text" — described in `chunking-contract.md`).

## Dispatch logic

Dispatch lives in `app/domain/services/chunking_service.py`, **not** in the parsers themselves. This keeps parsers stateless and single-purpose.

```python
async def parse_pdf(file_bytes: bytes, mime_type: str) -> list[ParsedPage]:
    pages = await pdfplumber_parser.parse(file_bytes=file_bytes, mime_type=mime_type)
    avg_chars_per_page = sum(
        sum(len(b.text) for b in page.blocks) for page in pages
    ) / max(len(pages), 1)
    if avg_chars_per_page < 50:
        pages = await tesseract_parser.parse(file_bytes=file_bytes, mime_type=mime_type)
        parser_used = 'tesseract'
    else:
        parser_used = 'pdfplumber'
    emit_event('ingest.extracted', parser_used=parser_used, page_count=len(pages))
    return pages
```

The 50-character threshold is the MVP default per ADR-0008. T-002 implementers may tune it (see ADR-0008 §Decision); changes are recorded in `approved-decisions-register.md`, not in this contract.

## Concrete implementations

### `PdfplumberParser`

- Wraps `pdfplumber`.
- `supports_typography = True`.
- Populates `text`, `block_type`, `font_size`, `bold`, `bbox`, `page_num` for every block.
- `bold` is derived from the font name (heuristic: name contains `Bold`, `Black`, or `Heavy`); `pdfplumber` does not expose a direct weight flag.

### `TesseractParser`

- Wraps `pytesseract` with `tesseract-ocr-grc` (Polytonic Greek) and `tesseract-ocr-ell` (modern Greek) language packs.
- `supports_typography = False`.
- Emits `font_size=None`, `bbox=None`, `bold=False` on every block.
- Emits `block_type='paragraph'` for body content; `'heading'` only when the ALL-CAPS heuristic in `chunking-contract.md` matches.
- Tesseract is invoked with `--psm 1` (automatic page segmentation with OSD) to handle the column layouts common in Migne editions.

### `VisionParser` (Phase 2 stub)

- Phase 1 implementation is a stub that raises `NotImplementedError` on instantiation if any code attempts to register it as the active parser.
- Phase 2 will implement this against an LLM-with-vision route for complex multi-column layouts. The Protocol surface does not change.

## Constraints

- **No LLM calls.** No parser may call an LLM or any external API. Tesseract runs locally inside the worker container.
- **No database writes.** Parsers are pure functions of `(file_bytes, mime_type)`.
- **No filesystem writes** except to a tempdir for Tesseract's intermediate files (cleaned up before return).
- **No `os.environ` reads.** Configuration (Tesseract language packs path, etc.) is injected via the parser constructor from `app/core/config.py`, per the same rule that governs `LLMProvider` adapters.

## Error Mapping

Each parser catches its library's exceptions and raises one of these typed exceptions, which the ingestion worker maps to `ingest_jobs.error_code`:

| Adapter exception | API code | Retryable |
|---|---|---|
| `ParserCorruptFileError` | `ingest_corrupt_file` | no |
| `ParserExtractionError` | `ingest_extraction_failed` | yes (after operator review) |
| `ParserTimeoutError` | `ingest_timeout` | yes |
| `ParserPasswordProtectedError` | `ingest_password_protected` | no |

Parsers MUST NOT leak `pdfplumber.PDFSyntaxError`, `pytesseract.TesseractError`, or any other library-specific exception type upward.

## Configuration

Parsers read their configuration only via `app/core/config.py`, which reads from `.env`. Required env vars:

- `TESSERACT_BINARY_PATH` — absolute path to the `tesseract` binary inside the worker container (default: `/usr/bin/tesseract`).
- `TESSERACT_LANGUAGE_PACK_PATH` — directory containing `grc.traineddata` and `ell.traineddata` (default: `/usr/share/tesseract-ocr/4.00/tessdata`).

Tesseract and the language packs MUST be pinned to specific versions in the Dockerfile per ADR-0008 §Consequences. An unpinned upgrade silently changes the corpus across re-ingestions.

## Forbidden

- Importing `pdfplumber`, `pdfminer`, `pypdf`, `pymupdf`, or `pytesseract` outside `app/adapters/parsers/`.
- Calling any hosted OCR service (Google Document AI, AWS Textract, Azure OCR) from a parser implementation. The closed-corpus contract (ADR-0001) and CLAUDE.md §9 forbid corpus egress.
- Reading `os.environ` directly inside a parser.
- Any `# noqa` or `# type: ignore` in parser code without a linked issue.

## References

- ADR-0008 — rationale for the two-path hybrid and library selection.
- ADR-0009 / `chunking-contract.md` — consumer of `ParsedBlock`'s typographic fields.
- `docs/contracts/observability.md` — `ingest.extracted` log event definition.
- `docs/contracts/error-taxonomy.md` — error code definitions.
- `docs/schemas/parsed-block.schema.json` — on-disk JSON shape for `ParsedBlock`.
- `docs/contracts/approved-decisions-register.md` row D-PDF-001.
