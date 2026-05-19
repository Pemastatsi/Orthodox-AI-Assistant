# T-116: Liturgical Calendar Overlay

## Goal

Implement the Liturgical Calendar Overlay: compute today's feast, saint(s), Gospel/Epistle pericope, fasting rule, and Byzantine tone from the tenant's `calendarProfile`. Cache per `(tenantId, date, calendarStyle)` for 24 hours. Display alongside Q&A answers as contextual framing. Does not increment any billing meter. Does not influence A5 composition (context only, not evidence).

## Required Reads

- [`docs/contracts/multimedia-integration-contract.md`](../../contracts/multimedia-integration-contract.md) — calendar data source, caching, overlay behavior rules.
- [`docs/schemas/liturgical-context.schema.json`](../../schemas/liturgical-context.schema.json).
- [`docs/schemas/calendar-profile.schema.json`](../../schemas/calendar-profile.schema.json) — `calendarStyle` field.
- [`docs/contracts/rich-output-rendering.md`](../../contracts/rich-output-rendering.md) — `<LiturgicalOverlay>` contract.
- [`docs/contracts/cache-key.md`](../../contracts/cache-key.md) — `calendarVersion` cache key field.

## Files In Scope

- `backend/app/domain/services/liturgical_calendar.py` — deterministic calendar algorithm for Julian, Revised Julian, Coptic; outputs `LiturgicalContext`.
- `backend/app/api/v1/calendar.py` — `GET /calendar/today` endpoint; reads from cache or computes.
- `web/components/artifacts/LiturgicalOverlay.tsx` — compact chip (feast name, fasting rule, tone) and expanded card variant.

## Acceptance Tests

1. `GET /calendar/today` returns a valid `LiturgicalContext` for the current date.
2. Julian and Revised Julian calendars produce different dates for feast days that diverge between them.
3. Response is cached: second request within 24 hours returns same data without recomputation.
4. `LiturgicalContext` does NOT appear in A5 composition prompt (assert in `run_traces.stages` that calendar data is absent from composer input).
5. `<LiturgicalOverlay compact={true}>` renders a single-line chip; `compact={false}` renders expanded card.
6. Feast suggestion banner shown when `feastName` is semantically related to the query topic.

## Forbidden Scope

- Injecting `LiturgicalContext` into the A5 composition prompt (display only).
- External calendar API calls at runtime (deterministic algorithm only).
- Per-user calendar customization (tenant-level `calendarStyle` only in Phase 2).
