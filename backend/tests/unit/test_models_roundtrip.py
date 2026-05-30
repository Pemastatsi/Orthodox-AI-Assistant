"""Acceptance criterion #7: every pydantic model round-trips a fixture instance.

This test guards against drift between `docs/schemas/*.json` and `app/domain/models/`."""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.models import (
    AdmittedChunk,
    ApiError,
    Chunk,
    Citation,
    ClassifiedQuery,
    EvidencePacket,
    Principal,
    Reframing,
    RetrievalEvalRegression,
    RetrievalEvalRun,
    RetrievalFilters,
    RetrievalPlan,
    Source,
    Tenant,
    Verification,
    VerifiedResponse,
    VerifiedResponseUsage,
)

NOW = datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC)
SHA = "sha256:" + "a" * 64


def _roundtrip(model_instance) -> None:
    serialized = model_instance.model_dump(by_alias=True, mode="json")
    revived = model_instance.__class__.model_validate(serialized)
    assert revived.model_dump(by_alias=True, mode="json") == serialized


def test_principal_roundtrips() -> None:
    p = Principal(
        user_id="u_1",
        clerk_user_id="cu_1",
        tenant_id="t_1",
        clerk_org_id="org_1",
        role="member",
        scopes=["query:read", "corpus:read"],
    )
    _roundtrip(p)


def test_chunk_roundtrips() -> None:
    c = Chunk(
        chunk_id="ch_1",
        source_id="s_1",
        tenant_id="t_1",
        text="Body text.",
        chunk_hash=SHA,
        approved=True,
        visibility="member",
        context_prefix="From Athanasius, Letters to Serapion, on the divinity of the Holy Spirit.",
        embedding_model="text-embedding-3-small",
        embedding_dimension=1536,
        corpus_version="fixture-2026-05-01",
        created_at=NOW,
    )
    _roundtrip(c)
    # contextPrefix (chunk.schema.json field) must survive the camelCase wire round-trip.
    assert c.model_dump(by_alias=True, mode="json")["contextPrefix"] == c.context_prefix


def test_retrieval_eval_run_roundtrips() -> None:
    r = RetrievalEvalRun(
        retrieval_eval_run_id="reval_01",
        route_id="embedding_openai_large@2026-05-29.1",
        purpose="embedding",
        config_label="dense_only",
        gold_set_tenant_id="tenant_smoke",
        gold_set_version="2026-05-29.1",
        case_count=6,
        scores={"recall_at_6": 1.0, "mrr": 1.0},
        passed=False,
        is_first_run=False,
        judge_applied=False,
        regressions=[
            RetrievalEvalRegression(metric="recall_at_6", baseline=0.8, observed=0.75)
        ],
        initiated_by="usr_owner",
        started_at=NOW,
        finished_at=NOW,
        created_at=NOW,
    )
    _roundtrip(r)
    dumped = r.model_dump(by_alias=True, mode="json")
    assert dumped["retrievalEvalRunId"] == "reval_01"
    assert dumped["goldSetVersion"] == "2026-05-29.1"
    assert dumped["judgeApplied"] is False


def test_source_roundtrips() -> None:
    s = Source(
        source_id="s_1",
        tenant_id="t_1",
        title="On the Holy Spirit",
        source_type="pdf",
        source_hash=SHA,
        extraction_method="pdfplumber",
        corpus_version="fixture-2026-05-01",
        created_at=NOW,
    )
    _roundtrip(s)


def test_tenant_roundtrips() -> None:
    t = Tenant(
        tenant_id="t_1",
        name="OrthodoxEthos",
        clerk_org_id="org_1",
        status="active",
        data_region="us",
        created_at=NOW,
    )
    _roundtrip(t)


def test_api_error_roundtrips() -> None:
    e = ApiError(
        code="validation_failed",
        message="Bad input",
        trace_id="01HZX7ABC",
        details={"fieldErrors": [{"path": "answer", "msg": "required"}]},
    )
    _roundtrip(e)


def test_classified_query_roundtrips() -> None:
    q = ClassifiedQuery(
        raw_query="What is the Trinity?",
        answer_mode="consensus",
        sensitivity_primary="normal",
        risk_flags=[],
        handling="answer",
        preliminary_confidence_tier="GREEN",
    )
    _roundtrip(q)


def test_retrieval_plan_roundtrips() -> None:
    plan = RetrievalPlan(
        semantic_query="trinity orthodox doctrine",
        answer_mode="consensus",
        tenant_id="t_1",
        filters=RetrievalFilters(tenant_id="t_1"),
    )
    _roundtrip(plan)


def test_verified_response_roundtrips() -> None:
    r = VerifiedResponse(
        answer="The Holy Trinity is...",
        confidence_tier="GREEN",
        handling="answer",
        citations=[
            Citation(
                citation_id="c1",
                chunk_id="ch_1",
                source_id="s_1",
                title="On the Holy Spirit",
                source_hash=SHA,
                chunk_hash=SHA,
                corpus_origin="tenant",
            )
        ],
        verification=Verification(passed=True, checked_at=NOW, verifier_version="a6@2026-05-01.1"),
        reframing=Reframing(was_reframed=False),
        usage=VerifiedResponseUsage(
            served_answer_count=1,
            fresh_model_run_count=1,
            model_route_id="a5_compose_anthropic@2026-05-01.1",
        ),
        served_from_cache=False,
        schema_version="2026-05-01.1",
        run_id="01HZX7ABC",
    )
    _roundtrip(r)


def test_bounded_fallback_response_roundtrips() -> None:
    r = VerifiedResponse(
        answer="The approved library does not contain material on this topic. ...",
        confidence_tier="RED",
        handling="insufficient_evidence",
        citations=[],
        verification=Verification(
            passed=False,
            checked_at=NOW,
            verifier_version="a6@2026-05-01.1",
            failure_reason="quote_overlap_below_threshold:1",
        ),
        reframing=Reframing(was_reframed=False),
        usage=VerifiedResponseUsage(
            served_answer_count=1,
            fresh_model_run_count=0,
            model_route_id="a5_compose_anthropic@2026-05-01.1",
        ),
        served_from_cache=False,
        schema_version="2026-05-01.1",
        run_id="run_bounded",
    )
    _roundtrip(r)


def test_evidence_packet_roundtrips() -> None:
    packet = EvidencePacket(
        tenant_id="tn_test",
        corpus_version="2026-05-01",
        confidence_tier="YELLOW",
        admitted_chunks=[
            AdmittedChunk(
                chunk_id="ch_1",
                source_id="s_1",
                title="On Prayer",
                text="Saint Basil writes about prayer.",
                score=0.85,
                visibility="member",
                source_hash=SHA,
                chunk_hash=SHA,
            )
        ],
        suppressed_chunk_ids=["ch_2", "ch_3"],
        lineage_context=[],
    )
    _roundtrip(packet)
