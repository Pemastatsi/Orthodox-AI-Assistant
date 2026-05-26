"""F-14: reference vectors for the quote-overlap algorithm.

Six vectors from `docs/contracts/quote-overlap-algorithm.md`. Implementations must match
each expected ratio within ±0.01.
"""

from __future__ import annotations

import pytest
from app.domain.services.quote_overlap import (
    QUOTE_OVERLAP_THRESHOLD,
    make_shingles,
    normalize,
    quote_overlap,
)


@pytest.mark.parametrize(
    "claim,source,expected",
    [
        # V1 — Exact match
        (
            "Pray without ceasing, says the Apostle.",
            "The Apostle teaches us: pray without ceasing, says the Apostle, in every season.",
            1.00,
        ),
        # V2 — Partial paraphrase
        (
            "Saint Basil writes that prayer requires deep humility.",
            "Saint Basil writes that prayer requires patience and steadfastness.",
            0.50,
        ),
        # V3 — No overlap (different topic)
        (
            "The liturgy begins with the great litany.",
            "Saint Basil writes about almsgiving and care for the poor.",
            0.00,
        ),
        # V4 — Diacritic-insensitive Greek (short-claim fallback hit)
        ("Κύριε ἐλέησον", "ψάλλομεν Κυριε ελεησον τρίτον", 1.00),
        # V5 — Short claim, fallback hit
        (
            "ancestral sin",
            "Orthodox theology distinguishes ancestral sin from original sin.",
            1.00,
        ),
        # V6 — Short claim, fallback miss
        (
            "ancestral sin",
            "Orthodox theology speaks of original guilt and inherited mortality.",
            0.00,
        ),
    ],
)
def test_reference_vectors(claim: str, source: str, expected: float) -> None:
    actual = quote_overlap(claim, source)
    assert abs(actual - expected) < 0.01, (
        f"claim={claim!r} source={source!r} expected={expected} got={actual}"
    )


def test_threshold_is_platform_fixed() -> None:
    """ADR-0002 + quote-overlap-algorithm.md §Threshold: 0.70 is platform-fixed in Phase 1."""
    assert QUOTE_OVERLAP_THRESHOLD == 0.70


def test_normalize_strips_diacritics_and_punctuation() -> None:
    tokens = normalize("Saint Basil, on prayer — humility, patience!")
    assert tokens == ["saint", "basil", "on", "prayer", "humility", "patience"]


def test_normalize_handles_polytonic_greek() -> None:
    tokens = normalize("Κύριε, ἐλέησον.")
    # Casefold + Mn-strip + punctuation→space.
    assert tokens == ["κυριε", "ελεησον"]


def test_make_shingles_returns_empty_for_short_input() -> None:
    assert make_shingles(["a", "b"], n=5) == set()


def test_make_shingles_collapses_duplicates() -> None:
    # The repeated 5-window "a b c d e" appears at index 0 and again at index 5.
    tokens = ["a", "b", "c", "d", "e", "a", "b", "c", "d", "e"]
    shingles = make_shingles(tokens, n=5)
    # 6 windows in total (indices 0..5); set dedups the index-0/index-5 duplicate → 5.
    assert len(shingles) == 5
    assert "a b c d e" in shingles


def test_quote_overlap_zero_for_empty_claim() -> None:
    assert quote_overlap("", "some source text") == 0.0


def test_quote_overlap_asymmetric_denominator_matches_contract() -> None:
    """Denominator MUST be |claim_shingles|, not |claim_shingles ∪ source_shingles|.

    Contract: "the denominator is |claim_shingles| (asymmetric containment) so that long
    source chunks do not dilute the score."
    """
    # Short claim entirely contained in a much longer source.
    claim = "the lord said pray without ceasing in every season for prayer"
    source = " ".join([claim] + ["padding word"] * 200)
    ratio = quote_overlap(claim, source)
    # Every claim shingle must appear in source → ratio ≈ 1.0, regardless of source length.
    assert ratio == 1.0
