# `a5_composer` — closed-corpus answer composer

Answers the user's question using **only** `EvidencePacket.admittedChunks` (plus
the reframed query when present). No general knowledge, no chain-of-thought, no
external corpora. Outputs one JSON object: `answer` + `citedChunkIds`. See
`AGENTS.md §Closed-Corpus Rules` and ADR-0001.

- **Loaded by** `backend/app/domain/prompts/composer_a5.py` at import via
  `load_prompt("a5_composer", "en", <version>)`.
- **Version pin:** `Settings.active_prompt_version_a5`
  (`a5_compose@2026-05-01.1` → file `en/2026-05-01.1.j2`).
