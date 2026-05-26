"""Shingle-based quote-overlap for A6 verification.

Implements `docs/contracts/quote-overlap-algorithm.md` exactly. The 0.70 threshold and
algorithm shape are platform-fixed in Phase 1 and shared across providers so that
verification stays comparable across runs.
"""

from __future__ import annotations

import unicodedata
from typing import Final

SHINGLE_SIZE: Final[int] = 5
QUOTE_OVERLAP_THRESHOLD: Final[float] = 0.70


def normalize(text: str) -> list[str]:
    """NFKC + casefold + strip Mn diacritics + replace P punctuation with space + tokenize."""
    nfkc = unicodedata.normalize("NFKC", text)
    folded = nfkc.casefold()
    decomposed = unicodedata.normalize("NFD", folded)
    cleaned_chars: list[str] = []
    for ch in decomposed:
        category = unicodedata.category(ch)
        if category == "Mn":
            continue
        if category.startswith("P"):
            cleaned_chars.append(" ")
            continue
        cleaned_chars.append(ch)
    collapsed = "".join(cleaned_chars)
    return collapsed.split()


def make_shingles(tokens: list[str], n: int = SHINGLE_SIZE) -> set[str]:
    if len(tokens) < n:
        return set()
    return {" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def quote_overlap(claim_text: str, source_text: str, *, n: int = SHINGLE_SIZE) -> float:
    """Return the asymmetric containment ratio of `claim_text` shingles in `source_text`.

    Short claims (fewer than `n` tokens after normalization) fall back to exact substring
    containment in the normalized form — returns 1.0 if contained, 0.0 otherwise.
    """
    claim_tokens = normalize(claim_text)
    source_tokens = normalize(source_text)

    if len(claim_tokens) < n:
        joined_claim = " ".join(claim_tokens)
        joined_source = " ".join(source_tokens)
        if not joined_claim:
            return 0.0
        return 1.0 if joined_claim in joined_source else 0.0

    claim_shingles = make_shingles(claim_tokens, n)
    if not claim_shingles:
        return 0.0
    source_shingles = make_shingles(source_tokens, n)
    return len(claim_shingles & source_shingles) / len(claim_shingles)


__all__ = [
    "QUOTE_OVERLAP_THRESHOLD",
    "SHINGLE_SIZE",
    "make_shingles",
    "normalize",
    "quote_overlap",
]
