# Prompt Registry (`/prompts`)

Version-controlled, **runtime source of truth** for the answer-pipeline system prompts (GS-3).

## Layout

```
prompts/<stage>/<language>/<version>.j2
```

- **stage** — pipeline stage id (`a1_classifier`, `a5_composer`, …).
- **language** — BCP-47-ish content language (`en`).
- **version** — the `<YYYY-MM-DD.NN>` portion of the route's `promptVersion`
  (e.g. `2026-05-01.1`); the loader strips the `<name>@` prefix to find the file.

## How prompts are loaded

At import, the A1/A2 and A5 builders call
`app.domain.services.prompt_loader.load_prompt(stage, language, version)` to read the active
`.j2` (selected by `Settings.active_prompt_version_*`; registry root is `Settings.prompts_dir`,
default `<repo>/prompts`). The text is returned **verbatim** — no templating: the current
prompts carry no variables (dynamic context is composed in Python around the system prompt),
so a `.j2` with no Jinja tags renders to its own bytes. A missing file raises
`PromptNotFoundError`, so a misconfigured route fails fast at startup rather than serving an
empty system prompt. A rendering layer (Jinja with autoescape **off** for prompt text) can be
added the day a prompt first needs variables.

## Versioning rule: add, never edit

A prompt's behavior is part of a certified `ModelRoute`. **Never edit an existing `.j2` in
place.** To change a prompt:

1. Add a **new** `<version>.j2` (bump `NN`, or roll the date).
2. Bump the route's `promptVersion` and re-certify it — the safety suite (`tests/safety`)
   **and** retrieval-eval regression must pass — per `docs/adr/0004-*` and `docs/contracts/`.

The `prompts-gate` CI job validates this tree's **layout** and enforces the
**no-embedded-prompts** rule on every PR (`tests/prompts/test_prompt_registry.py`, dep-free).
`backend/tests/unit/test_prompt_loader.py` additionally asserts each builder serves the exact
registry text its active route advertises. A change to prompt *text* also requires the
`safety-suite-execution` and `retrieval-eval-regression` checks (route re-certification).

## Current contents

| Stage | File | Loaded by | Version pin |
|---|---|---|---|
| `a1_classifier` | `a1_classifier/en/2026-05-01.1.j2` | `query_analyzer_a1_a2.py` (via `load_prompt`) | `Settings.active_prompt_version_a1a2` |
| `a5_composer` | `a5_composer/en/2026-05-01.1.j2` | `composer_a5.py` (via `load_prompt`) | `Settings.active_prompt_version_a5` |
| `a6_judge` | `a6_judge/en/2026-05-01.1.j2` | `verifier.py` (via `load_prompt`; judge **disabled by default**, F-08) | `Settings.active_verifier_version` |

## Deferred

- **`retrieval_eval_judge`** — the Ragas-style retrieval-eval judge
  (`docs/contracts/retrieval-eval-suite.md`) is migrated with its own suite.
- **Templating** — Jinja rendering (autoescape disabled for prompt text) + per-prompt JSON
  schema sidecars, added when a prompt first needs variables.
