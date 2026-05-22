# Prompt Management Contract

Status: Canonical
Date: 2026-05-22

This contract codifies how system prompts and prompt templates are authored, versioned, certified, and invoked across the A1–A6 pipeline. It is the canonical reference for ADR-0004 §"Prompt-Version Lifecycle" and approved-decisions-register decision 6 (the structural piece pulled forward to Phase 1 by GS-3).

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
- **Files named by version** following the `YYYY-MM-DD.N` convention shared with `prompt_versions.prompt_version` in `db-schema.md`. The `.N` counter resets per day per stage per language. The file extension is `.j2` for Jinja2 templates (the default) or `.yaml` for structured prompts that the adapter renders into a chat message list.
- **Per-stage `README.md`** records the rationale for each version (what changed, who approved it, what safety-suite + retrieval-eval run aggregate produced the green CI required to merge it). The README is required at every stage directory.

## Path → `prompt_version` mapping

The `ModelRoute.prompt_version` and `RunTrace.stages[].details.promptVersion` fields are strings of the form `{stage}/{language}/{date}.{counter}` — the exact relative path under `/prompts/` minus the file extension. Examples:

- `a5_composer/en/2026-05-22.1`
- `context_prefix/en/2026-05-22.1`
- `a1_classifier/el/2026-05-01.1`

The startup self-check fails when an active `ModelRoute` references a `prompt_version` that does not correspond to a file on disk.

## Authoring rules

1. **Add, never edit.** A new prompt version is a new file. Modifying an existing committed file under `/prompts/` is forbidden once the file has been referenced by any merged `ModelRoute` row. Renames are also forbidden — the path identifier must remain stable for audit-trail integrity.
2. **One concern per template.** Templates do not branch on cross-stage state; an A5 composer template does not know whether A6 ran in `standard` or `strict` mode. Cross-stage state is handled in code, not in templates.
3. **Schema-aware.** Templates that drive `generate_structured` calls reference the same JSON schema the adapter sends with the request. The schema reference lives next to the template (e.g., `/prompts/a2_planner/en/2026-05-01.1.schema.json` is a symlink or copy of `docs/schemas/retrieval-plan.schema.json`). At runtime, the template-loader verifies the live schema matches the template-time copy and refuses to render on mismatch (drift guard).
4. **No secrets in templates.** Templates render with the user's query and retrieved chunks as variables. Secrets, API keys, and credentials never appear in template files (covered by the existing `.gitignore` and the pre-commit secret-scan).
5. **No PII anchoring.** Templates do not include hard-coded user names, email addresses, or other PII even in examples. Example variables use `{{ example_father }}`, never literal personal references.

## CI gate (the change-detection contract)

The `prompts-gate` job in `.github/workflows/ci-safety-gate.yml` (introduced by the T-008 amendment to T-001) does the following on every PR:

```
1. Compute git diff --name-only origin/main...HEAD restricted to /prompts/**.
2. If the diff is empty, exit 0 (no prompt changes).
3. For each affected stage/language pair, build a candidate ModelRoute that
   references the new prompt_version.
4. Run backend/tests/safety/test_20_queries_harness.py against the candidate
   route. Any non-passing case fails the PR.
5. Run tests/retrieval_eval/ for the affected purpose (e.g., a candidate
   a5_composer change runs the retrieval-eval suite). Any metric below
   baseline − 0.02 fails the PR.
6. Insert a safety_suite_runs aggregate row and a model_route_invocations
   audit row referencing the CI run; both rows are deleted at the end of the
   job (CI database is ephemeral).
```

The gate runs in the same CI workflow as the existing `safety-suite-execution` job; the two jobs share the same harness binary so prompt-only changes do not require a parallel scaffolding.

## Runtime — template-loader contract

The application's template-loader (`backend/app/services/prompts/loader.py`, T-001 deliverable) implements:

- `load_template(stage: str, language: str, version: str) -> RenderedTemplate` — reads the file, validates it against the schema sidecar if present, caches by path.
- `render(template: RenderedTemplate, variables: dict) -> RenderedPrompt` — renders Jinja2 or expands YAML; rejects undefined variables (`StrictUndefined`) so a stale template referencing a variable the agent no longer produces fails loudly at runtime.
- `audit_render(rendered: RenderedPrompt, run_id: str) -> None` — writes `prompt_id` and `prompt_version` to the `RunTrace.stages[]` for the current stage; the loader does NOT log the rendered prompt content (chunks are Confidential per ADR-0005).

The loader does NOT permit dynamic prompt composition from substrings stored in the database. Dynamic prompt composition is the runtime-piece of decision 6, which remains post-MVP.

## Forensic auditability

For any historical query, the operator can reconstruct the exact prompt template that served it by:

1. Look up `RunTrace.stages[].details.promptVersion` for the relevant stage.
2. `git show <hash>:prompts/<path>.j2` to view the template as it was at the time of the query.
3. The `model_route_invocations.prompt_version` field is a redundant copy for cross-checking against the route registry.

If a template is later superseded by a new version, the old file remains on disk (rule 1: add, never edit). `git log` traces who authored which version and when CI accepted it.

## Forbidden patterns

- Embedded prompt strings inside `.py`, `.ts`, or `.tsx` files. The codebase MUST NOT contain any string literal longer than 200 characters whose content looks like a system prompt (heuristic: contains the substring `You are` or `Your task is`). A unit test in `tests/unit/test_no_embedded_prompts.py` greps the application source tree for these heuristics.
- Mutating a committed prompt file in place.
- Renaming a prompt file path after it has been referenced by a merged `ModelRoute`.
- Reading prompt files outside the template-loader (no `open("/prompts/...")` in agent code).
- Routing user input through the template raw — every variable goes through Jinja2 escaping or the YAML-structured value pipe.
- Using `Environment(autoescape=False)` — the loader configures autoescape on by default to mitigate prompt-injection vectors from user-supplied content.

## References

- ADR-0004 §"Prompt-Version Lifecycle" — the route-certification contract this doc supports.
- `docs/contracts/approved-decisions-register.md` decision 6 — the structural-vs-runtime split this doc resolves for Phase 1.
- `docs/contracts/db-schema.md` §`prompt_versions` — the table where each rendered `prompt_version` is mirrored; for Phase 1 the contract source is the filesystem under `/prompts/` and the DB row mirrors that path identifier.
- `docs/schemas/run-trace.schema.json` — the `stages[].details.promptVersion` field surfaced to operators.
- `docs/contracts/observability.md` — confirmed that prompt content itself is NOT logged.
- 2026-05-22 frontier meta-evaluation — GS-3.
