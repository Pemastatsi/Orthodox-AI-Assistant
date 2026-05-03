# ADR 0002: Confidence, Sensitivity, and Handling

Date: 2026-04-26
Status: Accepted

## Context

The old single `sensitive` concept mixed evidence confidence, risk domain, and response action. That made routing, logging, and tests ambiguous.

## Decision

Use separate fields for evidence confidence, risk domain, harm flags, and response handling.

- `confidenceTier`: `GREEN | YELLOW | RED`
- `sensitivityPrimary`: `normal | pastoral_advice | political | medical | comparative_religion | canonical_dispute | other_sensitive`
- `riskFlags`: `self_harm | medical_emergency | canonical_dispute_active | minor_protection`
- `handling`: `answer | answer_with_disclaimer | reframe_to_teaching | block_with_redirect | insufficient_evidence`

## Rules

1. `confidenceTier` is based on evidence coverage, not topic sensitivity.
2. `sensitivityPrimary` identifies risk domain.
3. `riskFlags` identify urgent or special handling.
4. Self-harm and medical-emergency flags immediately route to `block_with_redirect`.
5. Non-emergency sensitive categories use keyword detection plus A1 confirmation.
6. Sensitive reframing is transparent in the UI.
7. A5 may present teachings but not personal advice, medical diagnosis, or electoral guidance.

## Tests

- A pastoral query with sufficient evidence can be GREEN but still use safe handling.
- A no-evidence normal query is RED without being sensitive.
- Hard safety triggers bypass normal two-stage detection.
- Reframed queries expose `reframedQuery` and UI disclosure metadata.
