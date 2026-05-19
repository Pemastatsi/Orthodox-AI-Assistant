# ADR 0014: Artifact Provider Abstraction

Date: 2026-05-19
Status: Accepted

## Context

ADR 0004 established provider abstraction and certification gates for LLM routes. The same motivations apply to rich-output rendering: different artifact types are best served by different specialized libraries and third-party services, those services evolve rapidly, and no single vendor is optimal across graph rendering, PDF generation, TTS, maps, and morphology. Hard-coding library calls in business logic creates vendor lock-in and makes it impossible to A/B-test providers or upgrade individual components without risking regressions across the system.

Additionally, every artifact renderer must enforce closed-corpus provenance (ADR 0013 Rule 2–3). If rendering is abstracted behind a common interface, provenance enforcement can be centralized in the base class rather than duplicated per library.

## Decision

Extend the ADR 0004 certification model to all artifact-rendering capabilities by defining an `ArtifactProvider` base protocol and a set of typed sub-interfaces, one per artifact category. Certified routes follow the same `model_routes`-equivalent registry, and providers cannot serve user traffic until certified by a user with `role='owner'`.

## Interface Hierarchy

**Authoritative source:** `docs/contracts/artifact-provider-interface.md`. The interfaces summarized below capture ADR scope; additions and current method signatures live in the contract file. Conflicts are resolved in favor of the contract.

### Base: `ArtifactProvider`

All providers expose:

- `generate(request: ArtifactRequest) -> Artifact`
- `verify_citation_provenance(artifact: Artifact, evidence_packet: EvidencePacket) -> ProvenanceReport`
- `supports_format(artifact_type: str, output_format: str) -> bool`
- `estimated_cost(request: ArtifactRequest) -> CostEstimate`

The `verify_citation_provenance` method is non-optional. A provider that cannot verify provenance cannot be certified.

### `GraphRenderer`

Renders interactive graph artifacts (lineage graph, citation network, dispute map, manuscript witness tree). Default certified route: D3.js (client-side, free). Alternative candidate routes: vis-network, Cytoscape.js.

Additional methods:
- `render_graph(nodes: list[GraphNode], edges: list[GraphEdge], config: GraphConfig) -> GraphArtifact`
- `supports_interactive(artifact_type: str) -> bool`

### `ExportProvider`

Generates downloadable document files (PDF, DOCX, PPTX). Default certified routes: `react-pdf` (PDF), `docx.js` (DOCX), `pptxgenjs` (PPTX). Alternative routes for PDF: `pdf-lib`; for PPTX: Marp (HTML slides).

Additional methods:
- `export(artifact: Artifact, format: ExportFormat, branding: TenantBranding) -> bytes`
- `supported_formats() -> list[ExportFormat]`
- `inject_citations(document: DocumentTree, citations: list[Citation]) -> DocumentTree`

The `inject_citations` method ensures citation footnotes or endnotes appear in every exported document regardless of format.

### `TTSProvider`

Synthesizes audio overviews. Default certified route: OpenAI TTS. Alternative candidate routes: Eleven Labs (higher quality, higher cost), Azure Cognitive Services. Each route has a separate certification due to differing voice models and pronunciation quality for Greek/Slavic theological terms.

Additional methods:
- `synthesize(script: AudioScript, voice_config: VoiceConfig) -> AudioArtifact`
- `supports_ssml() -> bool`
- `supports_chapter_markers() -> bool`
- `pronunciation_coverage(terms: list[str]) -> CoverageReport`

`pronunciation_coverage` is evaluated during certification: the route must achieve ≥ 80% acceptable pronunciation on the canonical theological proper-noun list in `tests/fixtures/tts_pronunciation_terms.json`.

### `SlideRenderer`

Generates presentation slide decks. Default certified route: Marp (markdown-to-slides, free). Alternative routes: pptxgenjs (native PPTX), Reveal.js (interactive HTML).

Additional methods:
- `render_slides(outline: SlideOutline, theme: TenantTheme) -> SlideArtifact`
- `supported_output_formats() -> list[SlideFormat]`

### `MapRenderer`

Renders geographical overlays. Default certified route: Leaflet.js (free, self-hosted tiles). Alternative routes: Mapbox (paid, higher quality), MapTiler.

Additional methods:
- `render_map(layers: list[MapLayer], viewport: MapViewport) -> MapArtifact`
- `supports_offline() -> bool`

### `MorphologyProvider`

Provides Greek morphological analysis for bilingual side-by-side rendering. Default certified route: SBLGNT/MorphGNT open dataset (offline, free). Alternative routes: Perseus Digital Library API, Logeion.

Additional methods:
- `analyze(token: str, language: str) -> MorphologyEntry`
- `align_passages(greek: str, translation: str) -> AlignedPassage`
- `supported_languages() -> list[str]`

### `IconographyProvider`

Looks up iconographic references from a curated licensed set. No default third-party route; the initial implementation is a locally hosted curated set. AI-generated images are permanently prohibited as a source.

Additional methods:
- `lookup(theological_concept: str, context: list[str]) -> list[IconCard]`
- `supported_traditions() -> list[str]`

### `ChantProvider`

Links to traditional Byzantine chant recordings for referenced troparia and hymns. Implementation is a locally hosted curated set; no external streaming API in Phase 2.

Additional methods:
- `lookup(text_reference: str, tradition: str) -> list[ChantReference]`

## Route Registry

Artifact provider routes are stored in the existing `model_routes` table using a new `purpose` namespace: `artifact_graph`, `artifact_export_pdf`, `artifact_export_docx`, `artifact_export_pptx`, `artifact_tts`, `artifact_slides`, `artifact_map`, `artifact_morphology`, `artifact_iconography`, `artifact_chant`.

Active routes are loaded from env vars at startup:

```
ACTIVE_ARTIFACT_ROUTE_GRAPH
ACTIVE_ARTIFACT_ROUTE_EXPORT_PDF
ACTIVE_ARTIFACT_ROUTE_EXPORT_DOCX
ACTIVE_ARTIFACT_ROUTE_EXPORT_PPTX
ACTIVE_ARTIFACT_ROUTE_TTS
ACTIVE_ARTIFACT_ROUTE_SLIDES
ACTIVE_ARTIFACT_ROUTE_MAP
ACTIVE_ARTIFACT_ROUTE_MORPHOLOGY
ACTIVE_ARTIFACT_ROUTE_ICONOGRAPHY
ACTIVE_ARTIFACT_ROUTE_CHANT
```

All follow the ADR 0004 certification lifecycle: `draft` → `experiment` → `certified` → `deprecated`. Only `certified` routes may serve user traffic. Missing vars disable the corresponding feature cleanly (artifact type unavailable, no startup failure).

## Certification Protocol

Identical to ADR 0004 with two additional gates:

1. **Provenance gate.** The provider's `verify_citation_provenance` must return `all_claims_verified=true` on a set of 10 canonical test artifacts in `tests/fixtures/artifact_provenance_cases.json`. No tolerance for unverified claims.
2. **Format fidelity gate.** For `ExportProvider` routes: citation footnotes must appear in all three export formats (PDF, DOCX, PPTX) and be machine-readable (not rendered as decorative text). Verified by `tests/artifacts/test_export_citation_injection.py`.

## Tenant-Customizable Routes

Enterprise-tier tenants may configure an alternative certified route for `artifact_tts` and `artifact_slides` via `tenants.config.artifactRouteOverrides`. Overrides must still point to a `certified` row in `model_routes`; uncertified overrides are rejected at query time.

## Provider Outage Policy

Artifact generation is non-blocking for the Q&A pipeline. A provider failure returns an artifact with `status='generation_failed'` and a user-visible message. No automatic cross-provider fallback in Phase 2 (mirrors ADR 0004 Phase 1 outage policy). Cross-provider failover for artifacts is deferred to Phase 3.

## Rules

1. All artifact rendering MUST go through a certified `ArtifactProvider` sub-interface; direct library calls in business logic are forbidden.
2. `verify_citation_provenance` MUST be called before any artifact transitions to `status='ready'`.
3. Providers MUST NOT fetch data from external URLs at render time; all source data is passed in the `ArtifactRequest` envelope.
4. `IconographyProvider` MUST NOT use AI image generation; source images MUST be from the locally hosted licensed set.
5. Provider swap (changing the active certified route) requires owner authorization and an audit entry; the change is effective on next service restart.
6. Startup rejects any active artifact route env var that resolves to a non-certified row, identical to ADR 0004 startup enforcement.
7. Experiments may be activated for a single tenant with `role='owner'` consent and a `model_routes.certification_status='experiment'` row; experimental artifacts are watermarked and never exported.

## Tests

- Provider interface conformance: every adapter implements all required methods; missing method raises `NotImplementedError` before certification.
- Provenance gate: canonical test artifacts in `tests/fixtures/artifact_provenance_cases.json` pass `verify_citation_provenance` on the default route.
- Startup enforcement: setting an active artifact route var to a `draft` row causes service startup to fail with a clear error.
- Provider swap: swap the default `GraphRenderer` to a stub; assert artifact output format matches the stub's declared format.
- Tenant override: apply an `artifactRouteOverrides` with an uncertified TTS route; assert the override is rejected at query time.
- Outage: mock a provider returning 500; assert artifact `status='generation_failed'` and Q&A pipeline is unaffected.
- Format fidelity: run `test_export_citation_injection.py` against the default `ExportProvider` route; assert footnotes present in PDF, DOCX, and PPTX output.
