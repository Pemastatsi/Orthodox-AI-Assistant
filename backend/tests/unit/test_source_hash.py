"""Source/chunk hash format conforms to approved-decisions-register.md row J."""

from __future__ import annotations

import re

from app.domain.repositories.chunk_repository import compute_chunk_hash
from app.domain.repositories.source_repository import compute_source_hash

_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def test_source_hash_format() -> None:
    h = compute_source_hash(b"abc")
    assert _SHA256_PATTERN.match(h), h


def test_source_hash_is_deterministic() -> None:
    assert compute_source_hash(b"abc") == compute_source_hash(b"abc")
    assert compute_source_hash(b"abc") != compute_source_hash(b"abd")


def test_chunk_hash_format_and_determinism() -> None:
    h1 = compute_chunk_hash(
        source_hash="sha256:" + "a" * 64,
        text_value="The body text.",
        section_path=["Book I", "Chapter 1"],
    )
    h2 = compute_chunk_hash(
        source_hash="sha256:" + "a" * 64,
        text_value="The body text.",
        section_path=["Book I", "Chapter 1"],
    )
    assert h1 == h2
    assert _SHA256_PATTERN.match(h1), h1


def test_chunk_hash_changes_with_section_path() -> None:
    a = compute_chunk_hash(
        source_hash="sha256:" + "a" * 64,
        text_value="t",
        section_path=["A"],
    )
    b = compute_chunk_hash(
        source_hash="sha256:" + "a" * 64,
        text_value="t",
        section_path=["B"],
    )
    assert a != b
