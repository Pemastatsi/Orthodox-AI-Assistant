# ADR 0009: Chunking Strategy

Date: 2026-05-11
Status: Accepted

## Context

A chunk is the smallest unit of retrievable text: vectorized once, surfaced as evidence in A4, quoted by A5, and verified by A6. The chunking algorithm therefore directly determines (a) retrieval precision, (b) how often A6's 70% quote-overlap check passes, and (c) whether the Phase 2 graph traversal layer described in ADR-0006 will work at all.

Fixed-size chunking — the naïve approach — fails on Patristic texts in three measurable ways:

1. **Mid-citation splits.** A scriptural quotation embedded in a long paragraph gets split across two chunks. A5 then has to reconstruct the citation from two retrieval hits, and A6's quote-overlap check (`docs/contracts/quote-overlap-algorithm.md`, default 0.70) systematically misses on long quotations.
2. **Mid-argument splits.** Patristic argumentation is structured: a thesis, a scriptural warrant, an objection from a heretic, a refutation. Fixed-size splits cut across these joints, producing retrieval hits that contain only fragments of the argument and degrading A5's composition quality.
3. **Section structure is discarded.** The chunk loses any record of which chapter, canon, or heading it came from. Citation display in the UI is reduced to "page N of *Title*" with no intra-work navigation, and the Phase 2 graph traversal layer has no parent/child relationships to traverse.

The chunking strategy is one of two architecture gaps `AGENTS.md` explicitly flags as unresolved (alongside the PDF parser, resolved in ADR-0008). It must be settled before T-001 generates the chunking service.

## Decision

Chunking is **hierarchical by heading boundary** with a **sentence-boundary fallback** for unheaded sections. The algorithm is specified in full in `docs/contracts/chunking-contract.md`; this ADR records the rationale and constraints.

### Boundary priority (highest wins)

1. The next heading boundary (always preferred when within or after the soft cap).
2. A sentence boundary, selected via `nltk.sent_tokenize` with the Greek tokenizer when the block contains characters in U+0370–U+03FF (Greek and Coptic) or U+1F00–U+1FFF (Greek Extended), and the English tokenizer otherwise.
3. A hard token-boundary split (last resort; emits a `chunking.hard_split` warning event).

### Token caps

- **Soft target:** 800–1200 tokens, counted via `tiktoken.get_encoding("cl100k_base")`.
- **Hard maximum:** 1500 tokens. Reaching the hard maximum triggers a sentence-boundary split.

The 800–1200 range is a deliberate compromise: large enough to hold a complete Patristic argument (typically 600–900 tokens in English; longer in Greek), small enough to embed efficiently with `text-embedding-3-small` (8192-token model context, but retrieval relevance degrades on long inputs) and to keep A5's prompt size bounded when several chunks are surfaced as evidence.

### Heading detection

Heading detection runs on the `ParsedBlock` stream from the `Parser` Protocol (ADR-0008, `parser-interface.md`). A `ParsedBlock` is treated as a heading if **either**:

- `block.bold == True` AND `len(block.text) ≤ 120` AND the block is the first block on its line; **or**
- `block.font_size > median_body_font_size * 1.3`, where `median_body_font_size` is computed across all blocks with `block_type == "paragraph"` in the document.

When `font_size` is `None` (OCR path — `TesseractParser` cannot recover font metrics), the chunking service falls back to an **ALL-CAPS heuristic**: `block.text.isupper() AND len(block.text.split()) ≤ 8`. This is acknowledged to be lossy on the OCR path and is part of the cost of accepting scanned sources at all (per ADR-0008).

The thresholds (`1.3`, `≤ 120 chars`, `≤ 8 words`) are MVP defaults grounded in inspection of sample Patristic PDFs. Per recommendation #4 during planning, T-002 implementers may tune them based on measurement and record the new values in `approved-decisions-register.md` without amending this ADR — provided the change improves heading-detection accuracy on a documented sample without regressing retrieval metrics.

### Required chunk metadata

Every emitted chunk MUST carry:

- `sectionPath: list[str]` — ordered list of enclosing heading strings from document root to nearest heading. Empty list for content preceding the first heading. This is what enables citation display ("*On the Holy Spirit*, Book III, Chapter 4") and what the Phase 2 graph layer joins on.
- `pageStart: int`, `pageEnd: int` — inclusive page numbers, derived from the `ParsedBlock.page_num` of the first and last block in the chunk. These satisfy the "page-anchored citation" requirement in decision register row "Citation detail".
- `parentChunkId: str | None` — `NULL` for top-level chunks. Populated only when a parent chunk exceeded the hard cap and was split by the sentence-boundary fallback, in which case all children point to the parent's chunk ID. **This is the join key for the Phase 2 graph traversal layer described in ADR-0006.** Preserving the parent/child relationship now is what makes the PAG-RAG lineage architecture buildable later without re-ingestion.

### Footnotes

`ParsedBlock`s with `block_type == "footnote"` are appended to the nearest preceding paragraph chunk, not emitted as standalone chunks. Standalone footnote chunks would be too short to embed meaningfully, would inflate the vector store, and would surface as low-signal retrieval hits.

## Why this matters for Phase 1 exit criteria

A6's quote-overlap algorithm (`docs/contracts/quote-overlap-algorithm.md`) requires that A5's cited text overlap with the retrieved chunk by at least 70% by default. Fixed-size chunking systematically reduces the overlap floor for long quotations — particularly scriptural quotations and conciliar canons, both of which are common in Patristic argument. Hierarchical chunking keeps these quotations whole inside a single chunk, raising the achievable overlap floor and making the 70% threshold a meaningful safety check rather than an obstacle.

In short: this ADR is what makes the 70% verifier gate in `phase1-implementation-contract.md` survivable.

## Phase 2 hook

`parentChunkId` is intentionally the only structural metadata field that is not strictly required for Phase 1 retrieval. It exists because ADR-0006's PAG-RAG graph layer treats chunk hierarchy as the substrate for lineage edges. If we did not preserve hierarchy now, the Phase 2 graph layer would either need to re-derive parent/child relationships from scratch (expensive and lossy) or trigger a full re-ingestion (which is exactly the kind of one-way door we are trying to avoid). Setting `parentChunkId` correctly during the sentence-boundary fallback is therefore a one-line change with multi-quarter consequences if missed.

## Consequences

- **Heading detection is heuristic, not perfect.** Documents with unusual typography (decorative initials, all-bold body text, hand-typed manuscripts converted to PDF) will misclassify some headings. The chunking contract requires the implementer to log the heading-detection rate per document for review.
- **OCR-path chunks lose hierarchy quality.** When `font_size` is `None`, the ALL-CAPS fallback catches only the loudest headings. Section paths on Tesseract-derived chunks may be shallower than on `pdfplumber`-derived chunks from the same logical work. This is acceptable for MVP and improved by the Phase 2 `VisionParser`.
- **Token-budget pressure on long arguments.** Some Patristic arguments exceed 1500 tokens (e.g., long anti-Arian sections in Athanasius). These trigger the sentence-boundary split and produce `parentChunkId`-linked child chunks. Retrieval may surface only one child; A5 must still produce a coherent answer. The orchestrator is responsible for fetching sibling chunks when `parentChunkId` is set on a top-K hit (this is an A4 detail tracked separately).
- **Embedding cost.** Hierarchical chunks are larger on average than fixed-size 500-token chunks. Embedding cost is roughly 60% of what it would be with smaller chunks (fewer chunks per document) — net favorable.

## Alternatives Considered

- **Fixed-size chunks with overlap (e.g., 500 tokens, 100-token overlap).** Industry default. Loses heading structure entirely, splits citations and arguments, drives A6 overlap failures. Rejected.
- **Sentence-only chunking.** Each sentence is a chunk. Chunks become too small to embed meaningfully, vector store size inflates by ~10×, and retrieval becomes noisy. Rejected.
- **LLM-based semantic chunking** (call an LLM per document to identify boundaries). High quality but adds per-document cost, slows ingestion by 10–100×, introduces a model dependency in the ingestion path, and is non-deterministic across re-ingestions. Rejected for Phase 1; could be revisited as a refinement pass in Phase 2.
- **Structural-only chunking** (one chunk per heading section, no token cap). Some Patristic chapters are 5,000+ tokens and would exceed the embedding model's relevance sweet spot. Rejected; the soft cap and sentence fallback exist precisely to cap chunks at an embeddable size.

## Tests

- A document with clear headings produces chunks whose `sectionPath` matches the heading hierarchy and whose `pageStart`/`pageEnd` are consistent with the source PDF's pagination.
- A document with a 2000-token unheaded section produces multiple chunks all sharing a `parentChunkId` pointing to a virtual parent (or to the first child; choice recorded in T-002).
- Footnote blocks do not produce standalone chunks; they are appended to the preceding paragraph chunk.
- A Tesseract-derived (OCR-path) document with `font_size=None` everywhere produces a non-empty `sectionPath` on at least the ALL-CAPS heading blocks.
- The `chunking.hard_split` warning event fires when (and only when) a chunk reaches 1500 tokens with no sentence boundary available before the cap.
- A6 quote-overlap regression test: for a fixture document containing a 200-word scriptural quotation, a chunk emitted by the chunking service contains the full quotation (i.e., the quotation is not split across two chunks).

## References

- ADR-0006 (PAG-RAG lineage architecture) — consumer of `parentChunkId`.
- ADR-0008 (PDF Parser Strategy) — supplier of the `ParsedBlock` stream.
- `docs/contracts/chunking-contract.md` — algorithm specification.
- `docs/contracts/parser-interface.md` — `ParsedBlock` shape and typographic fields.
- `docs/contracts/quote-overlap-algorithm.md` — the 70% gate this ADR is designed to make survivable.
- `docs/contracts/approved-decisions-register.md` row D-CHK-001.
- `docs/schemas/chunk.schema.json` — the chunk shape, expanded with `sectionPath`/`pageStart`/`pageEnd`/`parentChunkId` in Step 6 of this work.
