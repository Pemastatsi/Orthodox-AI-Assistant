# T-004: Evidence Packaging, Composition, Verification

## Goal

Implement deterministic A4, evidence-only A5 composition, and A6 verification.

## Required Reads

- [`AGENTS.md`](../../../AGENTS.md) — "Closed-Corpus Rules" + "Citation Rules" sections.
- [`docs/adr/0001-closed-corpus-contract.md`](../../adr/0001-closed-corpus-contract.md) — A5 may not use external knowledge; A6 rejects unsupported claims.
- [`docs/adr/0002-confidence-sensitivity-handling.md`](../../adr/0002-confidence-sensitivity-handling.md) — final confidenceTier is computed by A4, not A1.
- [`docs/adr/0006-pag-rag-lineage-architecture.md`](../../adr/0006-pag-rag-lineage-architecture.md) — Phase 1 emits empty `lineageContext`; A6 rejects lineage claims that don't have approved edges.
- [`docs/contracts/quote-overlap-algorithm.md`](../../contracts/quote-overlap-algorithm.md) — exact algorithm + 6 reference test vectors; the 0.70 threshold; forbidden variants.
- [`docs/contracts/safety-config-format.md`](../../contracts/safety-config-format.md) — `pastoral_filters.yaml` rules drive A6's `verifier_failed` and `safety_blocked` reason_codes.
- [`config/pastoral_filters.yaml`](../../../config/pastoral_filters.yaml) — current rules (stub today).
- [`docs/contracts/phase1-implementation-contract.md`](../../contracts/phase1-implementation-contract.md) — "Bounded Fallback Response Shapes" section is the canonical text source for `insufficient_evidence` and `block_with_redirect` answers.
- [`docs/schemas/evidence-packet.schema.json`](../../schemas/evidence-packet.schema.json), [`verified-response.schema.json`](../../schemas/verified-response.schema.json), [`run-trace.schema.json`](../../schemas/run-trace.schema.json) — typed outputs.
- [`docs/contracts/provider-interface.md`](../../contracts/provider-interface.md) — A5 uses `generate_structured`; A6 may optionally use a low-cost certified judge per ADR 0004.

## Files In Scope

- evidence packager
- composer
- verifier
- citation formatter
- answer-mode schemas
- safety tests

## Acceptance Tests

- A4 admits only approved tenant-visible chunks.
- RED evidence path returns deterministic fallback before A5.
- A5 receives only `EvidencePacket` content and prompt rules.
- A6 rejects citations to absent chunks.
- A6 rejects unsupported lineage claims.
- Verified response validates against `verified-response.schema.json`.

## Forbidden Scope

- Do not make A4 an LLM call.
- Do not stream draft answer text before verification.
- Do not allow A5 outside knowledge.
- Do not fabricate citations or lineage.

## Acceptance — Wave 4 Additions

- **F-08:** Verifier judge env slot wiring — `ACTIVE_MODEL_ROUTE_VERIFIER` empty disables the optional A6 judge cleanly; deterministic citation checks still run. Startup test confirms.
- **F-14:** `tests/unit/test_quote_overlap.py` PASSES — quote-overlap V1–V6 vectors match within ±0.01.
- **F-23 E2E:** `tests/integration/test_t004_e2e.py::test_admit_compose_verify_round_trip` PASSES — A4+A5+A6 over a fixed evidence packet, asserting the produced VerifiedResponse passes A6 deterministic checks.
