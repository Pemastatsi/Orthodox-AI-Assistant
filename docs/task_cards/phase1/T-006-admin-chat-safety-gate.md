# T-006: Chat UI, Admin UI, Safety Gate

## Goal

Build the Phase 1 user-facing chat and tenant-aware admin surfaces needed for private beta.

## Required Reads

- [`AGENTS.md`](../../../AGENTS.md) — "Sensitivity And Handling" + "Tenant And Role Rules" sections.
- [`docs/contracts/frontend-components.md`](../../contracts/frontend-components.md) — exact component prop and behavior contracts (`<ChatComposer>`, `<AnswerPanel>`, `<CitationPanel>`, `<ReframingDisclosure>`, `<ConfidenceBadge>`, `<DisclaimerBanner>`, `<StageStatus>`, `<AdminApprovalQueue>`, `<AdminQueryLog>`, `<AdminFlaggedList>`, `<AdminAuditLog>`, `<TenantSwitcher>`); error boundary i18n strategy.
- [`docs/contracts/auth-context.md`](../../contracts/auth-context.md) — role-scope table; raw_sensitive view audit row requirement.
- [`docs/contracts/error-taxonomy.md`](../../contracts/error-taxonomy.md) — codes and `user-visible` flag the frontend uses to choose between specific and generic localized text.
- [`docs/contracts/phase1-implementation-contract.md`](../../contracts/phase1-implementation-contract.md) — "Bounded Fallback Response Shapes" section; `<AnswerPanel>` and `<CitationPanel>` must render the canonical text exactly as specified.
- [`docs/api/openapi.yaml`](../../api/openapi.yaml) — every operation's `x-required-scope`; SSE behavior on `/query` cache-hit.
- [`tests/safety/test_20_queries.py`](../../../tests/safety/test_20_queries.py) — the canonical 20 cases.
- This task card delivers the missing `backend/tests/safety/test_20_queries_harness.py` referenced by `.github/workflows/ci-safety-gate.yml` (`safety-suite-execution` job).

## Files In Scope

- standalone chat page
- citation panel
- reframing disclosure
- admin corpus approval queue
- admin query log and flagged query views
- CI safety test command
- `backend/tests/safety/test_20_queries_harness.py` — runs the 20 canonical cases through the live A1–A6 pipeline (with mocked providers for hard-safety triggers, real providers for the rest); asserts both `expected_handling` and `expected_sensitivity` per case; for cases 6, 10, 12, 17, 20 also asserts the canonical bounded-fallback substring.

## Scholarly Dispute UX (decisive competitive affordance)

When `VerifiedResponse.answerMode === "scholarly_dispute"`, `<AnswerPanel>` MUST render
the competing patristic positions in **side-by-side columns**, not as one collapsed
paragraph. Each column carries:

- A clear position label (e.g. the father, the council, the work, the era) sourced from
  the chunk metadata (`father`, `work`, `sectionPath`); never invented.
- The supporting quote span(s) with `<CitationPanel>` items scoped to that column —
  citations are not aggregated across columns.
- A short composed framing per column drawn only from that column's admitted chunks
  (per the closed-corpus rules in `AGENTS.md`); A5 composition runs per column, not once
  across the whole packet.
- A confidence badge per column (`GREEN | YELLOW | RED`) reflecting that column's
  evidence strength, derived from the same A4 confidence-tier logic applied to that
  column's sub-packet.

The two-column layout collapses to a vertical stack at mobile widths; column attribution
labels remain visible at every breakpoint. The composed columns must NEVER imply
consensus where the evidence shows dispute — this is the single most differentiating
property versus Logos and VulgateAI, both of which collapse competing positions into
one narrative.

The detailed component prop contract for this layout (column count, prop names,
accessibility semantics, empty-column handling) lands in `frontend-components.md`
during T-006 implementation; this task card is the requirement source.

## Acceptance Tests

- Member can ask a question and receive a verified answer or bounded fallback.
- Citations render with source title and page or timestamp when available.
- Reframed sensitive answers disclose reframing.
- Admin can approve or reject chunks.
- Admin query logs respect sensitive redaction rules.
- 20-query safety suite runs in CI.
- A `scholarly_dispute` query renders side-by-side columns with per-column citations,
  composition, and confidence badges; collapses to a labeled vertical stack at mobile
  widths; never aggregates citations across columns.

## Forbidden Scope

- Do not add marketing landing page to MVP unless separately tasked.
- Do not add generated study packet UI.
- Do not add free-form tenant prompt editor.
- Do not expose raw sensitive text to content managers.
