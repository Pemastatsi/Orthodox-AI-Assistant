"""Per-tenant retrieval-evaluation suite (`docs/contracts/retrieval-eval-suite.md`).

This package is the empirical counterpart to `tests/safety/` — where the safety suite tests
*handling*, this suite tests *retrieval quality*. It gates `purpose IN ('embedding', 'rerank')`
`model_routes` certification (ADR-0004 §certification) alongside the safety suite.

Layout (adapted from the contract's aspirational top-level `tests/retrieval_eval/` to the repo's
real package root `backend/tests/`, which is the importable `tests` package — see the suite's
README for the rationale; the same adaptation already applies to the safety *execution* harness at
`backend/tests/safety/test_20_queries_harness.py`):

    metrics.py        # deterministic Recall@K / Precision@K / MRR / nDCG@K — offline, no API cost
    harness.py        # loads a gold set, runs A3 (Retriever) per case, collects retrieved IDs
    judge.py          # Ragas-style LLM-judge metrics via the retrieval_eval_judge route (gated)
    test_metrics.py   # rigorous known-answer unit tests for metrics.py
    test_eval_runs.py # end-to-end smoke: gold set -> A3 -> metrics -> RetrievalEvalRun
    gold_sets/<tenant_id>/<version>.json
    baselines/<tenant_id>.json
"""
