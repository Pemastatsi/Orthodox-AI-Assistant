# Audio Overview Contract

Status: Canonical
Date: 2026-05-19
ADR: 0013, 0014, 0015

This document defines the specification for Tier 4 audio overviews: two-voice TTS dialogue summaries of verified answers with embedded citation timestamps. Companion to `docs/contracts/artifact-provider-interface.md` (TTSProvider sub-protocol).

## Overview

An audio overview takes a verified answer + its evidence packet as input and produces an engaging two-voice dialogue in the style of a podcast discussion. Each claim voiced in the dialogue corresponds to a citation in the evidence packet. Citations are announced as chapter markers (e.g., "According to St. John Chrysostom in his Homily on Matthew…") and embedded as audio chapter timestamps.

## Script Generation

Script generation is an A5-class LLM composition step. The prompt instructs the model to:

1. Produce a dialogue between `voice_a` (the questioner / inquirer) and `voice_b` (the theological guide).
2. Every factual claim made by `voice_b` must correspond to a citation in the evidence packet; the claim must be explicitly attributed (e.g., "St. Maximos the Confessor writes in the Ambigua…").
3. `voice_a` may ask clarifying questions and reflect understanding; it may not introduce claims.
4. Total target duration: 5–12 minutes at normal speaking rate (~145 words/minute). Configurable via `generationOptions.targetMinutes` (min: 3, max: 20).
5. A6-equivalent verification runs over the script before TTS synthesis; unverified claims cause the generation to fail.

## `AudioScript` Schema

```json
{
  "title": "string",
  "totalTurns": "integer",
  "estimatedMinutes": "number",
  "turns": [
    {
      "speaker": "voice_a | voice_b",
      "text": "string",
      "ssmlOverrides": "string | null",
      "citationMarkers": [
        {
          "chunkId": "string",
          "positionInText": "integer",
          "spokeCitation": "string"
        }
      ]
    }
  ]
}
```

`spokeCitation` is the human-readable citation announcement embedded in the turn text (e.g., "…as Chrysostom writes in Homily 19 on Matthew…"). It must correspond exactly to the text at `positionInText` in the turn.

## SSML Rules

When the `TTSProvider` route supports SSML (`supports_ssml() == true`):

1. **Theological proper nouns:** wrap with `<phoneme alphabet="ipa" ph="...">` for names where default TTS pronunciation is unreliable. The canonical IPA list is in `tests/fixtures/tts_pronunciation_terms.json`.
2. **Greek-language passages:** wrap with `<lang xml:lang="el">` tags. Synthesis uses the Greek voice model for that span.
3. **Quoted patristic text:** wrap with `<emphasis level="reduced">` to distinguish quoted material from the discussion.
4. **Pauses at citation boundaries:** insert `<break time="300ms"/>` after each citation announcement.
5. **Chapter markers:** insert `<mark name="citation_{chunkId}_{index}"/>` immediately before the spoken citation. These become the chapter timestamps in the output audio file.

## Pronunciation Coverage

Certification requires ≥ 80% acceptable pronunciation on the terms in `tests/fixtures/tts_pronunciation_terms.json`. The list includes:

- All ecumenical council names (Nicaea, Chalcedon, Constantinople I–IV, Ephesus, etc.)
- Common patristic names in their English forms (Chrysostom, Athanasius, Maximos, Palamas, etc.)
- Greek theological terms used without translation (theosis, hypostasis, perichoresis, apophatic, etc.)
- Slavic ecclesiastical names (Seraphim, Paisios, Porphyrios, etc.)

A "term" passes if a trained listener (unfamiliar with the term) would correctly identify the spoken word ≥ 80% of the time when compared to the canonical pronunciation.

## Voice Configuration

| Field | Default | Description |
|---|---|---|
| `voiceA` | Route-dependent | Voice model for the inquirer role |
| `voiceB` | Route-dependent | Voice model for the theological guide role |
| `languageCode` | `en-US` | BCP 47; drives accent and pronunciation model |
| `speakingRate` | `1.0` | 0.5–2.0; 1.0 = normal |
| `includeIntro` | `true` | Spoken introduction: topic title + "Based on approved Orthodox sources…" |
| `includeOutro` | `true` | Spoken outro: "Sources used in this overview: {list of source titles}" |

Voice pairings per certified route are defined in the route's `metadata` JSON field in `model_routes`. Enterprise tenants may configure voice overrides via `tenants.config.artifactRouteOverrides`.

## Output Artifact

`AudioArtifact` fields (extends base `Artifact`):

| Field | Type | Description |
|---|---|---|
| `audioUrl` | string | Signed URL to the stored audio file (mp3, 128 kbps). Expires in 24 hours. |
| `transcriptUrl` | string | Signed URL to the transcript JSON (full `AudioScript`). |
| `durationSeconds` | integer | Actual audio duration. |
| `chapterMarkers` | array | `[{ chunkId, startSeconds, spokeCitation }]` |
| `ttsRouteId` | string | The certified `TTSProvider` route used. |
| `synthesisTimestamp` | ISO 8601 | When TTS synthesis completed. |

## Billing Metering

Audio overviews are billed via the `audio_minutes_generated` Stripe meter (ADR 0015). The meter is incremented by `ceil(durationSeconds / 60)` minutes after synthesis completes. Cached audio (same inputs within TTL) does not increment the meter; the `audioUrl` is served from cache.

Audio cache TTL: 48 hours (longer than artifact cache due to high generation cost). Cache key adds `ttsRouteId` and `voiceConfig` hash to the standard artifact cache key fields.

## Security and Privacy

1. Audio files are stored in tenant-scoped object storage; cross-tenant access is impossible.
2. Signed URLs expire in 24 hours; re-fetching issues a new signed URL.
3. Sensitive query content (queries with `sensitivityPrimary != 'normal'`) may only generate audio overviews if `tenants.config.audioSensitiveEnabled=true` (default `false`). Disabled by default to prevent unintended distribution of sensitive pastoral content.
4. The transcript (`AudioScript`) is subject to the same redaction rules as `run_traces.stages[].notes` (per `docs/contracts/observability.md`): sensitive query raw text is not included in the transcript JSON.

## Forbidden

- Generating audio for queries with `handling='block_with_redirect'`.
- Voicing claims not sourced from the evidence packet.
- Generating audio overviews for queries with `sensitivityPrimary != 'normal'` unless `config.audioSensitiveEnabled=true`.
- Storing audio files without tenant-scoped access control.
- Using a `TTSProvider` route that has not achieved ≥ 80% on the pronunciation coverage test.
