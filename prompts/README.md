# Prompt Registry (`/prompts`)

Version-controlled home for the answer-pipeline prompts (GS-3).

## Layout

```
prompts/<stage>/<language>/<version>.j2
```

- **stage** — pipeline stage id (`a1_classifier`, `a5_composer`, …).
- **language** — BCP-47-ish content language (`en`).
- **version** — the `<YYYY-MM-DD.NN>` portion of the route's `promptVersion`
  (e.g. `2026-05-01.1`). The exact `promptVersion` ⇄ filename mapping is
  finalized by the runtime loader (see _Status_ below).

## Versioning rule: add, never edit

A prompt's behavior is part of a certified `ModelRoute`. **Never edit an existing
`.j2` in place.** To change a prompt:

1. Add a **new** `<version>.j2` (bump `NN`, or roll the date).
2. Bump the route's `promptVersion` and re-certify it — the safety suite
   (`tests/safety`) **and** retrieval-eval regression must pass — per
   `docs/adr/0004-*` and `docs/contracts/`.

The `prompts-gate` CI job validates this tree's **layout** and **drift** on every
PR. A change to prompt *text* additionally requires the `safety-suite-execution`
and `retrieval-eval-regression` checks (route re-certification).

## Current contents

| Stage | File | Mirrors (runtime source of truth) | Version pin |
|---|---|---|---|
| `a1_classifier` | `a1_classifier/en/2026-05-01.1.j2` | `backend/app/domain/prompts/query_analyzer_a1_a2.py` `_SYSTEM_PROMPT` | `Settings.active_prompt_version_a1a2` |
| `a5_composer` | `a5_composer/en/2026-05-01.1.j2` | `backend/app/domain/prompts/composer_a5.py` `_SYSTEM_PROMPT` | `Settings.active_prompt_version_a5` |

## Status — Phase-1 bootstrap

This is the **structural bootstrap** of GS-3. The agents still load their prompt
from the inline `_SYSTEM_PROMPT` literal in `backend/app/domain/prompts/*.py` at
runtime; the `.j2` files here are the **canonical copy**, kept byte-identical to
that inline literal by `tests/prompts/test_prompt_files_match_inline.py` so the
two cannot silently drift.

**Tracked follow-up** (not in this bootstrap): a runtime template-loader that
renders these files (Jinja autoescape + `StrictUndefined`, per-prompt JSON-schema
sidecars, startup self-check), rewiring the agents to load from `/prompts`, and
removing the inline literals.

### Deferred prompts

- **`a6_judge`** — the optional closed-corpus consistency judge (ADR-0004) is
  **disabled by default** (`judge_route_id` empty, finding F-08) and its prompt
  is an inline concatenated literal inside `verifier.py::_run_judge` (not a
  module constant). It is migrated when the judge is productionized.
- **`retrieval_eval_judge`** — the Ragas-style retrieval-eval judge
  (`docs/contracts/retrieval-eval-suite.md`) is migrated with its own suite.
