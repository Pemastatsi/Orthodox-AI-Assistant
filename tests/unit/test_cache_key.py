"""Unit tests for the response cache-key algorithm.

Audit finding: F-15
Context citations:
  - docs/contracts/cache-key.md — algorithm spec + V1–V4 reference vectors
  - docs/task_cards/phase1/T-005-cache-logs-billing.md — Acceptance Tests
  - AGENTS.md "Cache, Billing, Logs": cache keys include tenant, role, session, versions

This skeleton encodes V1–V4 from docs/contracts/cache-key.md. Implementation
is pending T-005 (cache-logs-billing). Removing the pytest.skip() calls and
filling in the import makes the tests immediately meaningful when the code lands.

Two assertions per vector (per the Wave 4 audit spec):
  1. hashlib.sha256(canonical_json_bytes).hexdigest() == expected_sha256
     (literal byte hash — catches encoding regressions)
  2. compute_cache_key(input_dict) == expected_sha256
     (algorithm produces the same value from the input dict — catches algorithm regressions)

V3 (Greek) is casefold-dependent; Python version is printed in failure messages
so regressions are debuggable.
"""
import hashlib
import json
import sys

import pytest

pytest.importorskip("app", reason="awaits T-001 backend scaffold")


# ---------------------------------------------------------------------------
# Reference vectors — sourced verbatim from docs/contracts/cache-key.md
# ---------------------------------------------------------------------------
#
# Format: (vector_id, input_dict, canonical_json_str, expected_sha256)
#
# canonical_json_str is the exact bytes the algorithm produces; hashing it
# with sha256 must yield expected_sha256 byte-for-byte.
#
# Note on V3: the input dict already carries the casefolded query string
# (Greek final-sigma ς → σ, per Unicode casefold). The normalize_query()
# step runs before cache_key() in production; the test vectors encode the
# post-normalization state.
#

_V1_INPUT = {
    "tenantId": "tn_orthodoxethos",
    "queryNormalized": "what do the fathers teach about prayer?",
    "role": "member",
    "sessionHash": None,
    "answerMode": "consensus",
    "corpusVersion": "2026-05-01.1",
    "promptVersion": "a5_compose@2026-05-01.1",
    "modelRouteId": "a5_compose_anthropic@2026-05-01.1",
    "schemaVersion": "2026-05-01.1",
    "configVersion": "2026-05-01.1",
    "calendarVersion": "2026-05-01.1",
}
_V1_CANONICAL = (
    '{"answerMode":"consensus","calendarVersion":"2026-05-01.1",'
    '"configVersion":"2026-05-01.1","corpusVersion":"2026-05-01.1",'
    '"modelRouteId":"a5_compose_anthropic@2026-05-01.1",'
    '"promptVersion":"a5_compose@2026-05-01.1",'
    '"queryNormalized":"what do the fathers teach about prayer?",'
    '"role":"member","schemaVersion":"2026-05-01.1","sessionHash":null,'
    '"tenantId":"tn_orthodoxethos"}'
)
_V1_SHA256 = "3747051a45549400be4f16d9340761023c213ec49bbc494096957c49a3b24478"

_V2_INPUT = {
    "tenantId": "tn_orthodoxethos",
    "queryNormalized": "tell me more.",
    "role": "member",
    "sessionHash": "sh_5f2a",
    "answerMode": "consensus",
    "corpusVersion": "2026-05-01.1",
    "promptVersion": "a5_compose@2026-05-01.1",
    "modelRouteId": "a5_compose_anthropic@2026-05-01.1",
    "schemaVersion": "2026-05-01.1",
    "configVersion": "2026-05-01.1",
    "calendarVersion": "2026-05-01.1",
}
_V2_CANONICAL = (
    '{"answerMode":"consensus","calendarVersion":"2026-05-01.1",'
    '"configVersion":"2026-05-01.1","corpusVersion":"2026-05-01.1",'
    '"modelRouteId":"a5_compose_anthropic@2026-05-01.1",'
    '"promptVersion":"a5_compose@2026-05-01.1",'
    '"queryNormalized":"tell me more.","role":"member",'
    '"schemaVersion":"2026-05-01.1","sessionHash":"sh_5f2a",'
    '"tenantId":"tn_orthodoxethos"}'
)
_V2_SHA256 = "002b80c9435eedc48f06966d5328883e63fae49d4a25162165937dfa2e9320d3"

# V3: Greek query, scholar role. queryNormalized already post-casefold
# (Greek final-sigma ς → σ is intentional per cache-key.md).
_V3_INPUT = {
    "tenantId": "tn_orthodoxethos",
    "queryNormalized": "τί διδάσκουν οἱ πατέρεσ περὶ προσευχῆσ;",
    "role": "scholar",
    "sessionHash": None,
    "answerMode": "consensus",
    "corpusVersion": "2026-05-01.1",
    "promptVersion": "a5_compose@2026-05-01.1",
    "modelRouteId": "a5_compose_anthropic@2026-05-01.1",
    "schemaVersion": "2026-05-01.1",
    "configVersion": "2026-05-01.1",
    "calendarVersion": "2026-05-01.1",
}
_V3_CANONICAL = (
    '{"answerMode":"consensus","calendarVersion":"2026-05-01.1",'
    '"configVersion":"2026-05-01.1","corpusVersion":"2026-05-01.1",'
    '"modelRouteId":"a5_compose_anthropic@2026-05-01.1",'
    '"promptVersion":"a5_compose@2026-05-01.1",'
    '"queryNormalized":"τί διδάσκουν οἱ πατέρεσ περὶ προσευχῆσ;",'
    '"role":"scholar","schemaVersion":"2026-05-01.1","sessionHash":null,'
    '"tenantId":"tn_orthodoxethos"}'
)
# Corrected value per cache-key.md 2026-05-02 revision
# (previous published value 9768d2ed... was wrong).
_V3_SHA256 = "ccf8de99418794534e41615ba8c81519155ca84dbbda2656b52b0fd1fcc3b0c8"

# V4: calendar-profile bump — must NOT collide with V1.
_V4_INPUT = {
    "tenantId": "tn_orthodoxethos",
    "queryNormalized": "what do the fathers teach about prayer?",
    "role": "member",
    "sessionHash": None,
    "answerMode": "consensus",
    "corpusVersion": "2026-05-01.1",
    "promptVersion": "a5_compose@2026-05-01.1",
    "modelRouteId": "a5_compose_anthropic@2026-05-01.1",
    "schemaVersion": "2026-05-01.1",
    "configVersion": "2026-05-01.2",
    "calendarVersion": "2026-05-02.1",
}
_V4_CANONICAL = (
    '{"answerMode":"consensus","calendarVersion":"2026-05-02.1",'
    '"configVersion":"2026-05-01.2","corpusVersion":"2026-05-01.1",'
    '"modelRouteId":"a5_compose_anthropic@2026-05-01.1",'
    '"promptVersion":"a5_compose@2026-05-01.1",'
    '"queryNormalized":"what do the fathers teach about prayer?",'
    '"role":"member","schemaVersion":"2026-05-01.1","sessionHash":null,'
    '"tenantId":"tn_orthodoxethos"}'
)
_V4_SHA256 = "2c15b2345f7c327e7ca29cd904da3f490b7532c055a74dad72c9671fcd121c19"

REFERENCE_VECTORS = [
    ("V1", _V1_INPUT, _V1_CANONICAL, _V1_SHA256),
    ("V2", _V2_INPUT, _V2_CANONICAL, _V2_SHA256),
    ("V3", _V3_INPUT, _V3_CANONICAL, _V3_SHA256),
    ("V4", _V4_INPUT, _V4_CANONICAL, _V4_SHA256),
]


# ---------------------------------------------------------------------------
# Assertion 1 — literal canonical-bytes hash (encoding regression guard)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("vector_id,input_dict,canonical_json,expected_sha256", REFERENCE_VECTORS)
def test_canonical_bytes_sha256(
    vector_id: str, input_dict: dict, canonical_json: str, expected_sha256: str
):
    """hashlib.sha256(canonical_json.encode('utf-8')).hexdigest() must equal
    the expected SHA-256 listed in docs/contracts/cache-key.md.

    This test guards against encoding regressions (wrong encoding, BOM,
    whitespace injection). It does NOT exercise the production code path —
    that is test_compute_cache_key_matches_sha256 below.
    """
    actual = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    assert actual == expected_sha256, (
        f"[{vector_id}] Literal canonical-bytes sha256 mismatch. "
        f"Expected: {expected_sha256!r}  Got: {actual!r}  "
        f"Python: {sys.version}"
    )


# ---------------------------------------------------------------------------
# Assertion 2 — algorithm produces same value from input dict
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("vector_id,input_dict,canonical_json,expected_sha256", REFERENCE_VECTORS)
def test_compute_cache_key_matches_sha256(
    vector_id: str, input_dict: dict, canonical_json: str, expected_sha256: str
):
    """compute_cache_key(input_dict) must equal the expected SHA-256.

    This test exercises the production code path end-to-end, catching
    algorithm regressions (wrong field order, extra whitespace, wrong
    separator, wrong hash function).

    Note: V3 (Greek query) is casefold-dependent. Python version is included
    in the assertion message to make casefold regressions debuggable.
    """
    pytest.skip("pending T-005 implementation: compute_cache_key() not yet implemented")
    # When implementation lands, replace with:
    # from app.domain.services.cache_service import compute_cache_key
    # actual = compute_cache_key(input_dict)
    # assert actual == expected_sha256, (
    #     f"[{vector_id}] compute_cache_key() mismatch. "
    #     f"Expected: {expected_sha256!r}  Got: {actual!r}  "
    #     f"Python: {sys.version}"
    # )


# ---------------------------------------------------------------------------
# Additional contract guards
# ---------------------------------------------------------------------------


def test_v4_does_not_collide_with_v1():
    """V4 (calendar-profile bump) MUST NOT produce the same sha256 as V1.

    A calendarVersion change is a tenant-wide cache flush per cache-key.md.
    Collision would mean the cache flush silently fails.
    """
    assert _V4_SHA256 != _V1_SHA256, (
        "V4 and V1 sha256 values must differ; a calendarVersion bump must flush the cache."
    )


def test_reference_vectors_cover_all_four():
    """Meta-test: REFERENCE_VECTORS must have exactly 4 entries keyed V1–V4."""
    ids = [v[0] for v in REFERENCE_VECTORS]
    assert ids == ["V1", "V2", "V3", "V4"], (
        f"REFERENCE_VECTORS must have exactly V1–V4 in order; got {ids}"
    )
