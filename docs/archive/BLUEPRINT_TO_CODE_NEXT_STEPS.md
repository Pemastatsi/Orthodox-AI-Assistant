# Archived: Replaced By Contract Pack

This readiness plan has been implemented as `AGENTS.md`, `docs/DOCS_INDEX.md`, `docs/contracts/`, `docs/adr/`, `docs/api/`, `docs/schemas/`, task cards, fixtures, and tests. Do not use this file as active implementation guidance.

# Blueprint to Code Readiness Plan

Date: 2026-04-25
Project: Orthodox AI Assistant / Patristic Library Assistant

## Goal

Before generating application code, convert the blueprint/PRD into a small implementation contract pack. The coding agent should not need to reread large PDFs or infer product behavior from prose.

## Next Step

Create these source-of-truth files before scaffolding code:

| File | Purpose |
|---|---|
| `CLAUDE.md` or `AGENTS.md` | 150-250 line condensed implementation brief: stack, invariants, module boundaries, agent contracts, cache rules, billing rules, safety rules. |
| `docs/adr/0001-closed-corpus-contract.md` | Defines what "no outside knowledge" means operationally and how claims/citations are verified. |
| `docs/adr/0002-confidence-sensitivity-handling.md` | Locks the split between `confidence_tier`, `sensitivity`, and `handling`. |
| `docs/adr/0003-multi-tenant-day-one.md` | Locks tenant isolation, Clerk org mapping, Qdrant filters, cache keys, and admin UX. |
| `docs/adr/0004-model-provider-routing.md` | Locks provider adapters, model routes, certification gates, and experiment rules. |
| `docs/adr/0005-cache-billing-privacy.md` | Locks cache invalidation, served-answer billing, sensitive log retention, and audit policy. |
| `docs/adr/0006-pag-rag-lineage-architecture.md` | Locks Graph-RAG/PAG-RAG as a phased validated-lineage architecture: vector-first MVP, reviewed graph edges before graph-driven answers. |
| `docs/adr/0007-query-transformation-boundaries.md` | Locks Phase 1 query behavior: no generic LLM rewriting, A1-only safety reframing, and Phase 3 graph-grounded concept expansion. |
| `docs/api/openapi.yaml` | Stable API contract before frontend/backend implementation. |
| `docs/schemas/*.json` | JSON schemas for `ClassifiedQuery`, `RetrievalPlan`, `EvidencePacket`, answer modes, citations, and verification. |
| `tests/fixtures/corpus/*.json` | Tiny approved/unapproved corpus fixtures with known scores and citations. |
| `tests/safety/test_20_queries.py` | Executable safety suite with expected confidence/sensitivity/handling/citation behavior. |
| `docs/ui/admin-flow.md` | Tenant-aware admin screens, permissions, and state transitions. |
| `docs/task_cards/phase1/*.md` | One coding task per file: goal, files in scope, acceptance tests, out-of-scope items. |

## Blueprint Gaps Still Worth Resolving

These are the last ambiguity pockets I would close before code generation:

1. Define the exact 20 safety test expected outputs, not only descriptions.
2. Define answer-mode schemas in full, including required fields and max token budgets.
3. Define citation verification thresholds: exact quote, normalized quote, translated quote, summary citation.
4. Define redaction rules for sensitive logs: what patterns are removed and what remains.
5. Define the first private-beta tenant seed data: tenant slug, roles, starter corpus setting, calendar style, thresholds.
6. Define model route names and initial config values exactly.
7. Define admin permission matrix as code-ready rows.
8. Define cache key fields and invalidation triggers as tests.
9. Define the MVP UI route map and component names.
10. Define what must be mocked vs. real in tests: Qdrant/Postgres should be integration-tested; provider calls should use fixtures unless running certification.
11. Define graph edge approval states and reviewer UI behavior for `graph_entities`, `chunk_entity_mentions`, and `lineage_edges`.
12. Define graph-aware retrieval certification tests before any approved edge can affect answer composition or confidence tier.

## Recommended Build Order

1. Generate the implementation contract pack above.
2. Create the repo scaffold and empty modules.
3. Write schemas and tests before implementation.
4. Build database migrations.
5. Build ingestion and vector retrieval.
6. Build graph metadata tables and candidate-edge ingestion, but keep graph-driven answering disabled.
7. Build QueryAnalyzer, deterministic A4, A5 composer, and A6 verifier.
8. Build admin approval and chat UI.
9. Run the 20-query safety suite.
10. Only then wire real provider credentials and private-beta corpus.

## Rule for Later Coding Sessions

Each coding session should read only:
- `CLAUDE.md` / `AGENTS.md`
- The relevant task card
- The directly affected files
- The failing tests

Large planning PDFs and long blueprint docs should be reference material, not repeated context.
