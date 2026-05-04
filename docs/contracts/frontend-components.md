# Frontend Component Contracts

Status: Canonical
Date: 2026-05-02

This document defines the prop, state, and behavior contracts for the Phase 1 React components in `web/`. The implementation lives under `web/components/`. Visual design (colors, spacing, typography) is intentionally out of scope here — that lives in the Tailwind config and the design tokens added during scaffold.

## Conventions

- All components are **TypeScript strict**. No `any`. No prop spreads on wrapper elements.
- Props are passed by name; no `children` polymorphism unless explicitly listed below.
- Data fetching: **React Server Components by default**. Client components only when the component needs state or browser APIs (chat composer, approval queue actions).
- API access: every fetch goes through `web/lib/api-client.ts`, which is generated from `docs/api/openapi.yaml`. Components do not call `fetch` directly.
- Schema validation: every API response is validated client-side with the zod schema in `web/lib/schemas/` (generated from `docs/schemas/`). Validation failures render the error boundary.
- Accessibility: every interactive element is keyboard-reachable; semantic landmarks (`<main>`, `<nav>`, `<aside>`) are used; color is never the only signal for handling/confidence.

## Routes

| Route | Layout | Server/Client | Required scope |
|---|---|---|---|
| `/` | RootLayout | mixed (composer is client) | `query:read` |
| `/runs/[runId]` | RootLayout | server | `query:read` |
| `/admin/corpus` | AdminLayout | mixed | `corpus:read` (write actions require `corpus:write`/`corpus:approve`) |
| `/admin/queries` | AdminLayout | server | `admin:queries:read` |
| `/admin/flagged` | AdminLayout | server | `admin:flagged:read` |
| `/admin/audit` | AdminLayout | server | `admin:audit:read` |
| `/admin/settings` | AdminLayout | mixed | `tenant:config:read` (write requires `tenant:config:write`) |

A user without the required scope is redirected to `/` with a non-blocking toast.

**`/runs/[runId]` per-user filtering:** Members see only their own runs; admins, owners, and content managers see all runs in the tenant via the same route. The `<AdminQueryLog>` deep-link path (`/admin/queries → /runs/[runId]`) relies on the admin scope; member fetch attempts on other-user runIds receive a 404 (not 403) per the access rule in `auth-context.md §/runs/{runId} access rule`.

## Components

### `<ChatComposer>` (client)

Submits a question and receives a `VerifiedResponse`.

```ts
type AnswerMode = "direct_citation" | "consensus" | "historical_development" | "scholarly_dispute" | "institutional_policy";

interface ChatComposerProps {
  defaultAnswerMode: AnswerMode;
  sessionId: string | null;          // null → standalone; string → follow-up
  onResponse: (r: VerifiedResponse) => void;
  onError: (e: ApiError) => void;
  disabled?: boolean;
  maxLength?: number;                // defaults to 4000 to match openapi
}

interface ChatComposerState {
  value: string;
  isSubmitting: boolean;
  streamProgress: { stage: string; at: string }[];
}
```

Behavior:

- Enter submits; Shift+Enter inserts a newline.
- Posts to `/api/v1/query` with `streamProgress: true`. Progress events update local state and render in `<StageStatus>`. The terminal `done` event fires `onResponse`. Event grammar: see `code-gen-guide.md §Server-Sent Events (SSE) for /query progress`.
- On 4xx, fires `onError(error)`.
- Disables the textarea while `isSubmitting`.

### `<AnswerPanel>` (server)

Renders the verified answer. Reads `VerifiedResponse`.

```ts
interface AnswerPanelProps {
  response: VerifiedResponse;
  onCitationClick: (citationId: string) => void;
}
```

Behavior:

- Renders `response.answer` with citation markers (e.g., `[1]`) interleaved.
- Each marker is a button with `aria-label="Citation 1"`. Clicking calls `onCitationClick`.
- Renders `<ConfidenceBadge>` reflecting `response.confidenceTier`.
- When `response.handling === "answer_with_disclaimer"`, renders `<DisclaimerBanner>` above the answer.
- When `response.handling === "block_with_redirect"` or `"insufficient_evidence"`, renders the bounded fallback message and hides citation markers.
- When `response.reframing.wasReframed === true`, renders `<ReframingDisclosure>` between the question (in transcript) and the answer.

### `<CitationPanel>` (server)

Renders the citation list and the optional evidence packet drawer.

```ts
interface CitationPanelProps {
  citations: VerifiedResponse["citations"];
  evidencePacket?: EvidencePacket;       // hidden in member view; visible when role allows
  highlightedCitationId: string | null;
  onCitationClick: (citationId: string) => void;
}
```

Behavior:

- Each citation row shows: `title`, `father` (if present), `work` (if present), `page`/`timestamp`, and the `quote` if present.
- Clicking a row scrolls the panel to that row and emits `onCitationClick`.
- Highlighted row has `aria-current="true"`.
- The evidence packet drawer is rendered only when the current `Principal.role` is `scholar`, `content_manager`, `admin`, or `owner`. Members never see it (per closed-corpus governance, the evidence packet may include suppressed-chunk IDs).

### `<ReframingDisclosure>` (server)

Single-purpose component. Always transparent reframing per ADR 0002.

```ts
interface ReframingDisclosureProps {
  reframing: VerifiedResponse["reframing"];
}
```

Behavior:

- Renders only when `reframing.wasReframed === true`.
- Shows the `disclosureText` plus a small label "We answered a teaching-oriented version of your question."
- Shows both `originalQuery` and `reframedQuery` in collapsible blocks.
- Does not provide a "view as originally asked" toggle (decision register row F).

### `<ConfidenceBadge>` (server)

Visual badge for confidence tier, with text and color (color is the redundant cue, not the only one).

```ts
interface ConfidenceBadgeProps {
  tier: "GREEN" | "YELLOW" | "RED";
  size?: "sm" | "md";
}
```

### `<DisclaimerBanner>` (server)

```ts
interface DisclaimerBannerProps {
  templateId?: string;                   // resolves to the tenant's disclaimerTemplateId text
  category: ClassifiedQuery["sensitivityPrimary"];
}
```

### `<StageStatus>` (client)

Renders the live progress stream from `<ChatComposer>` while a query is running.

```ts
interface StageStatusProps {
  stages: { stage: string; at: string }[];
  isComplete: boolean;
}
```

### `<AdminApprovalQueue>` (client)

```ts
interface AdminApprovalQueueProps {
  initialChunks: Chunk[];               // server-fetched first page
  initialNextCursor: string | null;
  onApprove: (chunkId: string) => Promise<void>;
  onReject: (chunkId: string, note: string) => Promise<void>;
  onSetVisibility: (chunkId: string, visibility: Chunk["visibility"]) => Promise<void>;
}
```

Behavior:

- Lists chunks with `approved: false` first; toggle filter to show approved.
- Per-row actions: Approve, Reject (opens note modal), Set Visibility.
- Optimistic UI: action fires; on 4xx, row reverts and a toast shows the error code.
- Pagination loads next page on scroll.

### `<AdminQueryLog>` (server)

Reads from `GET /admin/queries` and renders a sortable table of `RunTrace` summaries.

```ts
interface AdminQueryLogProps {
  page: { items: RunTrace[]; nextCursor: string | null };
  filters: { handling?: string; confidenceTier?: "GREEN" | "YELLOW" | "RED"; since?: string };
  redactionMode: "redacted" | "raw_admin";
}
```

Behavior:

- Default redaction mode is `"redacted"`. The `"raw_admin"` mode requires `admin` role and produces an `audit_entries` row on first reveal of each row. `redactionMode='raw_admin'` is honored by the backend only when the principal holds `admin:raw_sensitive:read` and only on the `/admin/queries/{runId}/raw` endpoint; on `/admin/queries` the prop is a UI hint with no effect (the API always returns redacted text on the list endpoint).
- Columns: time, runId (truncated), handling, confidenceTier, cacheHit, durationMs.
- Click a row → navigate to `/runs/[runId]`.

### `<AdminFlaggedList>` (server)

Reads from `GET /admin/flagged`.

```ts
interface AdminFlaggedListProps {
  page: { items: FlaggedQuery[]; nextCursor: string | null };
  redactionMode: "redacted" | "raw_admin";
}
```

### `<AdminAuditLog>` (server)

Reads from `GET /admin/audit`.

```ts
interface AdminAuditLogProps {
  page: { items: AuditEntry[]; nextCursor: string | null };
}
```

### `<TenantSwitcher>` (client)

Header component. Wraps Clerk's `<OrganizationSwitcher>`. After org switch, calls `clerk.setActive({ organization })` and refreshes the route. The backend resolves the new tenant from the new token; no app-side tenant state is needed.

## Error Boundary

A single route-level error boundary at `web/app/error.tsx` renders user-friendly text keyed off `ApiError.code`. Always shows the `traceId`. Never shows raw stack traces.

### Localization Strategy

- Localized strings live at `web/lib/i18n/errors.<locale>.json` keyed by `ApiError.code` (e.g., `"corpus_empty": "This library has no approved sources yet…"`).
- The default locale (`en`) is required; other locales fall back to `en` per missing key.
- An unknown `code` (one not in the i18n file for any locale) renders a generic localized message (`errors.<locale>.json#unknown_error`) plus the `traceId`. The unknown code is logged via `console.warn` for inventory tracking.
- The `traceId` is always rendered verbatim in a copyable element so support can correlate to backend logs.
- Per `error-taxonomy.md`, codes marked `user-visible: no` (e.g., `tenant_mismatch`, `unapproved_chunk`, `webhook_*`) render the same generic message as unknown codes — the specific code is logged client-side but never displayed to the user.
- The `details` object on `ApiError` is never rendered to the user. It may be inspected in development mode (`process.env.NODE_ENV === 'development'`) under a collapsed "Developer details" section.

## Loading States

Every server component pair has a sibling `loading.tsx` (Next.js convention) showing a skeleton. Skeleton components live under `web/components/ui/skeleton/`.

## Forbidden

- Direct `fetch` to backend endpoints (use `api-client.ts`).
- Storing the bearer token in `localStorage` (Clerk handles tokens).
- Rendering raw chunk text or raw query text in admin views without first selecting `redactionMode === "raw_admin"`.
- Adding a "view as originally asked" toggle on `<ReframingDisclosure>`.
- Polling for run status faster than every 2 seconds in `/runs/[runId]`.
- Layout shift from late-arriving stage progress (the stage area must reserve its height).
