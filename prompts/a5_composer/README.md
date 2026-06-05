# `a5_composer` — closed-corpus answer composer

Answers the user's question using **only** `EvidencePacket.admittedChunks` (plus
the reframed query when present). No general knowledge, no chain-of-thought, no
external corpora. Outputs one JSON object: `answer` + `citedChunkIds`. See
`AGENTS.md §Closed-Corpus Rules` and ADR-0001.

- **Loaded by** `backend/app/domain/prompts/composer_a5.py` at import via
  `load_prompt("a5_composer", "en", <version>)`.
- **Version pin:** `Settings.active_prompt_version_a5`
  (`a5_compose@2026-06-05.1` → file `en/2026-06-05.1.j2`).

## Versions

- `2026-05-01.1` — initial closed-corpus composer. Single output shape:
  `answer` + `citedChunkIds`.
- `2026-06-05.1` — **adds the `scholarly_dispute` output shape** (T-006 §Scholarly
  Dispute UX). Rules 1–6 are unchanged from `2026-05-01.1`; rule 7 now branches on
  `answerMode`. For `answerMode == "scholarly_dispute"` the model emits `positions[]`
  (each a neutral `name` drawn from the evidence, a `thesis`, and column-scoped
  `citedChunkIds`) instead of a single `answer`; it must never merge opposing positions
  into a consensus or declare a winner. A6 verifies each position independently and
  fails closed to a bounded response when fewer than two positions survive. Promotion to
  the active pin requires the safety-suite + retrieval-eval CI checks green and founder
  review per `docs/contracts/prompt-management.md`.
