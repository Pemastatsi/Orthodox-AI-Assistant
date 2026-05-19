# T-101: Rich Text Rendering

## Goal

Enable Markdown, Mermaid diagram, and LaTeX mathematical/theological notation rendering in the `<AnswerPanel>`. This is the lowest-cost, highest-impact Phase 2 capability: it requires no new backend routes, no new schemas, and no billing changes. The `verified-response.schema.json` gains a `richText: boolean` flag; when true, the frontend renders the `answer` field as Markdown instead of plain text.

## Required Reads

- [`docs/contracts/rich-output-rendering.md`](../../contracts/rich-output-rendering.md) — component contracts.
- [`docs/adr/0013-rich-output-format-strategy.md`](../../adr/0013-rich-output-format-strategy.md) — Tier 1 definition.
- [`docs/contracts/frontend-components.md`](../../contracts/frontend-components.md) — existing `<AnswerPanel>` contract.
- [`docs/api/openapi.yaml`](../../api/openapi.yaml) — `VerifiedResponse` component to extend.
- [`docs/schemas/verified-response.schema.json`](../../schemas/verified-response.schema.json) — add `richText` flag.

## Files In Scope

**Backend:**
- `docs/schemas/verified-response.schema.json` — add `richText: boolean` (default `false`), `answerMarkdown: string | null`.
- `docs/api/openapi.yaml` — add `richText` and `answerMarkdown` to `VerifiedResponse` component.
- `backend/app/domain/models/verified_response.py` — add fields.
- `backend/app/domain/services/composer.py` — A5 route may output Markdown when `richText=true`; plain text otherwise for backward compatibility.

**Frontend:**
- `web/components/answer/AnswerPanel.tsx` — conditional Markdown rendering when `richText=true`.
- `web/components/answer/MermaidBlock.tsx` — new client component for Mermaid diagram rendering.
- `web/lib/markdown.ts` — Markdown-to-React renderer configuration (remark + rehype pipeline).
- `package.json` — add `react-markdown`, `remark-gfm`, `rehype-sanitize`, `mermaid`.

## Acceptance Tests

1. `POST /query` with `richText: false` (default) returns `answer` as plain text; `<AnswerPanel>` renders without HTML.
2. `POST /query` with `richText: true` (tenant config opt-in) returns `answerMarkdown`; `<AnswerPanel>` renders headings, bold, tables, lists correctly.
3. A Mermaid code fence in `answerMarkdown` renders as an interactive diagram via `<MermaidBlock>`.
4. HTML injection attempt in `answerMarkdown` (e.g. `<script>alert(1)</script>`) is sanitized by `rehype-sanitize`; no script executes.
5. Citation markers `[1]`, `[2]` in Markdown remain clickable and open the `<CitationPanel>`.
6. Existing plain-text Phase 1 responses are unaffected (backward compatible).
7. `redocly lint docs/api/openapi.yaml` exits 0 after schema changes.

## Forbidden Scope

- Adding a free-form Markdown editor for tenants (Phase 1 restriction still applies).
- Adding LaTeX rendering (deferred to T-101 Wave 2 amendment; libraries add significant bundle size).
- Streaming Markdown rendering before A6 verification.
- Changing the default `richText` to `true` (opt-in only in Phase 2).
