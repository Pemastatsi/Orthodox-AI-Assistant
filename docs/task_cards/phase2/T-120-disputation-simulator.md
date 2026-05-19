# T-120: Disputation Simulator

## Goal

Implement the Disputation Simulator: an evidence-gated interactive exploration of how Orthodox theology responds to common theological objections. The user selects an objection; the system generates an Orthodox response grounded strictly in the evidence packet. Reuses the existing Q&A pipeline (A1–A6) with a specialized `answer_mode='scholarly_dispute'` and a `disputation_response` artifact type. Increments `generated_artifact_count` (LLM-assisted).

## Required Reads

- [`docs/adr/0013-rich-output-format-strategy.md`](../../adr/0013-rich-output-format-strategy.md) — Tier 5 disputation.
- [`docs/schemas/dispute-map.schema.json`](../../schemas/dispute-map.schema.json) — disputation uses the same position-and-claim structure.
- [`docs/contracts/workflow-orchestration-contract.md`](../../contracts/workflow-orchestration-contract.md) — pipeline stages.
- [`docs/adr/0001-closed-corpus-contract.md`](../../adr/0001-closed-corpus-contract.md) — closed-corpus applies to every response.

## Files In Scope

- The disputation simulator reuses the existing Q&A `/query` endpoint with `answerMode='scholarly_dispute'` and a new `disputationContext` field on the query request (the selected objection).
- `backend/app/domain/models/query_request.py` — add `disputationContext: string | null`.
- `web/components/disputation/DisputationInterface.tsx` — objection selector; response panel with citations.
- `web/components/disputation/ObjectionCard.tsx` — preset objection chips (editable by tenant in safe config).

## Acceptance Tests

1. Submitting a disputation query with `disputationContext` produces a `VerifiedResponse` with `answerMode='scholarly_dispute'`.
2. Every claim in the response has a `citationRef`.
3. Response does not include claims from outside the evidence packet.
4. `billing_usage.generatedArtifactCount` increments by 1 (LLM-assisted).
5. A safety-sensitive objection topic triggers `reframe_to_teaching` or `block_with_redirect` handling per ADR 0002.

## Forbidden Scope

- Pre-programmed "scripted" responses not grounded in the evidence packet.
- Objection topics that trigger hard-safety exits generating a response (block_with_redirect exits cleanly).
- Open-web sources for the Orthodox response.
