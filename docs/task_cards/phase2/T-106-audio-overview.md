# T-106: Audio Overview

## Goal

Implement Tier 4 two-voice TTS audio overviews: an A5-class composition step generates a two-voice dialogue script from the verified answer + evidence packet; OpenAI TTS synthesizes the audio with SSML-tagged citation markers that become chapter timestamps. Meters `audio_minutes_generated`. Establishes the `TTSProvider` infrastructure and the `audio_overview` artifact type end-to-end.

## Required Reads

- [`docs/contracts/audio-overview-contract.md`](../../contracts/audio-overview-contract.md) — full spec: script generation, SSML rules, pronunciation coverage, voice config, billing.
- [`docs/contracts/artifact-provider-interface.md`](../../contracts/artifact-provider-interface.md) — `TTSProvider` protocol.
- [`docs/schemas/audio-overview.schema.json`](../../schemas/audio-overview.schema.json) — output schema.
- [`docs/adr/0013-rich-output-format-strategy.md`](../../adr/0013-rich-output-format-strategy.md) — Tier 4 definition.
- [`docs/adr/0015-multi-meter-billing.md`](../../adr/0015-multi-meter-billing.md) — `audio_minutes_generated` meter.
- [`docs/contracts/rich-output-rendering.md`](../../contracts/rich-output-rendering.md) — `<AudioOverviewPlayer>` contract.

## Files In Scope

**Backend:**
- `backend/app/adapters/artifact_providers/tts/openai_tts_adapter.py` — implement `TTSProvider`; replaces stub from T-103; handles SSML, chapter markers, signed URL storage.
- `backend/app/domain/services/audio_script_composer.py` — A5-class dialogue script composition; two-voice turn structure; SSML annotation for theological proper nouns.
- `backend/app/domain/services/artifact_service.py` — extend for `audio_overview` type; `audio_minutes_generated` meter increment.
- `backend/app/alembic/versions/0004_billing_audio_meter.py` — add `audioMinutesGenerated` column to `billing_usage`.
- `tests/fixtures/tts_pronunciation_terms.json` — canonical theological proper-noun pronunciation list for certification gate.
- `.env.example` — `ACTIVE_ARTIFACT_ROUTE_TTS`, `OPENAI_TTS_VOICE_A`, `OPENAI_TTS_VOICE_B`.

**Frontend:**
- `web/components/artifacts/AudioOverviewPlayer.tsx` — waveform progress bar, chapter markers, speaker labels, transcript toggle.

## Acceptance Tests

1. `POST /artifacts` with `artifactType='audio_overview'` produces an `AudioOverviewArtifact` with `audioUrl`, `transcriptUrl`, `chapterMarkers`.
2. `durationSeconds > 0`; `billedMinutes = ceil(durationSeconds / 60)`.
3. Every chapter marker corresponds to an admitted `chunkId`.
4. `provenance.allClaimsVerified=true`.
5. `billing_usage.audioMinutesGenerated` increments by `billedMinutes` after synthesis.
6. Cache hit on identical inputs returns existing `audioUrl` without re-synthesizing; `audioMinutesGenerated` does not increment.
7. Audio generation is rejected for a query with `handling='block_with_redirect'`.
8. Audio generation is rejected for a sensitive query on a tenant with `config.audioSensitiveEnabled=false`.
9. `TTSProvider.pronunciation_coverage` on the canonical list in `tests/fixtures/tts_pronunciation_terms.json` returns `coverageRatio >= 0.80` (certification gate).
10. `<AudioOverviewPlayer>` plays audio and chapter markers advance the citation highlight in the transcript.

## Forbidden Scope

- Eleven Labs or Azure TTS routes (stubs only; certifying those alternative routes is a post-Wave-2.0 amendment).
- Synthesizing audio for approval-gated document types without approval first.
- Streaming audio before script provenance verification passes.
- Storing audio files without tenant-scoped access control.
