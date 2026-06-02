# `a5_composer` — closed-corpus answer composer

Answers the user's question using **only** `EvidencePacket.admittedChunks` (plus
the reframed query when present). No general knowledge, no chain-of-thought, no
external corpora. Outputs one JSON object: `answer` + `citedChunkIds`. See
`AGENTS.md §Closed-Corpus Rules` and ADR-0001.

- **Runtime source of truth** (until the loader migration): `_SYSTEM_PROMPT` in
  `backend/app/domain/prompts/composer_a5.py`.
- **Version pin:** `Settings.active_prompt_version_a5`
  (`a5_compose@2026-05-01.1` → file `en/2026-05-01.1.j2`).
- `en/2026-05-01.1.j2` is kept byte-identical to that literal by
  `tests/prompts/test_prompt_files_match_inline.py`.
