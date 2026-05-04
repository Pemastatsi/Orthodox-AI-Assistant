"""Integration tests for tenant isolation invariants.

Audit finding: F-13
Context citations:
  - docs/contracts/phase1-implementation-contract.md — Phase 1 → Phase 2 Exit Criteria #5
  - tests/fixtures/corpus/tiny_other_tenant_corpus.json — isolationCases block
  - docs/contracts/cache-key.md — tenantId is a required cache-key field
  - docs/contracts/observability.md — run_traces.stages[] must not leak cross-tenant data
  - docs/task_cards/phase1/T-005-cache-logs-billing.md — Acceptance Tests

This file is the NAMED OWNER of the tenant-isolation invariant per
phase1-implementation-contract.md exit criterion #5. Implementation is pending
T-002 (ingestion), T-003 (retrieval), and T-005 (cache/logs/billing).

Fixture reference — isolationCases from tiny_other_tenant_corpus.json:
  tenant_a_query_about_prayer:
    submittingTenant: orthodox_ethos_v1
    query: "What do the Fathers teach about prayer?"
    mustNotReturnChunkIds: ["chunk-other-prayer-001"]
  tenant_a_query_about_eucharist:
    submittingTenant: orthodox_ethos_v1
    query: "What is the Orthodox view of the Eucharist?"
    mustNotReturnChunkIds: ["chunk-other-eucharist-001"]
  tenant_a_query_about_philokalia:
    submittingTenant: orthodox_ethos_v1
    query: "Tell me about the Philokalia."
    mustNotReturnChunkIds: ["chunk-other-philokalia-001"]

Zero cross-tenant leaks are required for Phase 1 → 2 gate.
"""
import json
from pathlib import Path
import pytest

pytest.importorskip("app", reason="awaits T-001 backend scaffold")

# ---------------------------------------------------------------------------
# Fixture data — sourced directly from the canonical JSON fixture.
# ---------------------------------------------------------------------------

_FIXTURE_PATH = (
    Path(__file__).parent.parent
    / "fixtures"
    / "corpus"
    / "tiny_other_tenant_corpus.json"
)

with open(_FIXTURE_PATH, encoding="utf-8") as _f:
    _OTHER_TENANT_FIXTURE = json.load(_f)

_ISOLATION_CASES = _OTHER_TENANT_FIXTURE["isolationCases"]

# Derived constants for assertion bodies
_TENANT_A_ID = "orthodox_ethos_v1"
_TENANT_B_ID = _OTHER_TENANT_FIXTURE["tenantId"]  # "other_tenant_v1"

# All chunk IDs that must NEVER appear in Tenant A results
_ALL_MUST_NOT_CHUNK_IDS: set[str] = set()
for _case in _ISOLATION_CASES.values():
    _ALL_MUST_NOT_CHUNK_IDS.update(_case["mustNotReturnChunkIds"])

# Query list for parametrized tests
_ISOLATION_QUERY_PARAMS = [
    (case_id, case["query"], set(case["mustNotReturnChunkIds"]))
    for case_id, case in _ISOLATION_CASES.items()
]


# ---------------------------------------------------------------------------
# Test stubs
# ---------------------------------------------------------------------------


def test_a3_retrieval_excludes_other_tenant_chunks():
    """Submit Tenant A's three queries from
    tests/fixtures/corpus/tiny_other_tenant_corpus.json#/isolationCases.
    Assert mustNotReturnChunkIds DO NOT appear in A3 retrieval results.
    """
    pytest.skip("pending T-003 implementation: A3 retrieval Qdrant tenant filter not yet wired")
    # When implementation lands, replace with:
    # from app.domain.services.retrieval_service import RetrievalService
    # from app.domain.models.principal import Principal
    # principal = Principal(tenantId=_TENANT_A_ID, role="member", userId="u_test")
    # service = RetrievalService(...)
    # for case_id, query, must_not_ids in _ISOLATION_QUERY_PARAMS:
    #     candidates = service.retrieve(query=query, principal=principal)
    #     returned_ids = {c.chunkId for c in candidates}
    #     assert returned_ids.isdisjoint(must_not_ids), (
    #         f"[{case_id}] A3 returned cross-tenant chunk(s): "
    #         f"{returned_ids & must_not_ids}"
    #     )


def test_a4_admission_excludes_other_tenant_chunks():
    """For the same queries, assert mustNotReturnChunkIds DO NOT appear
    in A4 admittedChunks NOR in suppressedChunkIds (a chunk from another
    tenant should never even be considered for suppression — it should
    not be retrieved at all).
    """
    pytest.skip("pending T-004 implementation: A4 evidence packager not yet implemented")
    # When implementation lands, replace with:
    # from app.domain.services.evidence_packager import EvidencePackager
    # for case_id, query, must_not_ids in _ISOLATION_QUERY_PARAMS:
    #     packet = EvidencePackager(...).pack(query=query, principal=...)
    #     admitted_ids = {c.chunkId for c in packet.admittedChunks}
    #     suppressed_ids = {c.chunkId for c in packet.suppressedChunks}
    #     considered = admitted_ids | suppressed_ids
    #     assert considered.isdisjoint(must_not_ids), (
    #         f"[{case_id}] A4 considered cross-tenant chunk(s): "
    #         f"{considered & must_not_ids}"
    #     )


def test_response_citations_exclude_other_tenant_chunks():
    """For the same queries, assert mustNotReturnChunkIds DO NOT appear
    in any final VerifiedResponse.citations[].chunkId.
    """
    pytest.skip("pending T-004 implementation: VerifiedResponse.citations not yet produced by A5/A6")
    # When implementation lands, replace with:
    # from app.domain.services.query_pipeline import QueryPipeline
    # for case_id, query, must_not_ids in _ISOLATION_QUERY_PARAMS:
    #     response = QueryPipeline(...).run(query=query, principal=...)
    #     cited_ids = {c.chunkId for c in response.citations}
    #     assert cited_ids.isdisjoint(must_not_ids), (
    #         f"[{case_id}] VerifiedResponse cited cross-tenant chunk(s): "
    #         f"{cited_ids & must_not_ids}"
    #     )


def test_cache_keys_differ_across_tenants():
    """Identical query strings issued by Tenant A and Tenant B MUST
    produce different cache keys (per cache-key.md tenantId is in the
    canonical input).
    """
    pytest.skip("pending T-005 implementation: cache_key() not yet implemented")
    # When implementation lands, replace with:
    # from app.domain.services.cache_service import cache_key, normalize_query
    # base_fields = {
    #     "queryNormalized": normalize_query("What do the Fathers teach about prayer?"),
    #     "role": "member",
    #     "sessionHash": None,
    #     "answerMode": "consensus",
    #     "corpusVersion": "fixture-2026-05-02",
    #     "promptVersion": "a5_compose@2026-05-01.1",
    #     "modelRouteId": "a5_compose_anthropic@2026-05-01.1",
    #     "schemaVersion": "2026-05-01.1",
    #     "configVersion": "2026-05-01.1",
    #     "calendarVersion": "2026-05-01.1",
    # }
    # key_a = cache_key({**base_fields, "tenantId": _TENANT_A_ID})
    # key_b = cache_key({**base_fields, "tenantId": _TENANT_B_ID})
    # assert key_a != key_b, (
    #     "Cache keys must differ across tenants; identical key would allow cross-tenant cache hit."
    # )


def test_run_trace_stages_exclude_other_tenant_data():
    """For the queries above, no run_traces.stages[] entry for Tenant A
    references chunkIds, sourceIds, or tenantIds belonging to Tenant B.
    """
    pytest.skip("pending T-005 implementation: run_traces persistence not yet implemented")
    # When implementation lands, replace with:
    # from app.domain.services.query_pipeline import QueryPipeline
    # from app.domain.repositories.run_trace_repository import RunTraceRepository
    # for case_id, query, must_not_ids in _ISOLATION_QUERY_PARAMS:
    #     response = QueryPipeline(...).run(query=query, principal=...)
    #     trace = RunTraceRepository(...).get(response.runId)
    #     for stage in trace.stages:
    #         stage_json = json.dumps(stage)
    #         for bad_id in must_not_ids:
    #             assert bad_id not in stage_json, (
    #                 f"[{case_id}] run_traces.stages contains cross-tenant chunkId {bad_id!r}"
    #             )
    #         assert _TENANT_B_ID not in stage_json, (
    #             f"[{case_id}] run_traces.stages references Tenant B id {_TENANT_B_ID!r}"
    #         )


def test_admin_queries_excludes_other_tenant_runs():
    """An admin in Tenant A calling /admin/queries does NOT see any rows
    where tenant_id != tn_orthodoxethos (the Tenant A id in the fixture).
    """
    pytest.skip("pending T-006 implementation: /admin/queries endpoint not yet implemented")
    # When implementation lands, replace with:
    # from app.api.routes.admin import get_queries
    # from app.domain.models.principal import Principal
    # admin_principal = Principal(tenantId="tn_orthodoxethos", role="admin", userId="u_admin_test")
    # rows = get_queries(principal=admin_principal, ...)
    # for row in rows:
    #     assert row.tenantId == "tn_orthodoxethos", (
    #         f"/admin/queries returned a row for tenant {row.tenantId!r}; "
    #         "expected only 'tn_orthodoxethos'"
    #     )
