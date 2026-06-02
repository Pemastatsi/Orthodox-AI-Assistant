# T-007: Real Safety Configurations (v1)

## Goal

Replace the stub `config/sensitivity_keywords.yaml` and `config/pastoral_filters.yaml` with founder-approved rules that cover every `sensitivityPrimary` category and every `riskFlags` value used in the system, including Greek-language coverage (Koine, Modern, transliterated) for the patterns the Orthodox-Ethos corpus actually exercises. This task is **non-coding work** owned by the founder; no application code changes are part of T-007 itself.

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

- **Founder (`role='owner'`):** `peterstavrinides0@gmail.com` — sole approver of every rule change. Signs off on cultural, theological, and linguistic appropriateness, including Greek-language patterns (Koine, Modern, transliterated) and their freedom from false positives common in Orthodox theological discourse. There is no separate named-reviewer gate; the founder may solicit informal Greek-reading review but it is not contractually required.
- **Engineering reviewer:** the on-call code reviewer ensures YAML structure matches `safety-config-format.md` and that startup validation passes.

## Target Merge Date

`<TBD: to be set once T-001 through T-006 are in flight>` — must land before any Phase 2 scoping decision. Founder will set a concrete date once the realistic Phase 1 finish line is visible. Recommend setting it at least 6 weeks before the planned Phase 1 → 2 evaluation to allow for paraphrase-suite iteration.

## Files In Scope

- `config/sensitivity_keywords.yaml` — replace stub with real rules covering: `pastoral_advice`, `political`, `medical`, `comparative_religion`, `canonical_dispute`, `other_sensitive`. Risk-flag rules: `self_harm`, `medical_emergency`, `canonical_dispute_active`, `minor_protection`. English + Greek (Koine, Modern, transliterated) coverage required. Bump `version` to a non-stub value (e.g., `2026-MM-DD.1`).
- `config/pastoral_filters.yaml` — replace stub with real forbidden-phrase regexes for A6. Same language coverage. Bump `version`.
- `tests/safety/test_20_queries_paraphrases.py` — fill in the per-case paraphrase lists (3–5 per case) so the fuzz suite exercises realistic non-literal phrasings.

## Acceptance Criteria

- Both YAML files load without validation error per `safety-config-format.md`.
- The 20-query suite (`tests/safety/test_20_queries.py` and the live harness `backend/tests/safety/test_20_queries_harness.py`) passes against the new configs in CI.
- The paraphrase fuzz suite (`tests/safety/test_20_queries_paraphrases.py`) passes against the new configs (every paraphrase reaches the same `expected_handling` and `expected_sensitivity` as its canonical case).
- Startup self-test for exit criterion #9 passes: when `APP_ENV='production'`, the application refuses to start if either YAML's `version` is still `2026-05-01.1`.
- The PR description includes (a) a short coverage matrix showing which rules cover each `sensitivityPrimary` × language combination, and (b) the `audit_entries.audit_id` of the `safety_config_approved` row inserted by the founder, plus the new `sensitivity_keywords.yaml` and `pastoral_filters.yaml` `version` strings.
- An `audit_entries` row with `action='safety_config_approved'` and `resource_type='safety_config'` is written by the founder (or by the deployment pipeline acting on behalf of `role='owner'`) referencing both YAML hashes after merge. `details` MUST include `sensitivity_keywords_version`, `pastoral_filters_version`, and the SHA-256 hash of each file. This action name is canonical in `docs/schemas/audit-entry.schema.json` and is the row consumed by `scripts/exit_criteria_dashboard.py::criterion_9_real_safety_configs`.

## Forbidden Scope

- Do not change `safety-config-format.md` itself; the format is a contract.
- Do not soften the startup self-test to "warn instead of fail" — exit criterion #9 demands a hard fail.
- Do not use the real configs in unit tests that should rely on the stub format-only baseline.
- Do not commit the configs without founder sign-off (recorded as the `safety_config_approved` audit row).

## Notes for Future Sessions

- This card is the answer to audit finding F-16 (P1). The audit observed that the configs were still at the stub baseline and that no task card scheduled real-config delivery.
- The stub configs match the literal phrasings in `tests/safety/test_20_queries.py` only by coincidence. Real configs must generalize beyond literal phrasings — see `safety-config-format.md §Paraphrase Coverage`.
- Greek-language false positives are the most common failure mode in Orthodox theological discourse (e.g., quotations from the Fathers about "death" should not trigger self-harm rules; theological discussion of "schism" should not trigger canonical-dispute-active). The founder is responsible for catching these; soliciting informal Greek-reading review before signoff is the recommended hedge, but the audit row records founder approval, not a separate reviewer.
