# Curating a real tenant gold set

This is the operator guide for **gated item #1**: replacing the synthetic `tenant_smoke` smoke set
with a real, founder/content-manager-curated gold set per `docs/contracts/retrieval-eval-suite.md`.
The curation itself is **Confidential** domain work (per `CLAUDE.md` §1) that only the tenant's
reviewers can do — this repo ships the *tooling* and *rules*, not the cases.

## What a gold set is

A per-tenant, version-pinned set of theological questions, each anchored on the stable `chunk_id`s
that should answer it. It is the empirical gate for `purpose IN ('embedding','rerank')` route
certification: a candidate route must score ≥ baseline − 0.02 on every metric against it.

File path: `tests/retrieval_eval/gold_sets/<tenantId>/<version>.json`
(`version` = `YYYY-MM-DD.NN`). Schema: `docs/schemas/retrieval-eval-gold-set.schema.json`.

## Steps

1. **Pick the cases.** 30–50 questions spanning the tenant's theological priorities and answer
   modes. Each must be answerable from **approved** chunks. Include sensitive-tier cases
   (`pastoral_advice`, `canonical_dispute`, …) — they exercise the rare retrieval paths. Do **not**
   include hard-trigger queries (`self_harm`, `medical_emergency`) — those live in the safety suite.
2. **Anchor each case.** Set `expectedChunkIds` (everything that together answers it) and
   `minimallySufficientChunkIds` (the subset that alone suffices). Use real `chunk_id`s from the
   corpus, not URLs or guesses. `minimallySufficientChunkIds ⊆ expectedChunkIds`.
3. **Record provenance.** `createdBy`, a non-empty `reviewedBy` (reviewers hold
   `role IN ('content_manager','admin','owner')`), and `corpusVersionAtCuration` (the
   `corpusVersion` the chunk ids were curated against).
4. **Validate before you gate.** Run the validator — offline first, then against the live corpus:

   ```bash
   cd backend
   uv run python ../scripts/validate_gold_set.py ../path/to/<version>.json            # schema + rules
   uv run python ../scripts/validate_gold_set.py --check-corpus ../path/to/<version>.json  # + corpus
   ```

   The corpus check fails the file if any referenced chunk is missing, unapproved, or belongs to
   another tenant, and warns if a chunk's `corpusVersion` drifted from `corpusVersionAtCuration`.
5. **First run establishes the baseline.** A passing first run on a new version sets the baseline
   (owner action, via `scripts/run_retrieval_eval.py --establish-baseline`). After that the version
   is frozen; changes ship as a new version.

## Rules (enforced by the validator)

- `reviewedBy` non-empty; `version` matches `YYYY-MM-DD.NN`; case ids match `RE-NNN` and are unique
  (never reused after deprecation).
- `minimallySufficientChunkIds ⊆ expectedChunkIds`.
- No hard-trigger sensitivities.
- (`--check-corpus`) every referenced chunk exists, is `approved = true`, and belongs to the tenant.

## Confidentiality

A real gold-set file is **Confidential** — same access tier as the corpus. Do not commit it to a
public-readable repository, paste cases into prompts/screenshots, or send them to third-party
services. The synthetic `tenant_smoke/2026-05-29.1.json` in this directory is the only
non-confidential example; it is a smoke fixture, not a certification gold set.

A `_TEMPLATE.json` skeleton sits beside this guide — copy it to
`<tenantId>/<version>.json`, fill it in, and delete the `_comment` fields.
