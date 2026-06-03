# Prompt Management Contract

Status: Canonical
Date: 2026-05-22
Amended: 2026-06-02

This contract codifies how system prompts and prompt templates are authored, versioned, certified, and invoked across the A1–A6 pipeline. It is the canonical reference for ADR-0004 §"Prompt-Version Lifecycle" and approved-decisions-register decision 6 (the structural piece pulled forward to Phase 1 by GS-3).

> **Amendment 2026-06-02 (GS-3 implementation).** The pipeline composes dynamic and untrusted content (user query, retrieved chunks, soft-trigger notes, reframed query) as **separate structured chat messages**, never interpolated into the system prompt. Prompts are therefore *static instruction templates* loaded **verbatim** — there is no Jinja render step today and `jinja2` is **not** a dependency. The original draft assumed variable interpolation with `autoescape=ON` as a prompt-injection control; that is both unnecessary here (no variables) and the wrong mechanism (Jinja `autoescape` is HTML-entity escaping — it neither stops natural-language prompt injection nor preserves prompt fidelity). Structured-message separation is the injection control. The sections below reflect the implemented design; the `.j2` extension is retained as a forward-looking convention, and a render layer (with `autoescape=OFF` for prompt text) may be added the day a prompt first needs a variable. ADR-0004 (directory layout + no-embedded-prompts) is unchanged.

The runtime piece — admin-facing free-form prompt editing with preview and rollback — remains post-MVP. This contract governs platform-authored prompt templates only.

## Why this exists as a separate doc

Embedded prompt strings inside agent code are a known maintenance hazard:

- They mix concerns: prompt wording lives next to control flow, and any change to wording touches a `.py` file that already has dozens of unrelated reasons to change.
- They make regression testing implicit: a careless edit to a system-prompt string in a service file slips past code review more easily than a change to a versioned template.
- They make A/B testing and rollback expensive: rolling back a prompt change requires reverting an unrelated commit.
- They make audit trails fuzzy: `RunTrace` records a `prompt_version` string that has to match a file or a database row, not a substring of a source file.

The canonical fix is to treat prompts as first-class artifacts under version control, with a directory structure that makes the `prompt_version` field on `ModelRoute` and `RunTrace` a real path identifier.

## Directory layout

All system prompts live under `/prompts/` at the repository root:

```
/prompts/
├── a1_classifier/
│   ├── en/
│   │   ├── 2026-05-01.1.j2
│   │   ├── 2026-06-15.1.j2
│   │   └── README.md          # rationale for each version
│   └── el/
│       └── 2026-05-01.1.j2
├── a2_planner/
│   └── en/
│       └── 2026-05-01.1.j2
├── a5_composer/
│   ├── en/
│   │   ├── 2026-05-01.1.j2
│   │   └── 2026-05-22.1.j2   # contextual-retrieval-aware
│   └── el/
│       └── 2026-05-01.1.j2
├── a6_judge/
│   └── en/
│       └── 2026-05-01.1.j2
├── context_prefix/             # REC-005, D-MDL-002
│   └── en/
│       └── 2026-05-22.1.j2
├── edge_extraction/            # REC-013, D-MDL-003
│   └── en/
│       └── 2026-05-22.1.j2
└── retrieval_eval_judge/
    └── en/
        └── 2026-05-01.1.j2
```

- **Top-level directory per agent stage** (`a1_classifier`, `a2_planner`, `a5_composer`, `a6_judge`, plus ingestion-time stages `context_prefix` and `edge_extraction`, plus `retrieval_eval_judge`).
- **Subdirectory per language** (`en`, `el`, `mixed`). Each file targets one language; multi-language prompts split into language-specific files.
- **Files named by version** following the `YYYY-MM-DD.N` convention shared with `prompt_versions.prompt_version` in `db-schema.md`. The `.N` counter resets per day per stage per language. The file extension is `.j2`, retained as a forward-looking convention — **today the loader reads `.j2` files verbatim, with no Jinja rendering** (the prompts carry no variables; see §Runtime and the 2026-06-02 amendment).
- **Per-stage `README.md`** records the rationale for each version (what changed, who approved it, what safety-suite + retrieval-eval run aggregate produced the green CI required to merge it). The README is required at every stage directory.
- **Populated in Phase 1:** `a1_classifier`, `a5_composer`, `a6_judge` (`en`). `a2_planner` is folded into `a1_classifier` (the combined A1+A2 classifier). `context_prefix` / `edge_extraction` are ingestion-time prompts not yet authored. `retrieval_eval_judge` uses **DeepEval's library-owned metric prompts** routed through the certified judge route — there is no prompt file of ours to register (see `prompts/README.md`).

## Path → `prompt_version` mapping

Two related identifiers are in play:

- **`ModelRoute.prompt_version`** (and the cache-key `promptVersion`) is the route/cache identifier `{name}@{date}.{counter}`, e.g. `a5_compose@2026-05-01.1` — the stable value stamped on the route and hashed into the response cache key.
- **The registry path** `{stage}/{language}/{date}.{counter}` locates the file on disk, e.g. `a5_composer/en/2026-05-01.1`. The `{date}.{counter}` stem is shared with the route identifier (the loader's `registry_version()` strips the `{name}@` prefix); `{stage}/{language}` come from the agent that owns the prompt.
- **`RunTrace.stages[].details.promptVersion`** records the full **registry path** (so an operator can reconstruct the exact template — see §Forensic auditability); `details.promptId` holds the `{stage}/{language}` stem.

The startup self-check fails when an active prompt version does not resolve to a file on disk (`backend/tests/unit/test_prompt_loader.py::test_active_prompt_versions_resolve_to_files`).

> Unifying `ModelRoute.prompt_version` onto the bare registry-path form is a deferred migration (it would re-hash the cache-key golden vectors in `backend/tests/unit/test_cache_key.py`); the two-identifier mapping above is the Phase-1 state.

## Authoring rules

1. **Add, never edit.** A new prompt version is a new file. Modifying an existing committed file under `/prompts/` is forbidden once the file has been referenced by any merged `ModelRoute` row. Renames are also forbidden — the path identifier must remain stable for audit-trail integrity.
2. **One concern per template.** Templates do not branch on cross-stage state; an A5 composer template does not know whether A6 ran in `standard` or `strict` mode. Cross-stage state is handled in code, not in templates.
3. **Schema-aware.** Stages that drive `generate_structured` calls derive the JSON schema from a single in-code source of truth — A1/A2 from the `ClassifiedQuery` + `RetrievalPlan` Pydantic models, A5 from `composer_a5.composer_output_schema()` — so the schema the prompt expects and the schema the adapter sends cannot drift (they are the same object). Parity is guarded by `backend/tests/unit/test_models_roundtrip.py`. Sidecar `.schema.json` files next to templates are therefore not required.
4. **No secrets in prompts.** Secrets, API keys, and credentials never appear in prompt files (covered by the existing `.gitignore` and the pre-commit secret-scan). Dynamic content (the user's query and retrieved chunks) is **not** placed in the prompt file at all — it is passed as separate structured messages at call time.
5. **No PII anchoring.** Prompt files do not include hard-coded user names, email addresses, or other PII, even in examples — use a neutral placeholder (e.g. `<example_father>`), never literal personal references.

## CI gate (the change-detection contract)

Two layers in `.github/workflows/ci-safety-gate.yml` gate prompt changes on every PR:

1. **`prompts-gate`** (dep-free, `pytest tests/prompts/`) validates the registry: the `{stage}/{language}/{version}.j2` layout, per-stage READMEs, and the no-embedded-prompts rule (answer-path prompt constants are `load_prompt(...)` calls; no >200-char prompt literal in `backend/app/**`).
2. **`safety-suite-execution`** and **`retrieval-eval-regression`** are required checks that run on **every** PR — including any that touches `/prompts/**` — so a prompt change is gated by the full 20-case theological safety suite and the deterministic retrieval-eval metrics before merge.

Because the safety + retrieval-eval suites run unconditionally on every PR, a separate candidate-route harness with ephemeral audit rows is unnecessary; the change-detection intent (no prompt change merges without those suites passing) is satisfied by them being required checks.

## Runtime — prompt-loader contract

The application's prompt-loader is `backend/app/domain/services/prompt_loader.py` (codebase convention — the agents import from `app.domain.services`):

- `load_prompt(stage: str, language: str, version: str) -> str` — returns the file's text **verbatim** (no rendering), `lru_cache`d by path; raises `PromptNotFoundError` when the file is absent, so a misconfigured route fails fast at startup.
- `registry_version(prompt_version: str) -> str` — maps a route `promptVersion` (`{name}@{date}.{counter}`) to its on-disk version stem (`{date}.{counter}`).
- **Audit:** the query pipeline writes `promptVersion` (the full registry path) and `promptId` into `RunTrace.stages[].details` for each model-backed stage (`backend/app/api/v1/query.py`, helpers `_stage_a1a2` / `_stage_a5`). Prompt *content* is never logged (chunks are Confidential per ADR-0005).

There is no render step and no dynamic prompt composition from database substrings (the free-form-editing piece of decision 6 remains post-MVP). **When a prompt first needs a variable,** add a minimal render layer using `Environment(autoescape=False)` (prompt text is not HTML) + `StrictUndefined`; untrusted content must still be passed as structured messages, never interpolated into the instruction prompt.

## Forensic auditability

For any historical query, the operator can reconstruct the exact prompt template that served it by:

1. Look up `RunTrace.stages[].details.promptVersion` for the relevant stage.
2. `git show <hash>:prompts/<path>.j2` to view the template as it was at the time of the query.
3. The `model_route_invocations.prompt_version` field is a redundant copy for cross-checking against the route registry.

If a template is later superseded by a new version, the old file remains on disk (rule 1: add, never edit). `git log` traces who authored which version and when CI accepted it.

## Forbidden patterns

- Embedded prompt strings inside `.py`, `.ts`, or `.tsx` files. The codebase MUST NOT contain any string literal longer than 200 characters whose content looks like a system prompt (heuristic: contains `You are` or `Your task is`). Enforced two ways: `tests/prompts/test_prompt_registry.py::test_prompt_constant_is_loaded_not_embedded` (ast — the answer-path prompt constants must be `load_prompt(...)` calls) and `::test_no_embedded_prompt_literals_in_app_source` (the >200-char heuristic scan over `backend/app/**`).
- Interpolating untrusted content (user query, retrieved chunks, tenant input) into the instruction/system prompt. Untrusted and dynamic content is passed as **separate structured chat messages** — this, not HTML autoescaping, is the prompt-injection control.
- Mutating a committed prompt file in place.
- Renaming a prompt file path after it has been referenced by a merged `ModelRoute`.
- Reading prompt files outside the prompt-loader (no `open("/prompts/...")` in agent code).

## References

- ADR-0004 §"Prompt-Version Lifecycle" — the route-certification contract this doc supports.
- `docs/contracts/approved-decisions-register.md` decision 6 — the structural-vs-runtime split this doc resolves for Phase 1.
- `docs/contracts/db-schema.md` §`prompt_versions` — the table where each rendered `prompt_version` is mirrored; for Phase 1 the contract source is the filesystem under `/prompts/` and the DB row mirrors that path identifier.
- `docs/schemas/run-trace.schema.json` — the `stages[].details.promptVersion` field surfaced to operators.
- `docs/contracts/observability.md` — confirmed that prompt content itself is NOT logged.
- 2026-05-22 frontier meta-evaluation — GS-3.
