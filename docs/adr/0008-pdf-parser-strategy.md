# ADR 0008: PDF Parser Strategy

Date: 2026-05-11
Status: Accepted

## Context

The Patristic source corpus is heterogeneous PDF. Two failure-causing classes exist in roughly equal proportions:

1. **Born-digital PDFs** — modern monastery publications, academic editions, journal articles. A text layer is present; page-order extraction returns usable Unicode.
2. **Scanned PDFs** — common in pre-1980 editions of Migne's *Patrologia Graeca*, monastery reprints, and out-of-print sources. The PDF carries only page images; page-order extraction silently returns empty text. Without OCR, these sources ingest successfully (`sources.approved=true`, `chunks` rows inserted with empty text) and then silently disappear from retrieval — the failure is invisible until a user asks a question the corpus should answer and gets nothing.

A second concern is heading detection. ADR-0009 (Chunking Strategy) requires bold/large-font block detection at the parser layer. A parser that returns flat text without per-block typographic metadata makes hierarchical chunking impossible without a second pass.

Phase 1 must also keep the corpus inside the server boundary (CLAUDE.md §9, ADR-0001 closed-corpus contract). Hosted OCR services (Google Document AI, AWS Textract) ship the corpus to a third-party processor and incur per-page cost; both are disqualified.

## Decision

PDF parsing is performed by two concrete parsers behind a `Parser` Protocol (specified in `docs/contracts/parser-interface.md`):

| Path | Implementation | When chosen |
|---|---|---|
| Digital | `PdfplumberParser` wrapping the `pdfplumber` library | First attempt for every file |
| Scanned | `TesseractParser` wrapping `pytesseract` with `tesseract-ocr-grc` + `tesseract-ocr-ell` language packs | Selected when the digital path returns insufficient text |

**Dispatch heuristic.** The chunking service (`app/domain/services/chunking_service.py`), not the parsers themselves, owns dispatch:

1. Call `PdfplumberParser.parse(file_bytes, mime_type)`.
2. Compute `avg_chars_per_page = total_extracted_chars / page_count`.
3. If `avg_chars_per_page < 50`, discard the result and call `TesseractParser.parse(file_bytes, mime_type)` instead.
4. Emit `ingest.extracted` log event (per `docs/contracts/observability.md`) with a `parser_used` field set to `pdfplumber` or `tesseract`.

The 50-character threshold is a tunable MVP default; T-002 implementers may adjust it based on measurement against the seed corpus and record the new value in `approved-decisions-register.md` without amending this ADR.

**Library selection rationale.**

- `pdfplumber` (MIT) gives per-word bounding boxes, per-character font size, and a bold flag derived from the font name. ADR-0009's heading detection (`block.bold` OR `font_size > median_body_font * 1.3`) relies on these fields. `pdfplumber` is pure Python (no native compile step in the container) and has been stable for >5 years.
- `pytesseract` (Apache 2.0) wraps Tesseract OCR, which ships with language data files for both modern Greek (`ell`) and Polytonic Greek (`grc`). Tesseract runs locally inside the worker container — no network egress, no per-page cost. Accuracy on clean modern Greek scans is ~92–95%; Polytonic accuracy is lower on degraded scans and is tracked as a Phase 2 quality target.

**Phase 2 hook.** A `VisionParser` implementation (LLM-with-vision for multi-column or heavily-degraded layouts) can be added as a third `Parser` implementation. Adding it does not change the dispatch heuristic — instead, the heuristic gains a third branch (e.g., "if Tesseract confidence below threshold, fall through to `VisionParser`"). Phase 1 ships a `NotImplementedError` stub of `VisionParser` so the seam is visible in the codebase.

## Consequences

- **Container image.** The Docker image gains ~120 MB for the Tesseract binary plus `grc` and `ell` language packs. Tesseract and language-pack versions MUST be pinned in the Dockerfile because OCR output is sensitive to the trained-data version; an unpinned upgrade silently changes the corpus.
- **Cost.** Per-page OCR cost is zero (local Tesseract). No corpus bytes leave the server boundary.
- **Latency.** Tesseract is slower than the digital path (roughly 1–3 seconds per page on commodity CPU). This affects ingestion throughput, not query latency. The ingestion job state machine in `db-schema.md` (`status='extracting'`) already accommodates long extraction steps.
- **OCR quality.** Tesseract on degraded Polytonic Greek scans is the known weak point. The chunking contract emits a `parser_used=tesseract` field on every chunk's source record; the ingestion review UI surfaces this so content managers can prioritize manual review for OCR-derived chunks. Improving Polytonic OCR (custom Tesseract training, or `VisionParser`) is a Phase 2 quality target.
- **Heading detection on OCR path.** Tesseract output lacks reliable font-size and bold metadata. The chunking contract (`chunking-contract.md`) defines an ALL-CAPS fallback heuristic specifically for the OCR path; this is acknowledged to be lossy and is the chunking-side cost of accepting scanned sources at all.

## Alternatives Considered

- **`unstructured.io`** — strong layout detection but pulls in heavy ML dependencies, has slow cold starts, and includes a hosted-API code path that risks accidental corpus egress. Rejected.
- **`pymupdf` / `fitz`** — superior layout extraction but distributed under AGPL. The project ships as commercial SaaS (per ADR-0001 and `phase1-implementation-contract.md`); AGPL would impose source-disclosure obligations on the entire service. Rejected.
- **Hosted OCR** (Google Document AI, AWS Textract, Azure OCR) — high accuracy but ships corpus to a third party (violates CLAUDE.md §9) and adds per-page cost. Rejected for Phase 1; may be reconsidered if data-residency contracts are added.
- **Single-path Tesseract-only** — would OCR every PDF including born-digital ones, wasting compute and degrading accuracy on PDFs where the text layer is perfect. Rejected.
- **LLM-with-vision as primary** — accurate but per-page cost is non-trivial at corpus scale and adds a hard dependency on an external API for ingestion. Reserved as the Phase 2 `VisionParser` for difficult cases only.

## Tests

- A born-digital PDF round-trips through `PdfplumberParser` and produces `ParsedBlock` entries with non-null `font_size` and `bold` fields.
- A scanned-only PDF (no text layer) triggers the dispatch heuristic and routes to `TesseractParser`; the resulting `ParsedBlock` entries have `font_size=None`, `bbox=None`, `bold=False`, and a non-empty `text` field.
- A PDF with a mostly-empty text layer (e.g., one paragraph on the first page only, blank pages following) routes to Tesseract because `avg_chars_per_page < 50` over the whole document.
- An `ingest.extracted` log event is emitted with `parser_used` populated for every successful extraction.
- The `VisionParser` stub raises `NotImplementedError` when instantiated and is not registered in any production dispatch path.

## References

- ADR-0001 (closed-corpus contract) — the no-egress constraint.
- ADR-0006 (PAG-RAG lineage architecture) — chunking output feeds the Phase 2 graph layer.
- ADR-0009 (Chunking Strategy) — consumer of `ParsedBlock` typographic metadata.
- `docs/contracts/parser-interface.md` — the `Parser` Protocol and `ParsedBlock` shape.
- `docs/contracts/approved-decisions-register.md` row D-PDF-001.
- `docs/contracts/observability.md` — `ingest.extracted` event definition.
- `docs/contracts/quote-overlap-algorithm.md` — A6 verification consumes the text this parser emits. Both `pdfplumber` and `pytesseract` output is run through the canonical normalization layer (NFKC + casefold + diacritic strip for the purposes of overlap only) before the 0.70 threshold is evaluated. Polytonic Greek breathings/accents and Latin diacritics are uniformly handled there; the parser does **not** need to pre-normalize text. This cross-link exists because the OCR error model is the dominant source of A6 false-negatives on scanned Greek sources — see V4 reference vector in `quote-overlap-algorithm.md` for the canonical test of diacritic-insensitive matching.
