# Bilingual Rendering Contract

Status: Canonical
Date: 2026-05-19
ADR: 0013, 0014

This document defines the specification for the Tier 5 bilingual Greek–English side-by-side rendering feature, including morphological analysis, passage alignment, transliteration, and the `MorphologyProvider` interface. See `docs/schemas/bilingual-passage.schema.json` for the machine-readable schema.

## Purpose

Patristic texts exist primarily in Greek (Koine and Byzantine). Academic and ecclesiastical users who encounter a translated quotation often need to verify the Greek original, check word-level semantics, and understand the morphological forms behind a translation choice. This feature renders a Greek passage alongside its English translation with:

- Word-level alignment (which Greek token corresponds to which English token).
- Hover-activated morphology popover for each Greek token.
- Alignment confidence score per token pair.
- Inline lexical glosses.

## Supported Corpora

| Corpus | Coverage | Provider route |
|---|---|---|
| Greek New Testament | Complete (27 books) | `morphgnt_v1` (MorphGNT, offline) |
| Septuagint (LXX) | Complete (canonical OT + deuterocanonical) | `lxx_morph_v1` (CATSS morphology, offline) |
| Patristic Greek | Partial (corpus-dependent; ingested at chunk level) | `patristic_morph_v1` (stub in Phase 2; expanded in Phase 3) |

For patristic texts not in the morphology dataset, the provider returns `null` for morphology fields and a `coverageNote` explaining the gap. The UI renders the Greek token with a tooltip: "Morphological analysis not available for this text."

## `BilingualPassageArtifact` Schema (`bilingual-passage.schema.json`)

| Field | Type | Description |
|---|---|---|
| `sourceChunkId` | string | The `chunk_id` of the approved source chunk |
| `greekText` | string | Full Greek passage text (Unicode NFC normalized, polytonic) |
| `translationText` | string | Full English translation |
| `translationSource` | string | Name of the translation used (e.g., "NPNF Series 2", "Brenton LXX") |
| `alignedTokens` | array | See token alignment schema below |
| `morphologyDatasetId` | string | Identifier of the morphology dataset used |
| `alignmentConfidenceScore` | number (0–1) | Passage-level alignment confidence |
| `coverageNote` | string \| null | Non-null if morphology is partial |

### Token Alignment Schema

Each `alignedToken` carries:

| Field | Type | Description |
|---|---|---|
| `greekToken` | string | Surface form (with diacritics) |
| `greekTokenNormalized` | string | Normalized form for morphology lookup |
| `greekPosition` | integer | 0-indexed token position in Greek text |
| `englishTokens` | array of strings | Corresponding English token(s) |
| `englishPositions` | array of integers | Positions in English text |
| `alignmentConfidence` | number (0–1) | Per-token alignment confidence |
| `morphology` | `MorphologyEntry \| null` | Null if not in dataset |
| `glosses` | array of strings | Short lexical glosses |

### `MorphologyEntry` Schema

| Field | Type | Description |
|---|---|---|
| `lemma` | string | Greek lemma (dictionary form) |
| `partOfSpeech` | enum | `noun`, `verb`, `adjective`, `adverb`, `preposition`, `conjunction`, `particle`, `pronoun`, `article`, `interjection` |
| `case` | enum \| null | `nominative`, `genitive`, `dative`, `accusative`, `vocative` |
| `number` | enum \| null | `singular`, `plural`, `dual` |
| `gender` | enum \| null | `masculine`, `feminine`, `neuter` |
| `tense` | enum \| null | `present`, `imperfect`, `aorist`, `perfect`, `pluperfect`, `future`, `future_perfect` |
| `mood` | enum \| null | `indicative`, `subjunctive`, `optative`, `imperative`, `infinitive`, `participle` |
| `voice` | enum \| null | `active`, `middle`, `passive`, `middle_passive` |
| `person` | enum \| null | `first`, `second`, `third` |
| `strongsNumber` | string \| null | Strong's concordance number (for NT and LXX tokens) |
| `lsjReference` | string \| null | Liddell-Scott-Jones lexicon entry reference |

## Morphology Popover UI Behavior

Hovering or clicking a Greek token opens a popover showing:

1. **Surface form** in large polytonic Greek font.
2. **Lemma** (nominative singular or infinitive form).
3. **Part of speech** and full parsing in abbreviated form (e.g., "V-AAI-3S" = Verb, Aorist Active Indicative, 3rd Person Singular).
4. **Gloss(es)** — one-line English meanings.
5. **Strong's / LSJ reference** as a hyperlink (if available; links to a self-hosted reference page, not a third-party site).
6. **Corresponding English token(s)** highlighted simultaneously in the translation column.

Accessibility: popovers are keyboard-activatable (Tab to token, Enter/Space to open, Escape to close). Screen-reader text describes each token as: "Greek: {greekToken}, {parsing}, meaning: {gloss}".

## Alignment Algorithm

Passage-level alignment is produced by `MorphologyProvider.align_passages(greek, translation)`. Phase 2 uses a deterministic algorithm combining:

1. **Strongs/lemma matching** for NT and LXX texts (where Strong's numbers are available).
2. **Word-order heuristic** for texts without Strong's coverage.
3. **Confidence scoring**: `1.0` for exact lemma match, `0.6–0.9` for word-order matches, `0.3–0.5` for low-confidence heuristic alignment.

Full neural alignment (using a trained bilingual alignment model) is deferred to Phase 3 and requires a new ADR before adoption.

## Generation Request

A `bilingual_passage` artifact request must include:

| Field | Required | Description |
|---|---|---|
| `sourceChunkId` | yes | Must be an approved chunk in the tenant corpus containing a Greek-language passage |
| `translationPreference` | no | Preferred translation name; falls back to the translation stored in the chunk metadata |
| `showMorphology` | no | Default `true`; if `false`, alignment only (no morphology lookup) |

The billing meter does not increment for `bilingual_passage` artifacts (morphology lookups are cheap and served from a local offline dataset). There is no LLM call unless the patristic morphology stub is activated.

## Limitations and Disclosures

The UI must display a disclosure for `bilingual_passage` artifacts with:

- `morphologyDatasetId`: which dataset was used.
- `alignmentConfidenceScore`: passage-level confidence score.
- `coverageNote` (if non-null): text explaining partial coverage.

For passages with `alignmentConfidenceScore < 0.6`, the UI additionally shows: "Word alignment is approximate for this text. Treat highlighted correspondences as suggestions, not translations."

## Polytonic Greek Rendering

Greek tokens must be rendered using a Unicode polytonic Greek font. The platform bundles `GFS Didot` (SIL Open Font License) as the primary polytonic Greek font. Fallback chain: `GFS Didot`, `Gentium`, `Palatino Linotype`, serif.

All Greek text is stored and transmitted as Unicode NFC-normalized polytonic Unicode (not betacode or precomposed characters). The `greekText` field in `BilingualPassageArtifact` is validated against the Unicode polytonic Greek range on storage.

## Forbidden

- Fetching morphology data from third-party APIs at render time (all morphology data is served from the local offline dataset).
- Rendering Greek tokens with betacode or non-Unicode encoding.
- Displaying alignment for texts where `alignmentConfidenceScore < 0.3` without a prominent uncertainty warning.
- Linking to third-party lexicon sites from morphology popovers (LSJ and Strong's references must point to self-hosted pages).
- Using a neural alignment model without an ADR approving its adoption and a certification gate for alignment quality.
