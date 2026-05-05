"""Unit tests for the A6 quote-overlap algorithm.

Audit finding: F-14
Context citations:
  - docs/contracts/quote-overlap-algorithm.md — algorithm spec + V1–V6 reference vectors
  - docs/task_cards/phase1/T-004-evidence-composer-verifier.md — Acceptance Tests
  - AGENTS.md "Citation Rules": quote overlap threshold defaults to 70%

This skeleton encodes V1–V6 from docs/contracts/quote-overlap-algorithm.md.
Implementation is pending T-004 (evidence-composer-verifier). Removing the
pytest.skip() calls and filling in the import makes the tests immediately
meaningful when the code lands.

Each vector: (vector_id, claim_text, source_text, expected_ratio)
Expected ratio must match within ±0.01 per the algorithm contract.
"""
import sys
import pytest

pytest.importorskip("app", reason="awaits T-001 backend scaffold")

# ---------------------------------------------------------------------------
# Reference vectors — sourced verbatim from docs/contracts/quote-overlap-algorithm.md
# ---------------------------------------------------------------------------
#
# Format: (vector_id, claim_text, source_text, expected_ratio)
# expected_ratio is rounded to 2 dp; implementations must match within ±0.01.
#
REFERENCE_VECTORS = [
    (
        "V1",
        "Pray without ceasing, says the Apostle.",
        "The Apostle teaches us: pray without ceasing, says the Apostle, in every season.",
        1.00,
    ),
    (
        "V2",
        "Saint Basil writes that prayer requires deep humility.",
        "Saint Basil writes that prayer requires patience and steadfastness.",
        0.50,
    ),
    (
        "V3",
        "The liturgy begins with the great litany.",
        "Saint Basil writes about almsgiving and care for the poor.",
        0.00,
    ),
    (
        "V4",
        # Diacritic-insensitive Greek — short-claim fallback (< n=5 tokens)
        "Κύριε ἐλέησον",
        "ψάλλομεν Κυριε ελεησον τρίτον",
        1.00,
    ),
    (
        "V5",
        # Short claim, fallback hit
        "ancestral sin",
        "Orthodox theology distinguishes ancestral sin from original sin.",
        1.00,
    ),
    (
        "V6",
        # Short claim, fallback miss
        "ancestral sin",
        "Orthodox theology speaks of original guilt and inherited mortality.",
        0.00,
    ),
]


# ---------------------------------------------------------------------------
# Parametrized skeleton test
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("vector_id,claim,evidence,expected_ratio", REFERENCE_VECTORS)
def test_compute_overlap_reference_vectors(
    vector_id: str, claim: str, evidence: str, expected_ratio: float
):
    """compute_overlap(claim, evidence) must equal expected_ratio within ±0.01.

    Vectors V1–V6 are the normative reference from
    docs/contracts/quote-overlap-algorithm.md. Any implementation change that
    breaks these vectors must update the contract document, bump the algorithm
    version, and re-run the full safety suite.
    """
    pytest.skip(
        f"pending T-004 implementation: compute_overlap() not yet implemented "
        f"(vector {vector_id})"
    )
    # When implementation lands, replace with:
    # from app.domain.services.quote_overlap import compute_overlap
    # result = compute_overlap(claim, evidence)
    # assert result == pytest.approx(expected_ratio, abs=0.01), (
    #     f"[{vector_id}] compute_overlap({claim!r}, {evidence!r}) "
    #     f"returned {result!r}, expected {expected_ratio!r} ±0.01. "
    #     f"Python version: {sys.version}"
    # )


def test_reference_vectors_cover_all_six():
    """Meta-test: the REFERENCE_VECTORS constant must have exactly 6 entries
    keyed V1–V6, matching docs/contracts/quote-overlap-algorithm.md.
    """
    ids = [v[0] for v in REFERENCE_VECTORS]
    assert ids == ["V1", "V2", "V3", "V4", "V5", "V6"], (
        f"REFERENCE_VECTORS must have exactly V1–V6 in order; got {ids}"
    )
