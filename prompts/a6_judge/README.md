# `a6_judge` — optional closed-corpus consistency judge (ADR-0004)

A low-cost LLM check that may **downgrade** a GREEN answer to YELLOW when the answer drifts
from the evidence; it can never upgrade or override a deterministic verifier miss. **Disabled
by default** (`judge_route_id` empty / `Settings.active_model_route_verifier` unset — finding
F-08). The deterministic A6 checks in `verifier.py` run regardless and do **not** use this
prompt.

- **Loaded by** `backend/app/domain/agents/verifier.py` at import via
  `load_prompt("a6_judge", "en", <version>)`; used in `_maybe_downgrade` when the judge is enabled.
- **Version pin:** `Settings.active_verifier_version` (`a6_verify@2026-05-01.1` → file
  `en/2026-05-01.1.j2`). When the judge is productionized it gets its own certified route and
  prompt version.
- `en/2026-05-01.1.j2` intentionally has **no trailing newline** — it is byte-identical to the
  inline literal it replaced.
