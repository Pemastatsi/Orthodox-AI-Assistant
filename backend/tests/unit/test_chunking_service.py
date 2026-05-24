"""Unit tests for the hierarchical chunking service (chunking-contract.md / ADR-0009).

These tests are pure-Python and require only `tiktoken` at runtime.
"""

from __future__ import annotations

import pytest
from app.adapters.parsers.base import ParsedBlock, ParsedPage
from app.domain.services.chunking_service import (
    _HARD_CAP,
    chunk_pages,
)


def _heading(text: str, page: int = 1, font_size: float = 16.0) -> ParsedBlock:
    return ParsedBlock(
        text=text,
        block_type="heading",
        font_size=font_size,
        bold=True,
        bbox=(0, 0, 500, 20),
        page_num=page,
    )


def _para(text: str, page: int = 1, font_size: float = 11.0) -> ParsedBlock:
    return ParsedBlock(
        text=text,
        block_type="paragraph",
        font_size=font_size,
        bold=False,
        bbox=(0, 0, 500, 20),
        page_num=page,
    )


def _footnote(text: str, page: int = 1) -> ParsedBlock:
    return ParsedBlock(
        text=text,
        block_type="footnote",
        font_size=9.0,
        bold=False,
        bbox=(0, 700, 500, 720),
        page_num=page,
    )


def _page(num: int, blocks: list[ParsedBlock]) -> ParsedPage:
    return ParsedPage(page_num=num, blocks=blocks)


def _long_para(token_words: int, page: int = 1) -> ParsedBlock:
    return _para(" ".join(f"word{i}" for i in range(token_words)), page=page)


def test_empty_input_yields_no_chunks() -> None:
    assert chunk_pages([]) == []


def test_single_short_paragraph_yields_one_chunk() -> None:
    pages = [_page(1, [_para("Hello world. Short body.")])]
    chunks = chunk_pages(pages)
    assert len(chunks) == 1
    assert chunks[0].text.startswith("Hello world")
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 1
    assert chunks[0].section_path == []
    assert chunks[0].parent_chunk_index is None


def test_heading_followed_by_paragraph_sets_section_path() -> None:
    pages = [
        _page(1, [
            _heading("Chapter Four", page=1),
            _para("Body paragraph under chapter four.", page=1),
        ])
    ]
    chunks = chunk_pages(pages)
    assert len(chunks) == 1
    assert chunks[0].section_path == ["Chapter Four"]


def test_heading_flushes_when_accumulator_above_threshold() -> None:
    # First section: ~600 tokens of body. Then a heading. Should flush the section before heading.
    page1 = _page(1, [
        _heading("Section A", page=1),
        _long_para(600, page=1),
    ])
    page2 = _page(2, [
        _heading("Section B", page=2),
        _para("Section B body.", page=2),
    ])
    chunks = chunk_pages([page1, page2])
    paths = [c.section_path for c in chunks]
    # Section A flushes before Section B; the body of A becomes its own chunk; B starts a new one.
    assert ["Section A"] in paths
    assert ["Section B"] in paths
    assert all(len(p) == 1 for p in paths)


def test_soft_cap_triggers_flush() -> None:
    # Big enough to exceed the 1200-token soft cap with the whitespace fallback (~1.3 tokens/word).
    blocks = [_long_para(120, page=1) for _ in range(20)]
    chunks = chunk_pages([_page(1, blocks)])
    assert len(chunks) >= 2, "expected the soft cap to produce more than one chunk"


def test_hard_split_logs_warning_and_splits_paragraph(caplog: pytest.LogCaptureFixture) -> None:
    huge = _long_para(_HARD_CAP + 200, page=1)
    chunks = chunk_pages([_page(1, [huge])])
    assert len(chunks) >= 2
    parents = [c for c in chunks if c.parent_chunk_index is None]
    children = [c for c in chunks if c.parent_chunk_index is not None]
    assert parents, "first sub-chunk should be the parent (parent_chunk_index=None)"
    assert children, "subsequent sub-chunks should reference a parent index"
    parent_index = chunks.index(parents[0])
    for c in children:
        assert c.parent_chunk_index == parent_index


def test_footnote_folds_into_preceding_paragraph() -> None:
    pages = [_page(1, [
        _para("Main body paragraph.", page=1),
        _footnote("1. Footnote text here.", page=1),
    ])]
    chunks = chunk_pages(pages)
    assert len(chunks) == 1
    assert "Footnote text here" in chunks[0].text


def test_section_path_resets_at_each_heading() -> None:
    # Each section needs ≥ 200 tokens of body for the heading boundary rule to flush.
    pages = [_page(1, [
        _heading("Heading One"),
        _long_para(200),
        _heading("Heading Two"),
        _long_para(200),
    ])]
    chunks = chunk_pages(pages)
    paths = [c.section_path for c in chunks]
    assert ["Heading One"] in paths
    assert ["Heading Two"] in paths


def test_chunk_text_never_exceeds_hard_cap_after_emission() -> None:
    # Use the module's own tokenizer so the test works in offline CI (tiktoken auto-falls back
    # when the BPE files can't be fetched).
    from app.domain.services.chunking_service import _Tokenizer

    tok = _Tokenizer()
    huge = _long_para(_HARD_CAP * 2, page=1)
    chunks = chunk_pages([_page(1, [huge])])
    for c in chunks:
        assert tok.count(c.text) <= _HARD_CAP, "no chunk should exceed the hard cap"


def test_page_start_and_end_track_correctly_across_pages() -> None:
    pages = [
        _page(1, [_para("Page one body.", page=1)]),
        _page(2, [_para("Page two body.", page=2)]),
    ]
    chunks = chunk_pages(pages)
    starts = {c.page_start for c in chunks}
    ends = {c.page_end for c in chunks}
    assert 1 in starts
    assert 2 in ends


def test_determinism_same_input_same_output() -> None:
    pages = [_page(1, [_heading("H"), _para("body. " * 200)])]
    a = chunk_pages(pages)
    b = chunk_pages(pages)
    assert [c.text for c in a] == [c.text for c in b]
    assert [c.section_path for c in a] == [c.section_path for c in b]
