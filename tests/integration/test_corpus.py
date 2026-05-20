"""Integration tests for corpus approval invariants.

Audit finding: F-12
Context citations:
  - docs/contracts/db-schema.md §Cross-Table Invariants #2 ("chunks.approved=true
    implies sources.approved=true") and #3 (source-approval cascade)
  - docs/task_cards/phase1/T-002-tenant-data-ingestion.md — Acceptance Tests
  - docs/contracts/phase1-implementation-contract.md — Data Contracts

This skeleton encodes the cross-table approval invariant. Implementation is pending
the named task card. See docs/contracts/db-schema.md §Cross-Table Invariants
for the authoritative rules.
"""
import pytest

pytest.importorskip("app", reason="awaits T-001 backend scaffold")


def test_chunk_approval_requires_source_approval():
    """A chunk can be approved=true only when its source.approved=true.

    Encodes the cross-table invariant from docs/contracts/db-schema.md
    §Cross-Table Invariants #2 ("chunks.approved=true implies sources.approved=true").
    Writing chunks.approved=true while sources.approved=false MUST raise
    a domain error and roll back the transaction.
    """
    pytest.skip("pending T-002 implementation: chunks.approved=true invariant requires source approval")
    # When implementation lands, replace with:
    # from app.domain.repositories.chunk_repository import ChunkRepository
    # from app.domain.repositories.source_repository import SourceRepository
    # from app.core.exceptions import DomainError
    # ... create a source with approved=False, attempt to set chunk.approved=True,
    # assert DomainError is raised and transaction is rolled back.


def test_source_un_approval_cascades_or_rejects():
    """Setting sources.approved=false while a chunk is approved must
    either cascade chunk approval to false or reject the source change
    with a clear error. Implementation MAY pick either, but the chosen
    behavior must be deterministic and tested.
    """
    pytest.skip("pending T-002 implementation: source un-approval cascade/reject behavior must be deterministic")
    # When implementation lands, replace with:
    # from app.domain.repositories.chunk_repository import ChunkRepository
    # from app.domain.repositories.source_repository import SourceRepository
    # ... create source with approved=True, approve a chunk, then set source.approved=False,
    # assert either: (a) chunk.approved cascades to False, OR (b) a clear domain error is raised.
    # Whichever branch is chosen must be consistent across all calls.
