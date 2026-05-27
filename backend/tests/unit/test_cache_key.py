"""F-15: cache-key reference vectors.

The four vectors V1, V2, V3, V4 in `docs/contracts/cache-key.md` are reproduced here
byte-for-byte. The contract states: "Any implementation change that breaks these tests
must bump `schemaVersion` or `promptVersion`/`modelRouteId` as appropriate, accept the
cache flush, and update this document."
"""

from __future__ import annotations

import hashlib
import json

import pytest
from app.domain.services.cache_service import (
    build_cache_fields,
    cache_key,
    normalize_query,
)

V1_FIELDS = {
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
V1_CANONICAL = (
    '{"answerMode":"consensus","calendarVersion":"2026-05-01.1",'
    '"configVersion":"2026-05-01.1","corpusVersion":"2026-05-01.1",'
    '"modelRouteId":"a5_compose_anthropic@2026-05-01.1",'
    '"promptVersion":"a5_compose@2026-05-01.1",'
    '"queryNormalized":"what do the fathers teach about prayer?",'
    '"role":"member","schemaVersion":"2026-05-01.1","sessionHash":null,'
    '"tenantId":"tn_orthodoxethos"}'
)
V1_SHA256 = "3747051a45549400be4f16d9340761023c213ec49bbc494096957c49a3b24478"

V2_FIELDS = {
    **V1_FIELDS,
    "queryNormalized": "tell me more.",
    "sessionHash": "sh_5f2a",
}
V2_CANONICAL = (
    '{"answerMode":"consensus","calendarVersion":"2026-05-01.1",'
    '"configVersion":"2026-05-01.1","corpusVersion":"2026-05-01.1",'
    '"modelRouteId":"a5_compose_anthropic@2026-05-01.1",'
    '"promptVersion":"a5_compose@2026-05-01.1",'
    '"queryNormalized":"tell me more.","role":"member",'
    '"schemaVersion":"2026-05-01.1","sessionHash":"sh_5f2a",'
    '"tenantId":"tn_orthodoxethos"}'
)
V2_SHA256 = "002b80c9435eedc48f06966d5328883e63fae49d4a25162165937dfa2e9320d3"

V3_FIELDS = {
    **V1_FIELDS,
    "queryNormalized": "τί διδάσκουν οἱ πατέρεσ περὶ προσευχῆσ;",
    "role": "scholar",
}
V3_CANONICAL = (
    '{"answerMode":"consensus","calendarVersion":"2026-05-01.1",'
    '"configVersion":"2026-05-01.1","corpusVersion":"2026-05-01.1",'
    '"modelRouteId":"a5_compose_anthropic@2026-05-01.1",'
    '"promptVersion":"a5_compose@2026-05-01.1",'
    '"queryNormalized":"τί διδάσκουν οἱ πατέρεσ περὶ προσευχῆσ;",'
    '"role":"scholar","schemaVersion":"2026-05-01.1","sessionHash":null,'
    '"tenantId":"tn_orthodoxethos"}'
)
V3_SHA256 = "ccf8de99418794534e41615ba8c81519155ca84dbbda2656b52b0fd1fcc3b0c8"

V4_FIELDS = {
    **V1_FIELDS,
    "configVersion": "2026-05-01.2",
    "calendarVersion": "2026-05-02.1",
}
V4_CANONICAL = (
    '{"answerMode":"consensus","calendarVersion":"2026-05-02.1",'
    '"configVersion":"2026-05-01.2","corpusVersion":"2026-05-01.1",'
    '"modelRouteId":"a5_compose_anthropic@2026-05-01.1",'
    '"promptVersion":"a5_compose@2026-05-01.1",'
    '"queryNormalized":"what do the fathers teach about prayer?",'
    '"role":"member","schemaVersion":"2026-05-01.1","sessionHash":null,'
    '"tenantId":"tn_orthodoxethos"}'
)
V4_SHA256 = "2c15b2345f7c327e7ca29cd904da3f490b7532c055a74dad72c9671fcd121c19"


@pytest.mark.parametrize(
    "fields,canonical,expected_sha",
    [
        (V1_FIELDS, V1_CANONICAL, V1_SHA256),
        (V2_FIELDS, V2_CANONICAL, V2_SHA256),
        (V3_FIELDS, V3_CANONICAL, V3_SHA256),
        (V4_FIELDS, V4_CANONICAL, V4_SHA256),
    ],
    ids=["V1", "V2", "V3", "V4"],
)
def test_reference_vector_matches_contract(
    fields: dict, canonical: str, expected_sha: str
) -> None:
    actual_canonical = json.dumps(
        fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    assert actual_canonical == canonical, "canonical JSON drift from contract"

    literal_sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert literal_sha == expected_sha, "contract literal-SHA drift"

    assert cache_key(fields) == expected_sha


def test_v1_v4_do_not_collide() -> None:
    """A calendar-profile bump must flush the cache scope, not collide with V1."""
    assert cache_key(V1_FIELDS) != cache_key(V4_FIELDS)


def test_cache_key_rejects_extra_field() -> None:
    bad = {**V1_FIELDS, "requestId": "rq_01"}
    with pytest.raises(ValueError, match="extra="):
        cache_key(bad)


def test_cache_key_rejects_missing_field() -> None:
    bad = {k: v for k, v in V1_FIELDS.items() if k != "calendarVersion"}
    with pytest.raises(ValueError, match="missing="):
        cache_key(bad)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("  Hello   World  ", "hello world"),
        ("PRAYER", "prayer"),
        ("ΛΕΙΤΟΥΡΓΊΑ", "λειτουργία"),
        # Greek casefold maps final-sigma ς → σ, per V3 vector note in cache-key.md.
        ("τί\tδιδάσκουν\nοἱ πατέρες;", "τί διδάσκουν οἱ πατέρεσ;"),
        ("a b", "a b"),
    ],
)
def test_normalize_query(raw: str, expected: str) -> None:
    assert normalize_query(raw) == expected


def test_normalize_query_idempotent() -> None:
    q = "What do the FATHERS teach   about prayer?"
    once = normalize_query(q)
    assert normalize_query(once) == once


def test_build_cache_fields_assembles_v1() -> None:
    """Round-trip: build_cache_fields(...) → cache_key(...) must equal V1 SHA-256."""
    from app.domain.models.principal import Principal

    principal = Principal(
        user_id="u_01",
        clerk_user_id="ck_01",
        tenant_id="tn_orthodoxethos",
        clerk_org_id="org_01",
        role="member",
        scopes=["query:read"],
    )
    fields = build_cache_fields(
        principal=principal,
        raw_query="What do the Fathers teach about prayer?",
        answer_mode="consensus",
        session_hash=None,
        corpus_version="2026-05-01.1",
        config_version="2026-05-01.1",
        calendar_version="2026-05-01.1",
        prompt_version="a5_compose@2026-05-01.1",
        model_route_id="a5_compose_anthropic@2026-05-01.1",
        schema_version="2026-05-01.1",
    )
    assert fields == V1_FIELDS
    assert cache_key(fields) == V1_SHA256


def test_build_cache_fields_standalone_vs_followup_differ() -> None:
    """sessionHash null ↔ string flips the JSON shape per contract §Standalone vs Follow-up."""
    from app.domain.models.principal import Principal

    principal = Principal(
        user_id="u_01",
        clerk_user_id="ck_01",
        tenant_id="tn_orthodoxethos",
        clerk_org_id="org_01",
        role="member",
        scopes=["query:read"],
    )
    common = dict(
        principal=principal,
        raw_query="same query",
        answer_mode="consensus",
        corpus_version="2026-05-01.1",
        config_version="2026-05-01.1",
        calendar_version="2026-05-01.1",
        prompt_version="a5_compose@2026-05-01.1",
        model_route_id="a5_compose_anthropic@2026-05-01.1",
        schema_version="2026-05-01.1",
    )
    standalone = build_cache_fields(session_hash=None, **common)
    followup = build_cache_fields(session_hash="sh_abc", **common)
    assert cache_key(standalone) != cache_key(followup)
