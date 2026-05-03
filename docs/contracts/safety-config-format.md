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

## Phase 2 Launch Gate (per `phase1-implementation-contract.md` exit criterion #9)

The two stub files are gated for Phase 2 readiness. The `version` string `2026-05-01.1` is the stub baseline. Both files MUST carry a different `version` (i.e., real rules merged) before the Phase-1→2 review opens.

A startup self-test in `app/domain/services/safety_config.py` fails with a clear error if `APP_ENV='production'` AND either YAML's top-level `version` still equals `2026-05-01.1`. This prevents accidental production deploys against stubs.

Real-rule sets must:

- Cover every `sensitivityPrimary` enum value with at least one keyword (`normal` excepted — it is the absence of a match).
- Cover every `riskFlags` value with at least one hard-trigger or candidate rule.
- Include reviewed Greek (`lang: el`) variants matching the corresponding English rule, per the project's Orthodox-Ethos linguistic scope.
- Pass the full safety suite (20 cases) end-to-end through the live pipeline with no regressions.
- Be reviewed by a Greek-language-competent reviewer named in the PR description; the founder owns final sign-off.
