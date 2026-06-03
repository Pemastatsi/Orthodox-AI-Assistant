# `a1_classifier` — A1+A2 combined query analyzer / retrieval planner

Classifies the user query and emits a `RetrievalPlan` as one structured JSON
object (`classifiedQuery` + `retrievalPlan`). It does **not** answer the question
and does **not** invent citations; it only applies a transparent safety reframing
for sensitive advice-seeking queries. See `AGENTS.md` and the JSON shape derived
from `ClassifiedQuery` + `RetrievalPlan`.

- **Loaded by** `backend/app/domain/prompts/query_analyzer_a1_a2.py` at import via
  `load_prompt("a1_classifier", "en", <version>)`.
- **Version pin:** `Settings.active_prompt_version_a1a2`
  (`qa_analyze@2026-05-01.1` → file `en/2026-05-01.1.j2`).
