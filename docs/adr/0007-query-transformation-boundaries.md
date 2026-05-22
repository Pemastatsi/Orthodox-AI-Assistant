# ADR 0007: Query Transformation Boundaries and Graph-Grounded Expansion

Date: 2026-04-26
Status: Accepted

## Context

The Patristic Library Assistant must preserve the user's intent while answering only from a closed, tenant-approved corpus. Query transformation can improve retrieval, but unrestricted LLM query rewriting creates risks: hidden intent drift, extra latency, harder evaluation, and safety ambiguity.

ADR 0006 defines a phased PAG-RAG architecture where Phase 1 remains vector-first and graph-aware retrieval is deferred until reviewed graph metadata exists. This ADR defines the boundary between safety reframing, retrieval planning, and future graph-grounded expansion.

## Decision

Phase 1 will not implement generic LLM query rewriting. The only query transformation allowed in Phase 1 is transparent A1 safety reframing for sensitive advice-seeking queries.

In Phase 1, `RetrievalPlan.semanticQuery` must default to:

```text
classifiedQuery.reframedQuery ?? classifiedQuery.rawQuery
```

No Phase 1 LLM call may perform generic query rewriting, synonym expansion, or intent reinterpretation. Retrieval quality should first improve through chunking, metadata, BM25 or hybrid retrieval, reranking, and approved graph structure.

### Clarification — chunk-side ingestion enrichment is not query rewriting

This ADR constrains **query-side, answer-time** transformation only. Chunk-side metadata enrichment performed at **ingestion time** — including Contextual Retrieval per-chunk prefixes (ADR-0009 Step 4) and candidate edge extraction (ADR-0006 Phase-1 capture) — is not query rewriting and does not fall under the prohibition above. The distinguishing tests:

- The LLM call runs at ingestion, not at retrieval. The user's question is never an input.
- The output enriches the chunk vector or the graph, not the user-facing `semanticQuery`.
- Two users asking the same question receive identical retrieval inputs (no per-query LLM intermediation).

Future contributors flagging Contextual Retrieval or edge extraction as an ADR-0007 violation should re-read this clarification before opening a follow-up; the report's risk register R-1 (2026-05-22) anticipates this confusion.

Phase 3 may add graph-grounded concept expansion inside A2, coupled to graph-aware retrieval. Expansion must be based only on approved tenant-scoped graph entities, aliases, reviewed mentions, and approved lineage edges. Candidate graph data may be visible to admins, but it must not affect retrieval expansion, answer wording, confidence tier, or user-facing lineage claims.

## Ownership

- A1 owns safety reframing: advice-seeking to teaching-seeking, transparent in the UI, logged as `reframedQuery`.
- A2 owns retrieval planning. It may select templates, filters, boosts, `k`, and later approved graph-grounded concept expansion.
- A2 does not own user intent, sensitivity, handling, final evidence inclusion, or answer composition.
- A4 remains the admission boundary for evidence. Expansion data cannot support confidence or answer claims unless admitted through the approved evidence path.
- A5 may not expose graph-expanded wording as if it were the user's question.

## Interface Contract

Keep the existing `RetrievalPlan.semanticQuery` field.

Reserve this optional Phase 3 field:

```typescript
conceptExpansion?: {
  entityIds: string[]
  aliases: string[]
  edgeIds: string[]
  rationale: string
}
```

`conceptExpansion` is not part of Phase 1 behavior. When introduced, it must be tenant-scoped, auditable, and populated only from approved graph metadata.

The response must continue exposing safety reframing through the existing `reframing` object. Concept expansion is retrieval metadata, not user-facing question text.

## Sensitivity Boundary

Expansion cannot preset or override A1 sensitivity or handling. A2 must not mark a query sensitive because an expansion candidate looks sensitive.

Post-retrieval policy and evidence checks may still apply sensitive handling if approved retrieved evidence makes the response sensitive. Example: a normal query about marriage may retrieve approved divorce-related material through graph expansion in Phase 3; any resulting pastoral handling must come from normal safety and policy checks, not from A2 overriding classification.

## Metrics Requirement

Phase 1 must track retrieval quality so Phase 3 expansion decisions are evidence-based. The minimum tracking set is:

- a small retrieval evaluation set with expected supporting chunks
- recall@k
- MRR
- no-result follow-up rate
- RED or fallback query clusters

Generic LLM query rewriting may be reconsidered only after measured retrieval gaps show that chunking, metadata, BM25 or hybrid retrieval, reranking, and graph-grounded expansion are insufficient.

## Tests

- Normal Phase 1 queries produce no rewritten variant beyond `reframedQuery ?? rawQuery`.
- Sensitive pastoral advice queries use A1 reframing and the mandatory redirect.
- No Phase 1 model route performs generic query rewriting, synonym expansion, or intent reinterpretation.
- Phase 3 concept expansion uses only approved graph entities, aliases, reviewed mentions, and approved lineage edges.
- Candidate graph entities or edges are ignored for retrieval expansion.
- Expanded retrieval cannot alter user-visible intent or bypass sensitive handling.
- If expansion retrieves sensitive-domain evidence, handling is applied through normal post-retrieval policy checks, not by A2 override.

## Consequences

This keeps Phase 1 simpler, faster, and easier to test. It also keeps query safety semantics clear: reframing is a transparent safety behavior, while concept expansion is a future retrieval behavior.

The tradeoff is that Phase 1 may miss some recall opportunities that generic query rewriting could catch. That risk is accepted because the initial corpus is small, and because retrieval metrics will make later recall failures visible.
