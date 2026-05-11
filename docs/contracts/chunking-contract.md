# Chunking Contract

Status: Canonical
Date: 2026-05-11

This document specifies the chunking algorithm: the bridge between `Parser` output and the `chunks` table. Implemented in `app/domain/services/chunking_service.py`. The rationale for hierarchical chunking, the boundary priority, and the required metadata fields are recorded in ADR-0009.

## Input and output

| | |
|---|---|
| Input | `list[ParsedPage]` produced by the dispatched `Parser` (per `parser-interface.md`). |
| Output | `list[Chunk]` where each `Chunk` validates against `docs/schemas/chunk.schema.json`. |

The service is a pure function of its input plus the `tenantId`, `sourceId`, `sourceHash`, `corpusVersion`, and `language` carried on the parent `sources` row. Calling it twice on the same inputs MUST produce identical output (same `chunkHash` values, same `sectionPath`s, same boundaries). Determinism is required for re-ingestion safety; see `ingest_jobs` state machine in `db-schema.md`.

## Required Chunk metadata

Every emitted `Chunk` MUST carry these fields in addition to those already present in `chunk.schema.json`:

| Field | Type | Meaning |
|---|---|---|
| `sectionPath` | `list[str]` | Ordered list of enclosing heading strings from document root to the nearest enclosing heading. Empty list (`[]`) for content preceding the first heading. |
| `pageStart` | `int` | 1-indexed PDF page number of the first `ParsedBlock` included in this chunk. |
| `pageEnd` | `int` | 1-indexed PDF page number of the last `ParsedBlock` included in this chunk. `pageEnd >= pageStart`. |
| `parentChunkId` | `str \| null` | `null` for top-level chunks. Populated only when a parent chunk exceeded the hard token cap and was split by the sentence-boundary fallback — all resulting children point to the parent's `chunkId`. |

These four fields are required by `chunk.schema.json` once amended in Step 6 of this work. They are the join keys for citation display (`sectionPath`, `pageStart`/`pageEnd`) and for the Phase 2 graph traversal layer described in ADR-0006 (`parentChunkId`).

## Heading detection

Heading detection runs on each `ParsedBlock`. A block is treated as a heading if **either** rule below matches.

### Rule A — Typography (applies when `parser.supports_typography == True`)

A block is a heading if:

```
block.bold == True
AND len(block.text) <= 120
AND block_is_first_on_line(block)
```

OR

```
block.font_size > median_body_font_size * 1.3
```

where `median_body_font_size` is computed across all `ParsedBlock` entries in the document where `block_type == "paragraph"`. If the document contains no paragraph blocks (extremely short documents), the chunking service treats all blocks as paragraphs and emits no headings.

### Rule B — ALL-CAPS fallback (applies when `parser.supports_typography == False`, i.e., the OCR path)

A block is a heading if:

```
block.text.isupper()
AND len(block.text.split()) <= 8
```

This is acknowledged to be lossy and is the chunking-side cost of accepting scanned sources per ADR-0008. Tesseract-derived chunks therefore have shallower `sectionPath`s on average than `pdfplumber`-derived chunks from the same logical work.

### Tunable thresholds (MVP defaults)

The constants `1.3` (font-size multiplier), `120` (max heading length in characters), `8` (max ALL-CAPS heading length in words), and the soft/hard token caps below are MVP defaults grounded in inspection of sample Patristic PDFs. T-002 implementers MAY tune them when measurement against the seed corpus shows they misclassify headings on a documented fraction of pages, provided the new values are recorded in `approved-decisions-register.md` as a follow-up row to D-CHK-001. Tuning these constants does NOT require an ADR amendment.

## Token counting

```python
import tiktoken
encoder = tiktoken.get_encoding("cl100k_base")
token_count = len(encoder.encode(text))
```

`cl100k_base` is the same encoder used by `text-embedding-3-small`. Using a single encoder across chunking and embedding makes the "tokens-going-into-the-embedder" count exact, not approximate.

Greek text encodes slightly less efficiently than English in `cl100k_base` (roughly 1.4–1.7 tokens per word vs. 1.0–1.3 for English). The soft/hard caps are stated in tokens, not words, specifically to absorb this without per-language tuning.

## Chunk boundaries (priority order)

The chunking algorithm proceeds linearly through `ParsedBlock`s, accumulating into the current chunk, and emits a boundary using the **first applicable** rule below:

1. **Next heading boundary.** When a `ParsedBlock` is classified as a heading by §Heading detection AND the current chunk's accumulated token count is ≥ 200 (a minimum to prevent emitting tiny stub chunks from documents with very dense heading structure), emit a boundary before the heading block. The heading block becomes the first content of the next chunk, and the chunk's `sectionPath` gains the heading text.
2. **Sentence boundary (post soft-cap).** When accumulated tokens ≥ 800 (the soft floor), the next sentence boundary inside the current `ParsedBlock` becomes a candidate split point. The algorithm prefers to wait for a heading (rule 1) until accumulated tokens ≥ 1200 (the soft ceiling), at which point it splits at the next available sentence boundary regardless.
3. **Hard split (last resort).** If accumulated tokens reach 1500 with neither a heading nor a sentence boundary available, the chunker forces a hard token-boundary split AND emits a `chunking.hard_split` warning log event (per `observability.md`). Hard splits should be exceptional; if they occur on more than 1% of chunks in a document, the T-002 implementer should investigate.

Sentence boundaries are detected via:

```python
import nltk
def has_greek(text: str) -> bool:
    return any('Ͱ' <= ch <= 'Ͽ' or 'ἀ' <= ch <= '῿' for ch in text)
language = "greek" if has_greek(block.text) else "english"
sentences = nltk.sent_tokenize(block.text, language=language)
```

When the sentence-boundary fallback (rule 2 or 3) splits what would otherwise have been a single chunk, every resulting child chunk's `parentChunkId` points to the `chunkId` of the first child. The first child's `parentChunkId` is itself — this is the marker that "a sentence-split happened here" and is what the Phase 2 graph layer reads.

## Footnotes

`ParsedBlock`s with `block_type == "footnote"` are **not** emitted as standalone chunks. They are appended (with a single newline separator) to the nearest preceding paragraph chunk that shares their `page_num` or `page_num - 1`. If no such preceding chunk exists (unusual — a footnote on the first content page of a document), the footnote is folded into the first paragraph chunk that opens on its page.

This rule exists because standalone footnote chunks are too short to embed meaningfully and would surface as low-signal retrieval hits. The cost is that footnote text becomes searchable only via the chunk that contains the cited body text — which is the natural retrieval semantics anyway.

## Invariants

The chunking service MUST enforce all of the following. Each is covered by a test in `tests/unit/test_chunking_service.py`.

1. **Per-document `sourceId`.** Every emitted `Chunk` in a single `parse_pdf → chunk_document` call shares the same `sourceId`.
2. **Page consistency.** For every emitted chunk: `pageStart ≤ pageEnd`, both in `[1, parsed_pdf.page_count]`, and `pageStart` equals the `page_num` of the first `ParsedBlock` in the chunk.
3. **Section-path consistency.** A chunk's `sectionPath` must be a prefix-extension of the previous chunk's `sectionPath` OR diverge at exactly one level (the level at which a new heading was encountered). A chunk MUST NOT skip a heading level. Concretely: if document headings are H1 → H2 → H3, no chunk has `sectionPath=["H1", "H3"]`.
4. **Token cap.** No emitted chunk exceeds 1500 tokens under `cl100k_base`. This is checked AFTER footnote folding (footnotes can push a chunk over the soft cap but not the hard cap — if folding a footnote would exceed 1500 tokens, the footnote is folded into the next paragraph chunk instead).
5. **Determinism.** Two invocations with byte-identical input produce byte-identical output, including identical `chunkHash` values. `chunkHash` is `sha256(text)` per `db-schema.md`.
6. **Footnote completeness.** Every footnote `ParsedBlock` is either folded into a paragraph chunk OR explicitly logged as "orphan footnote" with a `chunking.orphan_footnote` warning event.
7. **Tenant isolation invariant carries through.** The chunking service receives `tenantId` from its caller (the ingestion worker) and stamps it on every chunk; chunks never inherit `tenantId` from any other source.

## What the chunking service must NOT do

- Call an LLM. Chunking is deterministic and local.
- Write to Postgres. The ingestion worker (`app/workers/tasks/ingestion.py`) owns persistence.
- Write to the vector store. Embedding and `VectorStore.upsert` are downstream steps.
- Approve chunks. `chunks.approved` is set only via `PATCH /corpus/{chunkId}` per `db-schema.md` invariant #3.
- Call into `app/adapters/parsers/` directly. The dispatch logic in §parser-interface.md owns parser selection; the chunking service receives `list[ParsedPage]` and does not know which `Parser` produced them.

## Observability

Per `docs/contracts/observability.md`, the chunking service emits:

| Event | When | Fields |
|---|---|---|
| `ingest.chunked` | Per document, on successful completion | `source_id`, `chunk_count`, `avg_tokens_per_chunk`, `parser_used` |
| `chunking.hard_split` | Per occurrence (rule 3 above) | `source_id`, `page_num`, `accumulated_tokens` |
| `chunking.orphan_footnote` | Per occurrence | `source_id`, `page_num`, `footnote_text_preview` (first 60 chars) |

## Error mapping

| Service exception | `ingest_jobs.error_code` | Retryable |
|---|---|---|
| `ChunkingDeterminismError` | `chunking_determinism_violated` | no (bug; logged for triage) |
| `ChunkingHeadingDetectionError` | `chunking_heading_detection_failed` | no |
| `ChunkingTokenizerError` | `chunking_tokenizer_failed` | yes |

## References

- ADR-0009 — rationale and Phase 2 hook.
- ADR-0008 / `parser-interface.md` — supplier of `ParsedPage` / `ParsedBlock`.
- ADR-0006 — consumer of `parentChunkId` in Phase 2.
- `docs/contracts/quote-overlap-algorithm.md` — A6's 70% gate, which hierarchical chunking is designed to make survivable.
- `docs/contracts/observability.md` — event definitions for the three events emitted above.
- `docs/schemas/chunk.schema.json` — chunk shape, expanded with `sectionPath`/`pageStart`/`pageEnd`/`parentChunkId` in this step.
- `docs/contracts/approved-decisions-register.md` row D-CHK-001.
