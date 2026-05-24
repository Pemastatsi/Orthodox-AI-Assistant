"""Hierarchical chunking per `docs/contracts/chunking-contract.md` (ADR-0009).

Boundary priority (first applicable wins, evaluated greedily as blocks stream in):
  1. **Heading** — when accumulated ≥ 200 tokens AND the next block is a heading, emit before it.
  2. **Sentence** — soft cap 800–1200 tokens; once we cross 1200, flush at the next sentence
     boundary inside the accumulator.
  3. **Hard split** — once a single paragraph exceeds the 1500-token hard cap, sentence-split it
     and emit a `chunking.hard_split` log event.

Footnotes (`block_type='footnote'`, or short blocks at the bottom of a page) are appended to the
nearest preceding paragraph in the accumulator, never emitted as standalone chunks.

Heading detection:
  - Rule A (typography): `bold AND len(text) ≤ 120` OR `font_size > 1.3 × median_body_font_size`.
  - Rule B (OCR fallback, when typography is missing): `text.isupper() AND word_count ≤ 8`.

Every chunk carries `section_path`, `page_start`, `page_end`, `parent_chunk_index` (None at top
level, else the index of the first chunk in the same sentence-split group). The ingestion worker
resolves `parent_chunk_index → parent_chunk_id` after the repository assigns IDs.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

from app.adapters.parsers.base import ParsedBlock, ParsedPage
from app.core.logging import get_logger

_SOFT_CAP_MIN = 800
_SOFT_CAP_MAX = 1200
_HARD_CAP = 1500
_HEADING_MIN_FLUSH = 200
_HEADING_MAX_LEN = 120
_HEADING_FONT_MULTIPLIER = 1.3
_HEADING_OCR_MAX_WORDS = 8
_SENTENCE_PUNCT = re.compile(r"(?<=[.!?;])\s+")
_AVG_TOKENS_PER_WORD = 1.3  # rough English approximation; only used in the offline fallback

logger = get_logger(__name__)


class _Tokenizer:
    """Wraps tiktoken's cl100k_base, falling back to a whitespace estimator if the BPE files
    can't be fetched (typical in air-gapped CI). Counts are within ~15% either way; the boundary
    rules in chunking-contract.md tolerate that for the heuristic caps."""

    def __init__(self) -> None:
        self._enc = None
        try:
            import tiktoken

            self._enc = tiktoken.get_encoding("cl100k_base")
        except Exception:  # noqa: BLE001 — any failure (network, missing data) falls back
            self._enc = None

    def count(self, text: str) -> int:
        if self._enc is not None:
            return len(self._enc.encode(text))
        return max(1, int(len(text.split()) * _AVG_TOKENS_PER_WORD))

    def encode(self, text: str) -> list[int]:
        if self._enc is not None:
            return self._enc.encode(text)
        # The fallback only needs to support len(); return a list sized to the estimate.
        return [0] * self.count(text)


@dataclass(frozen=True)
class ChunkCandidate:
    text: str
    section_path: list[str]
    page_start: int
    page_end: int
    parent_chunk_index: int | None = None


@dataclass
class _Accumulator:
    text_parts: list[str] = field(default_factory=list)
    tokens: int = 0
    page_start: int | None = None
    page_end: int | None = None
    section_path: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.text_parts

    def add(self, *, text: str, tokens: int, page_num: int) -> None:
        self.text_parts.append(text)
        self.tokens += tokens
        if self.page_start is None:
            self.page_start = page_num
        self.page_end = max(self.page_end or page_num, page_num)

    def reset(self, section_path: list[str]) -> None:
        self.text_parts = []
        self.tokens = 0
        self.page_start = None
        self.page_end = None
        self.section_path = list(section_path)

    def text(self) -> str:
        return "\n".join(part.strip() for part in self.text_parts if part.strip()).strip()


def _encoder() -> _Tokenizer:
    return _Tokenizer()


def _median_body_font_size(pages: list[ParsedPage]) -> float | None:
    sizes = [
        b.font_size
        for p in pages
        for b in p.blocks
        if b.font_size is not None and b.block_type == "paragraph"
    ]
    return statistics.median(sizes) if sizes else None


def _is_heading(block: ParsedBlock, *, median_body: float | None) -> bool:
    if block.block_type == "heading":
        return True
    text = block.text.strip()
    if not text:
        return False
    # Rule A — typography
    if block.font_size is not None:
        if block.bold and len(text) <= _HEADING_MAX_LEN:
            return True
        return bool(
            median_body and block.font_size > median_body * _HEADING_FONT_MULTIPLIER
        )
    # Rule B — OCR fallback
    return text.isupper() and len(text.split()) <= _HEADING_OCR_MAX_WORDS


def _is_footnote(block: ParsedBlock) -> bool:
    return block.block_type == "footnote"


def _split_sentences(text_value: str, *, encoder: _Tokenizer) -> list[str]:
    """Best-effort sentence split for hard-cap handling.

    NLTK is the contract's preferred sentence tokenizer; using its `punkt` model would catch more
    edge cases (abbreviations, Greek `;`). We use a regex fallback here so the service is usable
    without NLTK data downloads in the container; T-002 callers tolerate the small accuracy loss
    because hard splits are expected to be < 1% of chunks per the contract.
    """
    cleaned = text_value.strip()
    if not cleaned:
        return []
    parts = _SENTENCE_PUNCT.split(cleaned)
    out: list[str] = []
    for raw in parts:
        s = raw.strip()
        if not s:
            continue
        # If a "sentence" still exceeds the hard cap (very long line, no punctuation), fall back
        # to a word-level cut so the caller never sees a > _HARD_CAP fragment.
        if encoder.count(s) > _HARD_CAP:
            words = s.split()
            buf: list[str] = []
            for w in words:
                buf.append(w)
                if encoder.count(" ".join(buf)) > _HARD_CAP:
                    buf.pop()
                    if buf:
                        out.append(" ".join(buf).strip())
                        buf = [w]
                    else:  # single word longer than hard cap — emit anyway
                        out.append(w)
                        buf = []
            if buf:
                out.append(" ".join(buf).strip())
        else:
            out.append(s)
    return out


def _accumulator_split_at_sentence(
    acc: _Accumulator,
    *,
    encoder: _Tokenizer,
    target_tokens: int,
) -> tuple[str, _Accumulator]:
    """Split the accumulator text at the first sentence boundary that crosses `target_tokens`.

    Returns `(emitted_text, leftover_accumulator)` where `leftover_accumulator` carries the rest.
    If no sentence boundary is reached, the whole accumulator is emitted.
    """
    text_value = acc.text()
    sentences = _split_sentences(text_value, encoder=encoder)
    if not sentences:
        return text_value, _Accumulator(section_path=list(acc.section_path))

    emitted: list[str] = []
    emitted_tokens = 0
    cut = len(sentences)
    for i, s in enumerate(sentences):
        emitted.append(s)
        emitted_tokens += encoder.count(s)
        if emitted_tokens >= target_tokens:
            cut = i + 1
            break

    emitted_text = " ".join(emitted).strip()
    leftover_sentences = sentences[cut:]
    leftover = _Accumulator(section_path=list(acc.section_path))
    if leftover_sentences:
        leftover_text = " ".join(leftover_sentences).strip()
        leftover_tokens = encoder.count(leftover_text)
        leftover.add(text=leftover_text, tokens=leftover_tokens, page_num=acc.page_start or 1)
        leftover.page_start = acc.page_start
        leftover.page_end = acc.page_end
    return emitted_text, leftover


def _emit(
    acc: _Accumulator,
    *,
    chunks: list[ChunkCandidate],
    parent_chunk_index: int | None = None,
) -> int | None:
    """Flush the accumulator into a new chunk. Returns the index of the emitted chunk, or None."""
    text_value = acc.text()
    if not text_value:
        return None
    if acc.page_start is None or acc.page_end is None:
        return None
    chunks.append(
        ChunkCandidate(
            text=text_value,
            section_path=list(acc.section_path),
            page_start=acc.page_start,
            page_end=acc.page_end,
            parent_chunk_index=parent_chunk_index,
        )
    )
    return len(chunks) - 1


def chunk_pages(pages: list[ParsedPage]) -> list[ChunkCandidate]:
    """Walk every block across every page in order and emit `ChunkCandidate`s."""
    encoder = _encoder()
    median_body = _median_body_font_size(pages)

    chunks: list[ChunkCandidate] = []
    acc = _Accumulator(section_path=[])
    section_path: list[str] = []

    for page in pages:
        for block in page.blocks:
            text_value = block.text.strip()
            if not text_value:
                continue

            if _is_footnote(block):
                # Attach to the last accumulator paragraph (or open a new one if empty).
                tokens = encoder.count(text_value)
                if acc.is_empty():
                    acc.section_path = section_path[:]
                acc.add(text=text_value, tokens=tokens, page_num=block.page_num)
                continue

            if _is_heading(block, median_body=median_body):
                if acc.tokens >= _HEADING_MIN_FLUSH:
                    _emit(acc, chunks=chunks)
                    acc.reset(section_path=section_path[:])
                section_path = [text_value]
                acc.section_path = section_path[:]
                tokens = encoder.count(text_value)
                acc.add(text=text_value, tokens=tokens, page_num=block.page_num)
                continue

            # Paragraph
            tokens = encoder.count(text_value)
            if tokens > _HARD_CAP:
                # Single paragraph exceeds hard cap — sentence-split it and emit a parent group.
                if not acc.is_empty():
                    _emit(acc, chunks=chunks)
                    acc.reset(section_path=section_path[:])
                logger.warning(
                    "chunking.hard_split",
                    reason="paragraph_exceeds_hard_cap",
                    page_num=block.page_num,
                    tokens=tokens,
                )
                sentences = _split_sentences(text_value, encoder=encoder)
                parent_idx: int | None = None
                buf: list[str] = []
                buf_tokens = 0
                for sentence in sentences:
                    s_tokens = encoder.count(sentence)
                    if buf_tokens + s_tokens > _SOFT_CAP_MAX and buf:
                        sub_acc = _Accumulator(section_path=section_path[:])
                        sub_acc.add(
                            text=" ".join(buf).strip(),
                            tokens=buf_tokens,
                            page_num=block.page_num,
                        )
                        emitted = _emit(
                            sub_acc, chunks=chunks, parent_chunk_index=parent_idx
                        )
                        if parent_idx is None:
                            parent_idx = emitted
                        buf, buf_tokens = [], 0
                    buf.append(sentence)
                    buf_tokens += s_tokens
                if buf:
                    sub_acc = _Accumulator(section_path=section_path[:])
                    sub_acc.add(
                        text=" ".join(buf).strip(),
                        tokens=buf_tokens,
                        page_num=block.page_num,
                    )
                    emitted = _emit(sub_acc, chunks=chunks, parent_chunk_index=parent_idx)
                    if parent_idx is None:
                        parent_idx = emitted
                continue

            if acc.tokens + tokens > _HARD_CAP:
                # Would push us past hard cap — flush at sentence boundary first.
                emitted_text, leftover = _accumulator_split_at_sentence(
                    acc, encoder=encoder, target_tokens=_SOFT_CAP_MAX
                )
                if emitted_text:
                    flush_acc = _Accumulator(section_path=list(acc.section_path))
                    flush_acc.add(
                        text=emitted_text,
                        tokens=encoder.count(emitted_text),
                        page_num=acc.page_start or block.page_num,
                    )
                    flush_acc.page_start = acc.page_start
                    flush_acc.page_end = acc.page_end
                    _emit(flush_acc, chunks=chunks)
                acc = leftover or _Accumulator(section_path=section_path[:])
                if not acc.section_path:
                    acc.section_path = section_path[:]

            acc.add(text=text_value, tokens=tokens, page_num=block.page_num)

            if acc.tokens >= _SOFT_CAP_MAX:
                # Soft cap reached — flush.
                _emit(acc, chunks=chunks)
                acc.reset(section_path=section_path[:])

    # Final flush
    if not acc.is_empty():
        _emit(acc, chunks=chunks)

    return chunks


__all__ = ["ChunkCandidate", "chunk_pages"]
