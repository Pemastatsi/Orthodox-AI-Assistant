# `a1_classifier` — A1+A2 combined query analyzer / retrieval planner

Classifies the user query and emits a `RetrievalPlan` as one structured JSON
object (`classifiedQuery` + `retrievalPlan`). It does **not** answer the question
and does **not** invent citations; it only applies a transparent safety reframing
for sensitive advice-seeking queries. See `AGENTS.md` and the JSON shape derived
from `ClassifiedQuery` + `RetrievalPlan`.

- **Runtime source of truth** (until the loader migration): `_SYSTEM_PROMPT` in
  `backend/app/domain/prompts/query_analyzer_a1_a2.py`.
- **Version pin:** `Settings.active_prompt_version_a1a2`
  (`qa_analyze@2026-05-01.1` → file `en/2026-05-01.1.j2`).
- `en/2026-05-01.1.j2` is kept byte-identical to that literal by
  `tests/prompts/test_prompt_files_match_inline.py`.
