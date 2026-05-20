# T-007: Real Safety Configurations (v1)

## Goal

Replace the stub `config/sensitivity_keywords.yaml` and `config/pastoral_filters.yaml` with founder-approved, Greek-language-reviewed rules that cover every `sensitivityPrimary` category and every `riskFlags` value used in the system. This task is **non-coding work** owned by the founder and a named Greek-language reviewer; no application code changes are part of T-007 itself.

This task is required by Phase 1 → Phase 2 exit criterion #9 (`docs/contracts/phase1-implementation-contract.md`). Falling short blocks Phase 2 scoping.

## Required Reads

- [`AGENTS.md`](../../../AGENTS.md) — "Sensitivity And Handling" + "Closed-Corpus Rules" sections (constrains what the rules may and may not assert).
- [`docs/contracts/safety-config-format.md`](../../contracts/safety-config-format.md) — YAML schema, change procedure, validation rules, paraphrase coverage.
- [`docs/contracts/phase1-implementation-contract.md`](../../contracts/phase1-implementation-contract.md) — Bounded Fallback Response Shapes table + Appendix A canonical texts + exit criterion #9 wording.
- [`config/sensitivity_keywords.yaml`](../../../config/sensitivity_keywords.yaml) — current stub baseline (`version: 2026-05-01.1`).
- [`config/pastoral_filters.yaml`](../../../config/pastoral_filters.yaml) — current stub baseline (`version: 2026-05-01.1`).
- [`tests/safety/test_20_queries.py`](../../../tests/safety/test_20_queries.py) — the canonical 20 cases the rules must satisfy.
- [`tests/safety/test_20_queries_paraphrases.py`](../../../tests/safety/test_20_queries_paraphrases.py) — paraphrase fuzz harness (skeleton; populated as part of this task).

## Owners

- **Founder:** Peter Kyriacos Stavrinides (Founder) — final approver of every rule change. Signs off on cultural and theological appropriateness.
- **Greek-language reviewer:** `<TBD: founder to specify>` — verifies that Greek-language patterns (Koine, Modern, transliterated) are correct, comprehensive, and free of false positives common in Orthodox theological discourse.
- **Engineering reviewer:** the on-call code reviewer ensures YAML structure matches `safety-config-format.md` and that startup validation passes.

## Target Merge Date

`TBD: pin once Phase 1 → 2 evaluation date is set, then back off 6 weeks` — must land before any Phase 2 scoping decision. Recommend setting at least 6 weeks before the planned Phase 1 → 2 evaluation to allow for paraphrase-suite iteration.

## Files In Scope

- `config/sensitivity_keywords.yaml` — replace stub with real rules covering: `pastoral_advice`, `political`, `medical`, `comparative_religion`, `canonical_dispute`, `other_sensitive`. Risk-flag rules: `self_harm`, `medical_emergency`, `canonical_dispute_active`, `minor_protection`. English + Greek (Koine, Modern, transliterated) coverage required. Bump `version` to a non-stub value (e.g., `2026-MM-DD.1`).
- `config/pastoral_filters.yaml` — replace stub with real forbidden-phrase regexes for A6. Same language coverage. Bump `version`.
- `tests/safety/test_20_queries_paraphrases.py` — fill in the per-case paraphrase lists (3–5 per case) so the fuzz suite exercises realistic non-literal phrasings.

## Acceptance Criteria

- Both YAML files load without validation error per `safety-config-format.md`.
- The 20-query suite (`tests/safety/test_20_queries.py` and the live harness `backend/tests/safety/test_20_queries_harness.py`) passes against the new configs in CI.
- The paraphrase fuzz suite (`tests/safety/test_20_queries_paraphrases.py`) passes against the new configs (every paraphrase reaches the same `expected_handling` and `expected_sensitivity` as its canonical case).
- Startup self-test for exit criterion #9 passes: when `APP_ENV='production'`, the application refuses to start if either YAML's `version` is still `2026-05-01.1`.
- The PR description names the founder approver and the Greek-language reviewer (replacing the `<TBD>` placeholders above), and includes a short coverage matrix showing which rules cover each `sensitivityPrimary` × language combination.
- An `audit_entries` row with `action='safety_config_approved'` and `resource_type='safety_config'` is written referencing both YAML hashes after merge (operationally enforced by the deployment pipeline; manual entry acceptable in private beta). This action name is canonical in `docs/schemas/audit-entry.schema.json` and is the row consumed by `scripts/exit_criteria_dashboard.py`.

## Forbidden Scope

- Do not change `safety-config-format.md` itself; the format is a contract.
- Do not soften the startup self-test to "warn instead of fail" — exit criterion #9 demands a hard fail.
- Do not use the real configs in unit tests that should rely on the stub format-only baseline.
- Do not commit the configs without sign-off from both named reviewers.

## Notes for Future Sessions

- This card is the answer to audit finding F-16 (P1). The audit observed that the configs were still at the stub baseline and that no task card scheduled real-config delivery.
- The stub configs match the literal phrasings in `tests/safety/test_20_queries.py` only by coincidence. Real configs must generalize beyond literal phrasings — see `safety-config-format.md §Paraphrase Coverage`.
- Greek-language false positives are the most common failure mode in Orthodox theological discourse (e.g., quotations from the Fathers about "death" should not trigger self-harm rules; theological discussion of "schism" should not trigger canonical-dispute-active). The Greek-language reviewer is the gatekeeper here.
