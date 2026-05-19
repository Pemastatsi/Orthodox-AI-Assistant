# Rich Output Rendering Contract

Status: Canonical
Date: 2026-05-19
ADR: 0013, 0014

This document defines the frontend rendering contracts for all Phase 2 output types. Companion to `docs/contracts/frontend-components.md` (which defines Phase 1 Q&A components). All Phase 2 components follow the same conventions: TypeScript strict, API access via `api-client.ts`, zod validation of API responses.

## New Routes (Phase 2)

| Route | Layout | Server/Client | Required scope |
|---|---|---|---|
| `/artifacts/[artifactId]` | RootLayout | mixed | `query:read` |
| `/artifacts/[artifactId]/export` | RootLayout | client | `query:read` |
| `/admin/artifacts` | AdminLayout | server | `admin:artifacts:read` |
| `/admin/artifacts/[artifactId]/review` | AdminLayout | mixed | `admin:artifacts:approve` |
| `/admin/model-routes/artifacts` | AdminLayout | mixed | `model_route:read` |
| `/workbench` | WorkbenchLayout | client | `query:read` |
| `/workbench/[sessionId]` | WorkbenchLayout | client | `query:read` |

## New Components (Phase 2)

### `<ArtifactPanel>` (client)

Top-level wrapper for any artifact type. Renders the appropriate type-specific component based on `artifact.artifactType`. Shows status badge, provenance indicator, export button, and approval status for approval-required types.

```ts
interface ArtifactPanelProps {
  artifact: Artifact;
  showProvenance?: boolean;
  onExport?: (format: ExportFormat) => void;
}
```

### `<LineageGraphView>` (client)

Renders the Patristic Lineage Graph using the `GraphRenderer` provider. Interactive: nodes are clickable (opens entity detail drawer); edges show citation pop-over on hover; pan/zoom supported.

```ts
interface LineageGraphViewProps {
  artifact: LineageGraphArtifact;
  initialFocusNodeId?: string;  // highlight a specific node on load
  maxDepth?: number;            // default 4
}
```

Accessibility: all nodes are keyboard-reachable via Tab; Enter opens entity detail; Escape closes drawer. Screen-reader text on each node describes the entity type and name.

### `<CouncilTimelineView>` (client)

Scrollable horizontal timeline of ecumenical and local councils. Each council card is clickable for canon/decision detail. No LLM calls — rendered from structured corpus data.

```ts
interface CouncilTimelineViewProps {
  artifact: CouncilTimelineArtifact;
  highlightEra?: string;
}
```

### `<CitationNetworkView>` (client)

Force-directed graph of father-cites-father relationships. Edge thickness encodes citation frequency. No LLM calls — derived from chunk metadata.

```ts
interface CitationNetworkViewProps {
  artifact: CitationNetworkArtifact;
  minEdgeWeight?: number;
}
```

### `<DisputeMapView>` (client)

Side-by-side comparison of theological positions. Each position card shows tradition label, supporting citations, and contested-status badge. Positions without sufficient evidence display a `INSUFFICIENT_EVIDENCE` badge rather than fabricated content.

```ts
interface DisputeMapViewProps {
  artifact: DisputeMapArtifact;
  positions?: TraditionKey[];  // which traditions to show; defaults to all in artifact
}
```

### `<ManuscriptWitnessTreeView>` (client)

Tree visualization of textual transmission lineage. Nodes represent MSS families, editions, and translations; edges represent derivation relationships.

```ts
interface ManuscriptWitnessTreeViewProps {
  artifact: ManuscriptWitnessTreeArtifact;
}
```

### `<MindMapView>` (client)

Hierarchical outline derived deterministically from the verified response. Expandable/collapsible nodes. No LLM calls.

```ts
interface MindMapViewProps {
  artifact: MindMapArtifact;
  defaultExpanded?: number;  // depth level to expand by default; default 2
}
```

### `<DocumentPreview>` (client)

Embedded preview of a generated document (Study Packet, Sermon Outline, Slide Deck, etc.) before export. Shows pagination for multi-page documents.

```ts
interface DocumentPreviewProps {
  artifact: DocumentArtifact;
  page?: number;
}
```

### `<SlidePreview>` (client)

Slide deck viewer with navigation. Shows speaker notes panel (toggle). Rendered from the `SlideArtifact` data; no iframe sandbox required.

```ts
interface SlidePreviewProps {
  artifact: SlideArtifact;
  showSpeakerNotes?: boolean;
}
```

### `<AudioOverviewPlayer>` (client)

Audio player for TTS overviews. Shows: waveform progress bar, chapter markers at citation timestamps, speaker label (Voice A / Voice B), current-citation highlight synchronized to playback position.

```ts
interface AudioOverviewPlayerProps {
  artifact: AudioArtifact;
  autoPlay?: boolean;
}
```

Accessibility: full keyboard control (Space = play/pause, Left/Right = skip to prev/next chapter marker). Transcript toggle shows the full script with citation markers.

### `<ExportButton>` (client)

Unified export trigger for any artifact. Shows available formats; triggers `POST /artifacts/{artifactId}/export`. Disabled when `artifact.status !== 'approved' && artifact.status !== 'exported'` for approval-required types.

```ts
interface ExportButtonProps {
  artifact: Artifact;
  preferredFormat?: ExportFormat;
}
```

### `<BilingualPanel>` (client)

Side-by-side Greek + English passage view. Hovering or clicking a Greek token opens a morphology popover (parsing, lexical root, gloss). Alignment confidence badge shown per token pair.

```ts
interface BilingualPanelProps {
  artifact: BilingualPassageArtifact;
  showMorphology?: boolean;  // default true
  showAlignmentConfidence?: boolean;
}
```

### `<LiturgicalOverlay>` (client)

Displays today's feast, saint of the day, Gospel/Epistle pericope, and fasting rule as a contextual overlay on any Q&A or artifact view. Uses `liturgical-context.schema.json`.

```ts
interface LiturgicalOverlayProps {
  context: LiturgicalContext;
  compact?: boolean;  // compact = single-line chip; default = expanded card
}
```

### `<IconCard>` (client)

Displays an icon image with theological caption, tradition label, feast reference, and citation back to the corpus. Image is always from the curated licensed set; never AI-generated.

```ts
interface IconCardProps {
  icon: IconographicCard;
  size?: 'small' | 'medium' | 'large';
}
```

### `<MonasteryMap>` (client)

Interactive Leaflet map with overlays for patriarchates, monastic houses, hagiographic sites. Markers are clickable for detail panel. No external API calls at render time — tile server is self-hosted.

```ts
interface MonasteryMapProps {
  artifact: GeographicOverlayArtifact;
  initialZoom?: number;
  centerLat?: number;
  centerLng?: number;
}
```

### `<WorkflowApprovalQueue>` (client)

Admin component. Lists artifacts in `pending_review` state for the current tenant. Each row: artifact type, requesting user, creation timestamp, evidence coverage score, evidence source count, Approve / Reject / Request Changes buttons. Clicking a row opens the full `<DocumentPreview>` or `<LineageGraphView>` for review.

```ts
interface WorkflowApprovalQueueProps {
  items: ArtifactSummary[];
  onApprove: (artifactId: string, comment: string) => Promise<void>;
  onReject: (artifactId: string, comment: string) => Promise<void>;
  onRequestChanges: (artifactId: string, comment: string) => Promise<void>;
}
```

Approver comment: free text, max 1,000 characters, required for rejection, optional for approval.

### `<ProvenanceDrawer>` (client)

Slide-in drawer showing the full provenance report for an artifact: all `citationRefs`, admitted chunks, suppressed chunks, evidence coverage score, verifier run ID. Role-gated: `admin` or `owner` only. Triggered from `<ArtifactPanel showProvenance={true}>`.

```ts
interface ProvenanceDrawerProps {
  artifact: Artifact;
  evidencePacket: EvidencePacket;
  open: boolean;
  onClose: () => void;
}
```

### `<ArtifactStatusBadge>` (server)

Visual badge for artifact lifecycle status. States: Generating, Verifying, Pending Review, Approved, Exported, Failed. Color-coded; status is never the only signal (icon + label both present).

```ts
interface ArtifactStatusBadgeProps {
  status: ArtifactStatus;
  failureReason?: string;
}
```

### `<ArtifactGenerationForm>` (client)

Form for requesting artifact generation from an existing Q&A run. Fields: artifact type selector, output format checkboxes, locale selector, type-specific options. Submits to `POST /artifacts`.

```ts
interface ArtifactGenerationFormProps {
  sourceRunId: string;
  availableArtifactTypes: ArtifactType[];
  onGenerated: (artifact: Artifact) => void;
}
```

Displays the estimated cost before submission. Does not submit if the billing meter cap would be exceeded (client-side pre-check; server enforces authoritatively).

## Rendering Rules

1. **No progressive disclosure of unverified content.** Artifacts with `status !== 'approved'` and `status !== 'exported'` are never rendered to the requesting member. Admins may preview `pending_review` artifacts.
2. **Provenance indicators are always visible** on Tier 2 and Tier 3 artifacts. Members see a summary badge; admins can open `<ProvenanceDrawer>`.
3. **Citation markers are always present** in rendered documents and graphs. They are not optional in any export format.
4. **Audio transcripts are available on demand.** The `<AudioOverviewPlayer>` always has a "Show transcript" toggle; the transcript is the full `AudioScript.turns` with citation markers.
5. **Map tiles are self-hosted.** The `<MonasteryMap>` does not call a third-party tile API at render time.
6. **Icon images are cached browser-side.** `<IconCard>` images include appropriate `Cache-Control` headers; they are served from the platform CDN, not fetched from third-party URLs at runtime.

## Forbidden (Phase 2)

All Phase 1 forbidden items apply. Additionally:

- Rendering artifact content before `provenance.allClaimsVerified=true`.
- Showing unapproved artifacts to `member`-role users.
- Allowing export of approval-required artifacts with `status='pending_review'`.
- Calling image-generation APIs to populate `<IconCard>` images.
- Displaying unverified graph edges (those without `reviewStatus='approved'` per ADR 0006) in `<LineageGraphView>`.
