"""End-to-end integration test stub for T-003 (query analyzer + retrieval).

Audit finding: A-14
Context citations:
  - docs/task_cards/phase1/T-003-query-analyzer-retrieval.md (Acceptance Tests
    references this exact test path).
  - docs/schemas/classified-query.schema.json
  - docs/schemas/retrieval-plan.schema.json
  - docs/contracts/code-gen-guide.md (tenant_id injection rules)

Skipped until T-001 (backend scaffold) and T-003 (A1/A2/A3) land.
"""
import pytest

pytest.importorskip("app", reason="awaits T-001 backend scaffold")


def test_classify_then_retrieve_against_fixture():
    """A1/A2 produces a ClassifiedQuery + RetrievalPlan, and A3 retrieves
    expected approved chunks from the fixture corpus.

    Steps the implementation MUST satisfy when T-003 lands:
      1. Load tests/fixtures/corpus/tiny_approved_corpus.json into Qdrant
         under tenant=tn_orthodoxethos.
      2. Submit the canonical "what do the fathers teach about prayer?" query
         to the QueryAnalyzer.
      3. Assert ClassifiedQuery has the expected sensitivityPrimary='normal'
         and rawQuery preserved verbatim.
      4. Assert RetrievalPlan.semanticQuery equals
         classifiedQuery.reframedQuery ?? classifiedQuery.rawQuery
         (per phase1-implementation-contract.md "Query Behavior").
      5. Assert that even if A2 emits a different tenantId in the plan body,
         the Qdrant adapter overwrites it with Principal.tenantId at the
         filter boundary (per docs/contracts/code-gen-guide.md §8.1).
      6. Assert A3 returns >= 1 chunk and that every returned chunk has
         tenant_id == Principal.tenantId AND approved == true.
    """
    pytest.skip(
        "pending T-003 implementation: classify_then_retrieve_against_fixture "
        "requires the QueryAnalyzer (A1/A2) and A3 retrieval"
    )
