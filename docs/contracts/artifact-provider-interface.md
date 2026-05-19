# Artifact Provider Interface

Status: Canonical
Date: 2026-05-19
ADR: 0014

This document is the authoritative source for the `ArtifactProvider` protocol hierarchy. Companion to `docs/contracts/provider-interface.md` (which defines `LLMProvider` for Q&A). Implemented in `app/adapters/artifact_providers/base.py`. Per ADR 0014, only certified `model_routes` rows with artifact-namespace `purpose` values may serve production traffic.

## Base Protocol: `ArtifactProvider`

```python
from typing import Protocol, runtime_checkable
from app.domain.models.artifacts import (
    ArtifactRequest, Artifact, ProvenanceReport, CostEstimate
)
from app.domain.models.evidence import EvidencePacket

@runtime_checkable
class ArtifactProvider(Protocol):
    name: str              # e.g. 'd3_graph', 'react_pdf', 'openai_tts'
    artifact_purpose: str  # e.g. 'artifact_graph', 'artifact_export_pdf'

    async def generate(
        self,
        *,
        request: ArtifactRequest,
        evidence_packet: EvidencePacket,
        route_id: str,
    ) -> Artifact: ...

    async def verify_citation_provenance(
        self,
        *,
        artifact: Artifact,
        evidence_packet: EvidencePacket,
    ) -> ProvenanceReport: ...

    def supports_format(
        self,
        artifact_type: str,
        output_format: str,
    ) -> bool: ...

    def estimated_cost(
        self,
        request: ArtifactRequest,
    ) -> CostEstimate: ...
```

`verify_citation_provenance` is non-optional. If a provider cannot implement it, it cannot be certified.

`CostEstimate` carries `estimatedCents: int` (rounded up) and `billableMeter: str` (one of `generated_artifact_count` or `audio_minutes_generated`).

## Sub-Protocol: `GraphRenderer`

Purpose namespace: `artifact_graph`

```python
class GraphRenderer(ArtifactProvider, Protocol):
    async def render_graph(
        self,
        *,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
        config: GraphConfig,
        route_id: str,
    ) -> GraphArtifact: ...

    def supports_interactive(self, artifact_type: str) -> bool: ...
```

**Default certified route:** `d3_graph_v1` (D3.js, client-side rendering, free).
**Alternative candidate routes:** `vis_network_v1`, `cytoscape_v1`.

`GraphConfig` carries: `layout` (force-directed | hierarchical | circular), `maxNodes: int`, `interactiveHover: bool`, `citationPopoverEnabled: bool`. The `citationPopoverEnabled` field is always `true` in production; disabling it fails certification (provenance gate).

## Sub-Protocol: `ExportProvider`

Purpose namespaces: `artifact_export_pdf`, `artifact_export_docx`, `artifact_export_pptx`

```python
class ExportProvider(ArtifactProvider, Protocol):
    async def export(
        self,
        *,
        artifact: Artifact,
        output_format: ExportFormat,  # 'pdf' | 'docx' | 'pptx'
        branding: TenantBranding,
        route_id: str,
    ) -> bytes: ...

    def supported_formats(self) -> list[ExportFormat]: ...

    def inject_citations(
        self,
        document: DocumentTree,
        citations: list[Citation],
    ) -> DocumentTree: ...
```

**Default certified routes:**
- PDF: `react_pdf_v1` (react-pdf/renderer, SSR-safe)
- DOCX: `docxjs_v1` (docx.js)
- PPTX: `pptxgenjs_v1` (pptxgenjs) or `marp_v1` (Marp, for HTML slide output)

`inject_citations` is called before `export`. It must embed citations as machine-readable footnotes (not rendered as decorative text). Tested by `tests/artifacts/test_export_citation_injection.py`.

`TenantBranding` carries: `primaryColor`, `logoUrl`, `fontFamily`, `headerTemplate`, `footerTemplate`. All fields are optional; the provider uses platform defaults for any missing field.

## Sub-Protocol: `TTSProvider`

Purpose namespace: `artifact_tts`

```python
class TTSProvider(ArtifactProvider, Protocol):
    async def synthesize(
        self,
        *,
        script: AudioScript,
        voice_config: VoiceConfig,
        route_id: str,
    ) -> AudioArtifact: ...

    def supports_ssml(self) -> bool: ...
    def supports_chapter_markers(self) -> bool: ...

    def pronunciation_coverage(
        self,
        terms: list[str],
    ) -> CoverageReport: ...
```

**Default certified route:** `openai_tts_v1` (OpenAI TTS API, `tts-1-hd` model).
**Alternative candidate routes:** `elevenlabs_v1` (higher quality, higher cost), `azure_tts_v1`.

`AudioScript` carries: `turns: list[TurnScript]` (each turn has `speaker: 'voice_a' | 'voice_b'`, `text: str`, `citationMarkers: list[CitationMarker]`). `VoiceConfig` carries: `languageCode: str`, `speakingRate: float`, `voiceA: str`, `voiceB: str`.

`CoverageReport` carries: `coverageRatio: float` (0–1), `failedTerms: list[str]`. Certification requires `coverageRatio >= 0.80` on `tests/fixtures/tts_pronunciation_terms.json`.

## Sub-Protocol: `SlideRenderer`

Purpose namespace: `artifact_slides`

```python
class SlideRenderer(ArtifactProvider, Protocol):
    async def render_slides(
        self,
        *,
        outline: SlideOutline,
        theme: TenantTheme,
        route_id: str,
    ) -> SlideArtifact: ...

    def supported_output_formats(self) -> list[SlideFormat]: ...
```

**Default certified route:** `marp_v1` (Marp, markdown-to-slides, HTML + PDF output).
**Alternative candidate routes:** `pptxgenjs_v1` (native PPTX), `revealjs_v1` (interactive HTML).

`SlideOutline` carries: `title: str`, `slides: list[SlideSpec]`. Each `SlideSpec` has `heading`, `bodyPoints: list[str]`, `citationRefs: list[str]`, `speakerNotes: str`.

## Sub-Protocol: `MapRenderer`

Purpose namespace: `artifact_map`

```python
class MapRenderer(ArtifactProvider, Protocol):
    async def render_map(
        self,
        *,
        layers: list[MapLayer],
        viewport: MapViewport,
        route_id: str,
    ) -> MapArtifact: ...

    def supports_offline(self) -> bool: ...
```

**Default certified route:** `leaflet_v1` (Leaflet.js, self-hosted tiles, free).
**Alternative candidate routes:** `mapbox_v1` (paid, higher quality), `maptiler_v1`.

## Sub-Protocol: `MorphologyProvider`

Purpose namespace: `artifact_morphology`

```python
class MorphologyProvider(ArtifactProvider, Protocol):
    async def analyze(
        self,
        *,
        token: str,
        language: str,
        route_id: str,
    ) -> MorphologyEntry: ...

    async def align_passages(
        self,
        *,
        greek: str,
        translation: str,
        route_id: str,
    ) -> AlignedPassage: ...

    def supported_languages(self) -> list[str]: ...
```

**Default certified route:** `morphgnt_v1` (MorphGNT offline dataset, free, covers NT Greek).
Septuagint coverage: `lxx_morph_v1` (covers OT Greek).
**Alternative routes:** `perseus_api_v1`, `logeion_api_v1`.

## Sub-Protocol: `IconographyProvider`

Purpose namespace: `artifact_iconography`

```python
class IconographyProvider(ArtifactProvider, Protocol):
    async def lookup(
        self,
        *,
        theological_concept: str,
        context: list[str],
        route_id: str,
    ) -> list[IconCard]: ...

    def supported_traditions(self) -> list[str]: ...
```

**Implementation note:** Initial implementation is a locally hosted curated set. No third-party API. AI-generated images are **permanently prohibited** as a source; this is a hard rule (ADR 0013 Rule 10). Certification fails if the implementation calls an image-generation API.

## Sub-Protocol: `ChantProvider`

Purpose namespace: `artifact_chant`

```python
class ChantProvider(ArtifactProvider, Protocol):
    async def lookup(
        self,
        *,
        text_reference: str,
        tradition: str,
        route_id: str,
    ) -> list[ChantReference]: ...
```

**Implementation note:** Initial implementation is a locally hosted curated audio set. No streaming API in Phase 2.

## Error Handling

All provider methods raise `ArtifactProviderError` subclasses mapped to API error codes per `docs/contracts/error-taxonomy.md`:

| Exception | API code | HTTP |
|---|---|---|
| `ArtifactGenerationError` | `artifact_generation_failed` | 500 |
| `ArtifactProvenanceError` | `provenance_verification_failed` | 422 |
| `ArtifactUnsupportedFormat` | `artifact_format_unsupported` | 400 |
| `ArtifactProviderUnavailable` | `provider_unavailable` | 503 |
| `ArtifactRateLimited` | `rate_limited` | 429 |

No automatic cross-provider fallback in Phase 2 (mirrors ADR 0004 Phase 1 outage policy).

## Configuration

Artifact provider adapters read credentials only via `app/core/config.py`. The adapter constructor validates required env vars at startup. Active routes are loaded from the `ACTIVE_ARTIFACT_ROUTE_*` env vars defined in ADR 0014. Missing vars disable the corresponding feature; startup does not fail on a missing artifact route (unlike LLM routes, which are required for Q&A).

## Forbidden

- Importing rendering library SDKs outside `app/adapters/artifact_providers/`.
- Fetching external URLs at render time; all source data is passed in the `ArtifactRequest` envelope.
- Calling image-generation APIs inside `IconographyProvider` implementations.
- Using a route whose `certification_status != 'certified'` for production traffic.
- Returning an `Artifact` with `provenance.allClaimsVerified=false` without setting `status='failed'`.
