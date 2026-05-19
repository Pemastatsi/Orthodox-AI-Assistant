# Multimedia Integration Contract

Status: Canonical
Date: 2026-05-19
ADR: 0013

This document defines the sourcing, licensing, caching, and fallback rules for Tier 5 Orthodox-unique multimedia integrations: iconography, Byzantine chant audio, liturgical calendar overlays, and Holy Land / monastery geographical maps.

## General Rules for All Multimedia

1. **No runtime external API calls for content.** All multimedia content is either locally hosted or pre-fetched and stored in platform-controlled storage. No image or audio file is fetched from a third-party URL at render time.
2. **No AI-generated content.** Iconographic images and chant audio recordings must be sourced from real ecclesiastical sources. AI-generated images and synthetic chant recordings are permanently prohibited (ADR 0013 Rule 10).
3. **Licensing.** Every item in the curated sets must have a documented license compatible with the platform's use (display, search, and non-commercial or commercial distribution depending on the tier). License metadata is stored alongside each item.
4. **Tenancy.** Multimedia items from the curated set are tenant-shared (not tenant-scoped). An individual tenant may add to the curated set by submitting items to the platform admin for review; items are not added automatically.
5. **Citation back to corpus.** Every displayed multimedia item must carry a `citationRef` or a conceptual cross-reference to the theological topic it illustrates. Icons show the corpus passage they are associated with. Chant references show the troparion or hymn text from the approved corpus.

## Iconography

### Sourcing

The iconographic set is curated by a platform admin with ecclesiastical knowledge. Acceptable sources:

- High-quality photographs of canonical Orthodox icons from public collections (museum holdings, Wikimedia Commons where CC-licensed or public domain).
- Icons explicitly licensed for digital display by the iconographer or institution.
- Digitized reproductions from published iconographic reference works where rights have been cleared.

Unacceptable sources:
- AI-generated images (permanent prohibition).
- Stock photo libraries without ecclesiastical provenance.
- Icons of disputed canonicity or non-Orthodox origin without annotation.

### `IconographicCard` Fields

| Field | Type | Description |
|---|---|---|
| `iconId` | string (ULID) | Platform-assigned identifier |
| `title` | string | Feast / saint name in English |
| `titleGr` | string \| null | Title in Greek (for Greco-tradition icons) |
| `tradition` | enum | `byzantine`, `russian`, `greek`, `serbian`, `coptic`, `other` |
| `approximateDate` | string \| null | Century or date range (e.g., "14th century") |
| `artist` | string \| null | Iconographer name if known |
| `collection` | string | Holding institution or collection name |
| `licenseType` | string | SPDX license identifier or "public_domain" |
| `imageUrl` | string | Platform CDN URL (not a third-party URL) |
| `thumbnailUrl` | string | Platform CDN URL for thumbnail |
| `theologicalConcepts` | array of strings | Theological topics illustrated |
| `corpusCrossRef` | array of strings | `chunk_id` values from the tenant corpus that this icon illustrates |
| `altText` | string | Accessibility description |

### Lookup

`IconographyProvider.lookup(theological_concept, context)` returns at most 5 `IconCard` entries ranked by relevance to the theological concept and the context list. Items with `corpusCrossRef` matching admitted evidence chunks are ranked first.

### Fallback

If no icon is found for a concept, the component renders a placeholder with the theological concept name and a note: "No canonical icon in the current set for this concept." No fallback to AI-generated images or web search.

## Byzantine Chant

### Sourcing

Acceptable sources:
- Recordings by established Byzantine chanters or choral groups with documented licenses for digital distribution.
- Recordings from Orthodox seminary or monastic archives that have granted platform use rights.
- Audio files explicitly donated to the platform by chanters.

Unacceptable sources:
- AI-synthesized chant (permanent prohibition).
- Recordings of uncertain provenance or copyright status.
- Recordings of non-Orthodox liturgical music presented as Byzantine chant.

### `ChantReference` Fields

| Field | Type | Description |
|---|---|---|
| `chantId` | string (ULID) | Platform-assigned identifier |
| `hymnTitle` | string | English title of the troparion/hymn/kontakion |
| `hymnTitleGr` | string \| null | Greek title |
| `liturgicalCategory` | enum | `troparion`, `kontakion`, `sticheron`, `irmos`, `katavasion`, `psalm`, `other` |
| `tone` | string \| null | Byzantine tone (1–8 or plagal) |
| `mode` | string \| null | Mode name if applicable |
| `tradition` | enum | `byzantine_greek`, `byzantine_arab`, `russian_znamenny`, `serbian`, `other` |
| `chanter` | string \| null | Chanter or ensemble name |
| `licenseType` | string | SPDX license identifier |
| `audioUrl` | string | Platform CDN URL (signed, expires 24 hours) |
| `durationSeconds` | integer | |
| `textReference` | string | The troparion text (Greek + translation) |
| `feast` | string \| null | Associated feast if applicable |

### Lookup

`ChantProvider.lookup(text_reference, tradition)` matches against `hymnTitle`, `textReference`, and associated `feast`. Returns at most 3 matches. If no match, returns empty list; the UI renders a text-only reference with no audio.

## Liturgical Calendar Overlay

### Data Source

The liturgical calendar overlay is computed from a deterministic algorithm applied to the tenant's `calendarProfile` (see `docs/schemas/calendar-profile.schema.json`). It does not require an external API call at runtime; the algorithm is self-contained.

Supported calendar styles (from `calendarProfile.calendarStyle`):
- `julian_old` — Julian calendar (used by Russian, Serbian, Georgian, Jerusalem patriarchates, ROCOR, etc.)
- `revised_julian` — Revised Julian / New Calendar (used by Greek, Romanian, Bulgarian patriarchates, etc.)
- `coptic` — Coptic calendar
- `custom` — Tenant-defined override (date mappings stored in `tenants.config.calendarProfile.customMappings`)

### `LiturgicalContext` Fields (per `liturgical-context.schema.json`)

| Field | Type | Description |
|---|---|---|
| `date` | ISO 8601 date | The date for which context is computed |
| `calendarStyle` | enum | As above |
| `feastName` | string \| null | Major feast name if applicable |
| `feastType` | enum \| null | `great`, `lesser`, `post_feast`, `fore_feast`, `afterfeast`, `fast`, `none` |
| `saintOfTheDay` | array of strings | Saint names for the day |
| `fastingRule` | enum | `no_fast`, `fish_allowed`, `wine_oil_allowed`, `strict_fast`, `xerophagy` |
| `gospelPericope` | `{ reference: string, text: string }` \| null | Day's Gospel reading |
| `epistlePericope` | `{ reference: string, text: string }` \| null | Day's Epistle reading |
| `toneOfWeek` | integer \| null | Byzantine tone (1–8) for the current week's cycle |
| `scriptureRefs` | array of strings | All scriptural references for the day |

### Caching

`LiturgicalContext` is computed once per `(tenantId, date, calendarStyle)` and cached for 24 hours in Redis. Cache key does not include user identity (calendar context is not user-specific).

### Overlay Behavior

When a user submits a Q&A query, the `LiturgicalContext` for the current day is fetched (from cache or computed) and appended to the `<LiturgicalOverlay>` panel. It is not injected into the A5 composition prompt (to avoid influencing the closed-corpus answer), but is displayed alongside it as contextual framing. If a feast day is relevant to the query topic, the UI surfaces a soft suggestion: "Today's feast ({feastName}) is related to your question."

## Holy Land + Monastery Map

### Data Source

Geographical data is a static curated dataset of ecclesiastically significant sites:
- Patriarchate offices and cathedral churches
- Monastic houses (Athos, Meteora, Sinai, Holy Land, major Slavic monasteries)
- Holy Land pilgrimage sites
- Sites referenced in approved corpus documents

The dataset is stored as GeoJSON in platform storage. It is not fetched from a mapping data API at runtime.

### `GeographicOverlayArtifact` Layer Types

| Layer type | Description |
|---|---|
| `patriarchate` | Ecumenical + autocephalous patriarchate and archbishopric seats |
| `monastery` | Major monastic houses; filtered by tradition if `tenants.config.calendarStyle` suggests a preference |
| `holy_land` | Pilgrimage and scriptural sites in the Holy Land |
| `council_location` | Sites of ecumenical and notable local councils |
| `corpus_reference` | Locations explicitly mentioned in the current evidence packet |

The `corpus_reference` layer is populated dynamically from `EvidencePacket` location entities extracted at ingestion time. No LLM extraction at query time.

### Map Tiles

Tiles are served from a self-hosted tile server (MBTiles format, OpenStreetMap data). No calls to Mapbox, Google Maps, or any third-party tile provider at render time. The `leaflet_v1` certified route uses this self-hosted tile endpoint.

A Mapbox-based route (`mapbox_v1`) may be certified as an alternative for Enterprise tenants who require higher cartographic quality; this requires a separate Mapbox API key per tenant (`tenants.config.mapboxApiKey`).

### Fallback

If the self-hosted tile server is unavailable, the map renders without basemap tiles (markers and overlays still visible on a blank canvas). The user sees a non-blocking banner: "Map background unavailable — location markers still shown."

## Forbidden

- Fetching icon images from third-party URLs at render time.
- Fetching chant audio from third-party streaming services at render time.
- Using AI-generated images or synthetic chant in any context.
- Displaying unvetted items from the curated set without a completed license review.
- Injecting `LiturgicalContext` into the A5 composition prompt (it is context only, never evidence).
- Displaying map tiles from third-party providers without a tenant-specific API key.
