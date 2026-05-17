# Retrieval Evaluation Suite

Status: Canonical
Date: 2026-05-17

This document specifies the per-tenant retrieval evaluation suite that gates ADR-0011 (hybrid retrieval) and ADR-0012 (reranker selection). It is the empirical counterpart to `tests/safety/test_20_queries.py`: where the safety suite tests *handling*, this suite tests *retrieval quality*. The implementation lives under `tests/retrieval_eval/`.

Without this contract, ADR-0011's "sparse adds ~0.20 to Recall@6" and ADR-0012's "rerank lifts faithfulness" remain claims-by-analogy. With this contract, they become claims-with-measurement that a route certification can hinge on.

## Goals

- Provide a per-tenant, version-pinned gold set against which retrieval-quality regressions are measurable in CI.
- Define the metrics A3's certification depends on: Recall@K, Precision@K, MRR, nDCG@K for retrieval; faithfulness, context precision, context recall, answer relevancy for downstream answer quality.
- Make retrieval evaluation a binding gate for `purpose IN ('embedding', 'rerank')` `model_routes` certification — alongside the existing safety suite gate from ADR-0004.
- Run deterministically in CI without external network access (local-reranker path; managed-API rerankers gated by an explicit secret).

Non-goals:

- Replace the safety suite (`tests/safety/test_20_queries.py`). The two suites test orthogonal properties.
- Provide a public benchmark. Patristic gold sets are tenant-owned and not redistributable.

## Gold Set Shape

A gold set is a JSON file per tenant under `tests/retrieval_eval/gold_sets/<tenant_id>/<version>.json`. The version string is a date-prefixed identifier matching the `ModelRoute.routeId` convention: `YYYY-MM-DD.NN`.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "tenantId": "tenant_orthodox_ethos",
  "version": "2026-05-17.1",
  "createdBy": "founder",
  "reviewedBy": ["founder"],
  "corpusVersionAtCuration": "2026-05-15.3",
  "cases": [
    {
      "id": "RE-001",
      "query": "What did Athanasius teach about the divinity of the Holy Spirit?",
      "language": "en",
      "expectedChunkIds": [
        "chunk_athanasius_serapion_001_p012",
        "chunk_athanasius_serapion_001_p013"
      ],
      "minimallySufficientChunkIds": ["chunk_athanasius_serapion_001_p012"],
      "answerMode": "direct_citation",
      "sensitivityPrimary": "normal",
      "notes": "Tests Father-name + concept retrieval against a long work."
    }
  ]
}
```

Required per-case fields:

| Field | Type | Meaning |
|---|---|---|
| `id` | `str` | Stable case ID. `RE-NNN` for retrieval-eval; not reused after a case is deprecated. |
| `query` | `str` | The user-form question, exactly as the chatbot would receive it. |
| `language` | `'en' \| 'el' \| 'grc'` | Modern English, modern Greek, or Polytonic Greek. Determines which embedding/reranker variants this case exercises. |
| `expectedChunkIds` | `list[str]` | The set of approved chunks that, together, fully answer the question. At least one. |
| `minimallySufficientChunkIds` | `list[str]` | The subset that alone is enough to answer. Used for Recall@K when redundancy across `expectedChunkIds` would inflate the metric. |
| `answerMode` | `AnswerMode` | Expected `EvidencePacket.answerMode` (see `answer-mode.schema.json`). |
| `sensitivityPrimary` | `Sensitivity` | Expected `ClassifiedQuery.sensitivityPrimary` (see `flagged-query.schema.json`). Cases that route to `block_with_redirect` carry `expectedChunkIds: []` and are tested by the safety suite, not this one. |
| `notes` | `str` | Curator's rationale for inclusion. Used in regression triage. |

`expectedChunkIds` use the project's stable `chunk_id` values, not URLs. This is a deliberate departure from the Sialtsis 2026 methodology, which uses URLs because the source corpus is a website. Patristic chunks carry stable IDs derived from `sourceHash` + `sectionPath` + position (per `chunk.schema.json`); the gold set is therefore invariant under re-ingestions that preserve content.

## Curation Rules

- A gold set may serve `cases` only for chunks where `chunk.approved == true` at the time of curation. If a chunk's approval is revoked after curation, the case is automatically excluded from that gold-set version's runs (and a `gold_set.case_excluded` event is logged); a new gold-set version with the case removed or replaced is curated.
- Sensitive-tier cases (`sensitivityPrimary IN ('pastoral_advice', 'political', 'medical', 'comparative_religion', 'canonical_dispute', 'other_sensitive')`) are permitted and encouraged — they exercise the rare retrieval paths. Hard-trigger cases (`riskFlags` includes `self_harm` or `medical_emergency`) are forbidden in this suite; they live in the safety suite.
- Cases must be reviewed by the same role that approves chunks (`role IN ('content_manager', 'admin', 'owner')`). The `reviewedBy` field MUST be non-empty.
- A gold set is frozen after its first CI run on a `model_routes` certification path. Subsequent changes ship as a new version.

## Metrics

### Retrieval Metrics (deterministic, no LLM judge)

Computed against `expectedChunkIds` and `minimallySufficientChunkIds`:

| Metric | Definition | Aggregation |
|---|---|---|
| `recall_at_k` | For each case, `1` if any chunk in `minimallySufficientChunkIds` appears in the top-K retrieved chunk IDs, else `0`. Averaged across cases. | Mean across cases. |
| `precision_at_k` | For each case, `\|retrieved_top_k ∩ expectedChunkIds\| / k`. Averaged across cases. | Mean across cases. |
| `mrr` | Mean Reciprocal Rank against the first chunk in `minimallySufficientChunkIds` to appear; `0` if none appears. | Mean across cases. |
| `ndcg_at_k` | Standard nDCG with binary relevance from `expectedChunkIds`. | Mean across cases. |

K values: `6` (the production retrieval ceiling per AGENTS.md §Query Pipeline), `12`, and `20`. K=6 is the primary gate; the others diagnose whether the right candidates exist deeper in the ranking.

### Answer Quality Metrics (Ragas-style LLM judge)

These run a calibrated LLM judge against A5's composed answer and the admitted evidence. Computed only when retrieval succeeded (Recall@6 = 1 for the case); otherwise the case contributes only to retrieval metrics.

| Metric | Definition |
|---|---|
| `faithfulness` | Fraction of factual claims in the answer that are supported by the admitted evidence. |
| `answer_relevancy` | LLM-judged relevance of the answer to the original query. |
| `context_precision` | Of the chunks admitted into the evidence packet, the fraction that are in `expectedChunkIds`. |
| `context_recall` | Of `minimallySufficientChunkIds`, the fraction admitted into the evidence packet. |

The judge route is itself a `ModelRoute` with `purpose='retrieval_eval_judge'` (new purpose, certified separately from any production answer-path route). The judge is intentionally not the same model as A5 — using a different family/provider reduces the risk that A5's biases get re-rewarded by the judge.

### Score-Scale Normalization

All metrics are reported in `[0.0, 1.0]`. The Sialtsis 2026 1–5 human-rated scale is not used; calibrating a 1–5 scale across LLM judges is a known-fragile exercise, and binary/fractional metrics are easier to gate in CI.

## Harness

Implemented under `tests/retrieval_eval/`:

```
tests/retrieval_eval/
├── gold_sets/
│   └── <tenant_id>/
│       └── <version>.json
├── harness.py            # loads a gold set, runs A3 against fixture chunks, emits results
├── metrics.py            # the metric implementations above
├── judge.py              # Ragas-style LLM judge wrapper, calls Reranker-style ModelRoute
├── test_eval_runs.py     # the pytest entry point; emits a `retrieval_eval_runs` row
└── baselines/
    └── <tenant_id>.json  # last passing scores per gold-set version, written on certification
```

The harness is a pytest module. It collects gold-set cases, runs each query through A3 (with the route configuration under test), computes metrics, and writes one `retrieval_eval_runs` row per execution. The DDL for `retrieval_eval_runs` mirrors `safety_suite_runs` (ADR-0004) — it stores the route under test, the gold-set version, per-metric scores, and a pass/fail boolean.

The pass/fail rule is:

- **Pass:** for every metric reported in `baselines/<tenant_id>.json` for the active gold-set version, the new score is ≥ baseline − ε. The default ε is `0.02` (two percentage points). Larger regressions on any metric flip the run to fail.
- **First run for a gold-set version:** no baseline exists. The first run that passes the safety suite simultaneously establishes the baseline for that gold-set version.
- **Improvement:** new scores higher than the baseline are recorded but do not auto-update the baseline. Baseline updates are a deliberate owner-only action (mirrors `ModelRoute` certification authority).

## CI Integration

A new CI job `retrieval-eval-regression` runs against the dense-only retrieval path, the hybrid path (ADR-0011), and the hybrid+rerank path (ADR-0012) for every PR that touches `app/agents/a3_retrieval.py`, `app/adapters/vector_store/`, `app/adapters/reranker/`, `model_routes` seeds, or this file. The job is gating on `main`.

PRs that do not touch retrieval-relevant code skip the job by path filter — this avoids paying judge-LLM cost on every commit. PRs that touch retrieval code but legitimately move metrics (e.g., an embedding-model upgrade) update the baseline as part of the same PR; the baseline update requires explicit `owner` review.

Cost shape:

- Deterministic metrics (Recall@K, Precision@K, MRR, nDCG@K): zero API cost; runs offline.
- Judge metrics (faithfulness, etc.): one judge call per (case, route) where retrieval succeeded. At a ~50-case gold set across three route configurations, this is ~150 judge calls per gating run — a few cents on Anthropic Haiku or equivalent. Bounded enough to gate in CI.

The `retrieval-eval-regression` job is the second of two binding gates for `purpose IN ('embedding', 'rerank')` route certification — the first remains the safety suite from ADR-0004. A route may not be promoted to `certified` without a passing run on both, on the active gold-set version.

## Tenant Scoping and Privacy

- Gold sets are per-tenant. The Orthodox Ethos gold set is not shared with future tenants; each tenant's gold set encodes that tenant's theological priorities and approved corpus.
- A gold-set file is treated as **Confidential** per CLAUDE.md §1. It contains hand-curated theological queries that may reveal that tenant's review priorities or pastoral concerns. Gold sets MUST NOT be committed to public-readable repositories; they live in the same access tier as the corpus itself.
- Judge calls send the user query and admitted-evidence text to the judge model route. This is the same egress profile as A5 composition, and the same closed-corpus-egress review applies. Gold-set cases involving Sensitive content carry their `sensitivityPrimary` so the judge run can apply the same redaction rules as production runs.
- Per-case `notes` are admin-readable only; they MUST NOT appear in any user-facing surface or in error messages logged below admin-only scopes.

## Schema

A JSON schema for the gold-set file lives at `docs/schemas/retrieval-eval-gold-set.schema.json` (to be added alongside the harness implementation). A second schema at `docs/schemas/retrieval-eval-run.schema.json` defines the `retrieval_eval_runs` row shape. Both are referenced by ID from this contract.

## Forbidden Patterns

- Curating gold-set cases against unapproved chunks (`chunk.approved == false`).
- Reusing a gold-set `id` after deprecation.
- Updating a baseline without owner review.
- Including hard-trigger queries (`riskFlags` includes `self_harm` or `medical_emergency`) — those live in the safety suite.
- Running the judge against an unapproved route (`certification_status NOT IN ('certified', 'experiment')`).
- Comparing scores across different gold-set versions. Versions are not commensurable; regression checks compare a route's new score against the baseline for the same version.

## References

- ADR-0004 (Model Provider Routing) — the certification protocol this suite extends with a retrieval-quality gate.
- ADR-0006 (PAG-RAG lineage architecture) §Embedding Model Upgrade — names this suite as the retrieval-quality gate for embedding route certification.
- ADR-0011 (Hybrid Retrieval) — the recall claim this suite measures.
- ADR-0012 (Reranker Selection) — the precision claim this suite measures.
- `tests/safety/test_20_queries.py` — the orthogonal handling-correctness suite; this contract's design mirrors its shape.
- `docs/contracts/approved-decisions-register.md` row D-EVAL-001.
- `docs/schemas/chunk.schema.json` — the stable `chunkId` this suite anchors on.
- Sialtsis, A. (2026). *Building an AI Chatbot using RAG Architecture*. §5.1–5.3 — the methodology this contract adapts. Departures: per-tenant scoping, `chunk_id` granularity (not URL), Ragas-style automated judging (not human raters), [0.0, 1.0] metric range (not 1–5).
