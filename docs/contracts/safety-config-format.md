# Safety Config Format

Status: Canonical
Date: 2026-05-02

This document defines the YAML schema for `config/sensitivity_keywords.yaml` and `config/pastoral_filters.yaml`. Both files are loaded at startup by `app/domain/services/safety_config.py`. Changes require a safety-suite run before activation (decision register row 8).

## Files

| File | Purpose | Phase used |
|---|---|---|
| `config/sensitivity_keywords.yaml` | A1 keyword detection for `sensitivityPrimary` candidates and `riskFlags`. Hard triggers route to `block_with_redirect`. | Pre-classification |
| `config/pastoral_filters.yaml` | A6 post-composition forbidden-phrase regex. Drives `verifier_failed` when a forbidden pattern appears in the composed answer. | Post-composition |

## Common Top-Level Fields

```yaml
version: "2026-05-01.1"      # YYYY-MM-DD.NN, advanced on every change
schema: "1"                  # bumps when this format changes
regex_flavor: python_re      # only flavor supported in MVP
ordering: first_match_wins   # rules are evaluated top-to-bottom
languages: [en, el]          # the languages this file covers
```

## sensitivity_keywords.yaml — Rule Shape

```yaml
rules:
  - id: <stable_unique_id>            # e.g., "sk_self_harm_en_001"
    pattern: "<python regex string>"  # use raw form; tested case-insensitively
    sensitivity: <enum>               # one of: pastoral_advice | political | medical |
                                      #         comparative_religion | canonical_dispute |
                                      #         other_sensitive
    risk_flags: [<flag>, ...]         # subset of: self_harm | medical_emergency |
                                      #            canonical_dispute_active | minor_protection
    hard_trigger: false               # true → bypass two-stage gate, force block_with_redirect
    lang: en | el                     # rule language scope
    notes: "free text"                # optional reviewer note
```

### Rules

1. `id` must be unique within the file.
2. `pattern` is compiled with `re.IGNORECASE | re.UNICODE`.
3. A rule must set either `sensitivity` (with optional risk flags) or set `hard_trigger: true` with at least one risk flag.
4. The first matching rule wins. Subsequent matches are recorded in the run trace but do not change handling.
5. Hard triggers immediately produce `handling: block_with_redirect`. They bypass A1 LLM confirmation.
6. Non-hard rules are *candidates*. A1 confirms the sensitivity through structured classification before applying handling.

## pastoral_filters.yaml — Rule Shape

```yaml
rules:
  - id: <stable_unique_id>            # e.g., "pf_personal_advice_001"
    pattern: "<python regex string>"
    action: reject_answer | warn      # reject_answer fails A6; warn logs only
    reason_code: <error_taxonomy_code>
    lang: en | el
    notes: "free text"
```

### Rules

1. The composed answer is normalized (NFKC, lowercase) before each `pattern.search`.
2. `reject_answer` causes A6 to set `verification.passed = false` with `failureReason = "pastoral_filter:" + id`.
3. `warn` logs the match in the run trace but does not change handling. Used for tracking phrases that should *probably* be reframed.
4. `reason_code` must match a code in `docs/contracts/error-taxonomy.md`.

## Validation

`safety_config.py` validates each file at startup:

- YAML parses without error.
- All rule fields present and typed correctly.
- All regexes compile.
- All `id`s unique.
- Hard triggers carry at least one risk flag.
- All `reason_code`s exist in the error taxonomy.

A validation failure prevents the service from starting. Tests in `tests/unit/test_safety_config.py` cover the validator.

## Change Procedure

1. Author edits the YAML and bumps `version`.
2. Submit a PR; CI runs the safety suite (`tests/safety/test_20_queries.py`) against the new file.
3. Founder review required for any rule that adds a hard trigger or changes existing hard-trigger scope.
4. After merge, deploy to staging; run live spot-check with a small synthetic query set before promoting to production.

## Stub Content

The shipped stubs contain *format-correct, conservative* rules only. Real Greek/pastoral phrasing requires founder sign-off and is added in follow-up PRs.

## Paraphrase Coverage (CI gate)

Real safety configs (post-stub) MUST be tested against more than the literal phrasings in `tests/safety/test_20_queries.py`. The fuzz harness `tests/safety/test_20_queries_paraphrases.py` is the binding gate.

### Gate requirements

The paraphrase suite is a **CI-blocking gate** under the `safety-suite-execution` job in `.github/workflows/ci-safety-gate.yml`, equal in standing to the canonical 20-case suite. It runs immediately after the canonical suite and fails the build with the same exit semantics.

Activation is gated by the same condition that gates the canonical suite running against real configs (per `phase1-implementation-contract.md` exit criterion #9):

- When `sensitivity_keywords.yaml.version == 2026-05-01.1` (the stub baseline), the paraphrase suite is allowed to `pytest.skip`. The startup self-test in `safety_config.py` continues to fail-closed against stub configs in `APP_ENV='production'`.
- When `sensitivity_keywords.yaml.version != 2026-05-01.1` (real configs merged), the paraphrase suite MUST run and MUST pass; skips are CI failures.

### Coverage requirements (binding for real configs)

For every canonical case (IDs 1–20), `PARAPHRASES[case_id]` must contain:

- A **minimum of 3 paraphrases**, **maximum of 5**, in English.
- For the theologically-substantive cases (IDs 1, 4, 7, 8, 11), **at least 1 additional Greek (`lang: el`) paraphrase**.
- For the hard-trigger case (ID 12, `self_harm` → `block_with_redirect`), every paraphrase must still match a `hard_trigger: true` rule in `sensitivity_keywords.yaml`. Paraphrases that *soften* a hard trigger are a CI failure — the test asserts the hard trigger fired.
- For the block-with-redirect cases (IDs 6, 10, 17), every paraphrase must continue to route to `block_with_redirect`; an answer-handling fallback is a CI failure.

### Test assertions

For every paraphrase under every case, the A1 classifier — running with the real provider route certified for `purpose='query_analyzer'`, not a mocked stub — MUST produce `sensitivityPrimary` and `handling` values equal to `_EXPECTED_BY_CASE_ID[case_id]`. Mismatches are reported per-paraphrase with the case ID, paraphrase text (in test logs only, never written to flagged-query logs from the CI runner), expected outcome, and actual outcome.

### Authoring discipline

Paraphrases are authored by the founder under T-007. They are not LLM-generated at CI time — the same paraphrase set must produce the same result across runs for the suite to function as a regression gate. Adding, removing, or modifying a paraphrase is a config change that requires a safety-suite run before merge (same procedure as the YAML files themselves). The founder may solicit informal Greek-reading review for paraphrases in the `lang: el` slots, but no named reviewer is required by contract.

### Why this discipline catches the failure mode the canonical suite cannot

The canonical 20-case suite catches the obvious thing: the configured pattern matched the literal phrasing the founder wrote. It does not catch the realistic failure mode: a user phrases the same intent slightly differently and slips past the keyword. The paraphrase suite is the only structural defence against that failure mode; without it, the keyword-pattern approach degrades from "deterministic safety" to "deterministic safety only against people who phrase things exactly the way the founder did."

## Phase 2 Launch Gate (per `phase1-implementation-contract.md` exit criterion #9)

The two stub files are gated for Phase 2 readiness. The `version` string `2026-05-01.1` is the stub baseline. Both files MUST carry a different `version` (i.e., real rules merged) before the Phase-1→2 review opens.

A startup self-test in `app/domain/services/safety_config.py` fails with a clear error if `APP_ENV='production'` AND either YAML's top-level `version` still equals `2026-05-01.1`. This prevents accidental production deploys against stubs.

Real-rule sets must:

- Cover every `sensitivityPrimary` enum value with at least one keyword (`normal` excepted — it is the absence of a match).
- Cover every `riskFlags` value with at least one hard-trigger or candidate rule.
- Include Greek (`lang: el`) variants matching the corresponding English rule, per the project's Orthodox-Ethos linguistic scope. The founder is responsible for their linguistic correctness; soliciting informal Greek-reading review before signoff is recommended.
- Pass the full safety suite (20 cases) end-to-end through the live pipeline with no regressions.
- Be approved by the founder (`role='owner'`) via an `audit_entries(action='safety_config_approved')` row referenced in the PR description; see T-007.
