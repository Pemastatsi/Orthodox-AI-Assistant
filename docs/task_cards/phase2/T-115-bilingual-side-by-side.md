# T-115: Bilingual Side-by-Side

## Goal

Implement the Bilingual Passage artifact: Greek + English side-by-side with hover morphology popovers. Uses the `MorphologyProvider` interface with the `morphgnt_v1` (NT) and `lxx_morph_v1` (LXX) offline datasets. Does not increment `generated_artifact_count`. Renders client-side with polytonic Greek font.

## Required Reads

- [`docs/contracts/bilingual-rendering-contract.md`](../../contracts/bilingual-rendering-contract.md) — full spec.
- [`docs/contracts/artifact-provider-interface.md`](../../contracts/artifact-provider-interface.md) — `MorphologyProvider` protocol.
- [`docs/schemas/bilingual-passage.schema.json`](../../schemas/bilingual-passage.schema.json).
- [`docs/contracts/rich-output-rendering.md`](../../contracts/rich-output-rendering.md) — `<BilingualPanel>` contract.

## Files In Scope

- `backend/app/adapters/artifact_providers/morphology/morphgnt_adapter.py` — implement `MorphologyProvider`; replaces stub; loads MorphGNT offline dataset.
- `backend/app/adapters/artifact_providers/morphology/lxx_morph_adapter.py` — CATSS morphology for LXX.
- `backend/app/domain/services/bilingual_assembler.py` — token alignment + morphology lookup; outputs `BilingualPassageArtifact`.
- `web/components/artifacts/BilingualPanel.tsx` — side-by-side columns; morphology popover on Greek token hover/click.
- `web/components/artifacts/MorphologyPopover.tsx` — popover with lemma, parsing, gloss, Strong's/LSJ reference.
- `web/styles/fonts/` — GFS Didot font files (SIL OFL).
- `.env.example` — `ACTIVE_ARTIFACT_ROUTE_MORPHOLOGY`.

## Acceptance Tests

1. `POST /artifacts` with `artifactType='bilingual_passage'` and a Greek-language chunk produces a valid `BilingualPassageArtifact`.
2. Greek text is Unicode NFC normalized polytonic.
3. `alignedTokens` non-empty; at least 50% of tokens have `alignmentConfidence > 0.5`.
4. Morphology popover shows lemma, parsing, and gloss for NT Greek tokens.
5. `coverageNote` is non-null for tokens outside MorphGNT/CATSS coverage; popover shows "not available" message.
6. `billing_usage.generatedArtifactCount` does NOT increment.
7. `alignmentConfidenceScore < 0.6` triggers uncertainty warning banner in `<BilingualPanel>`.

## Forbidden Scope

- Neural alignment model (deterministic + Strong's matching only in Phase 2).
- Perseus API or Logeion API calls at render time.
- Fetching font files from Google Fonts or third-party CDN (self-hosted only).
