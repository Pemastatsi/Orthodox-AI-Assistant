"""End-to-end integration test stub for T-004 (evidence composer + verifier).

Audit finding: A-14
Context citations:
  - docs/task_cards/phase1/T-004-evidence-composer-verifier.md (Acceptance Tests
    references this exact test path).
  - docs/schemas/evidence-packet.schema.json
  - docs/schemas/verified-response.schema.json
  - docs/contracts/quote-overlap-algorithm.md

Skipped until T-001 (backend scaffold) and T-004 (A4/A5/A6) land.
"""
import pytest

pytest.importorskip("app", reason="awaits T-001 backend scaffold")


def test_admit_compose_verify_round_trip():
    """A4 admits chunks, A5 composes an answer, A6 verifies citations end-to-end.

    Steps the implementation MUST satisfy when T-004 lands:
      1. Construct an EvidencePacket from approved chunks (tests/fixtures/...)
         with at least one chunk whose visibility is 'member' (admin_only and
         suppressed are forbidden as user-facing evidence per ADR 0001 and
         enforced by the schema enum on EvidencePacket.admittedChunks[].visibility).
      2. Run A5 composition; assert the produced answer text references chunks
         only from the EvidencePacket.
      3. Run A6 verification; assert that for each citation, the recorded
         quoteOverlapRatio in RunTrace.stages[a6_verifier].details meets the
         platform-fixed 0.70 threshold (per quote-overlap-algorithm.md §Threshold).
      4. Assert the final VerifiedResponse.citations carry sourceHash, chunkHash,
         approved=true, and corpusOrigin (per verified-response.schema.json).
      5. Assert that admitting a chunk whose visibility is 'admin_only' or
         'suppressed' fails schema validation BEFORE A5 is invoked.
    """
    pytest.skip(
        "pending T-004 implementation: admit_compose_verify_round_trip "
        "requires A4 admission, A5 composition, and A6 verification"
    )
