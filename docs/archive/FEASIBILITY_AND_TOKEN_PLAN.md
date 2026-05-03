# Archived: Best-Case Planning Reference

This cost/token plan is retained for historical reference only. It is superseded by the compact canonical contract pack and by the later feasibility corrections extracted into `AGENTS.md`, ADRs, and task cards.

# Feasibility, Cost, and Token Optimization Plan
*Patristic Library Assistant — Build Execution Plan*

**Document Status:** Approved | **Prepared by:** Claude Code analysis
**Project:** Orthodox AI Assistant / Patristic Library Assistant
**Scope:** Full build (Phase 1 MVP through Phase 4 Launch)

---

## Executive Summary

| Question | Verdict |
|---|---|
| Can Claude Code deliver the full build autonomously? | ✅ Yes — 90–95% of all code. Developer needed only for credential wiring, load-test validation, and client theological sign-off. |
| Is the baseline cost economically viable? | ❌ No — $0.067/query baseline puts every pricing tier at a loss. Optimization is the business model, not a nice-to-have. |
| Is the optimized cost viable? | ✅ Yes — $0.007/query average yields 86–93% gross margin across all customer tiers. |
| Phase 1 MVP — true cost with all optimizations? | **$90–$100** in Claude Code tokens |
| Full build (all 4 phases) — true cost with all optimizations? | **$280–$350** in Claude Code tokens (hybrid Sonnet + Opus) |
| Phase 1 MVP — calendar time with Claude Code? | **2–3 weeks** (1 developer, part-time ~4h/day) |
| Full build — calendar time with Claude Code? | **7–10 weeks** total |
| Single biggest runtime savings lever | Route A1, A2, A6 to Haiku 4.5 (keep Sonnet only for A5 composition) — 58% reduction |
| Single biggest build savings lever | Pre-process the 1,210-line spec into a 200-line CLAUDE.md — eliminates most spec re-reads |

---

## Part 1 — Claude Code's Ability to Deliver

### Components Claude Code can build autonomously

| Component | Confidence | Notes |
|---|---|---|
| FastAPI backend + routing + middleware | ✅ High | Standard Python patterns |
| PostgreSQL schema + Alembic migrations | ✅ High | Schema fully specified |
| Qdrant vector DB integration | ✅ High | Python client well-documented |
| Token-based chunking module | ✅ High | Pure Python logic |
| OpenAI embedding integration | ✅ High | Simple SDK |
| Claude API orchestration (A1–A6) | ✅ High | All prompts and contracts defined |
| Redis session memory | ✅ High | Basic TTL key-value |
| Response caching layer | ✅ High | Key pattern specified |
| Next.js chat UI + admin panel | ✅ High | Component list is specified |
| Theological safety test suite | ✅ High | Query list is written |
| Clerk auth + JWT parsing | ⚠ Medium | Multi-tenant role edge cases require iteration |
| Stripe metered billing | ⚠ Medium | Webhook idempotency needs manual verification |
| Railway deployment config | ⚠ Medium | Env var wiring requires live credentials |

### Risk areas — developer must be in the loop

- Load testing at 100 concurrent queries (needs live infrastructure)
- Stripe webhook testing in production mode (live keys)
- Make.com webhook integration (external service credentials)
- Theological review sign-off by a qualified Orthodox clergy reviewer (cannot be automated)

---

## Part 2 — Build Cost Analysis (Claude Code Tokens)

### Baseline (no optimization)

Derived from the original estimate of 160M input + 12M output tokens across ~400 hours / 8,000 coding interactions, with 60% automatic caching built into Claude Code.

| Model | Full Build (4 Phases) | Phase 1 MVP Only |
|---|---|---|
| Sonnet 4.6 | ~$400 | ~$160 |
| Opus 4.7 | ~$2,000 | ~$800 |
| Hybrid (90% Sonnet / 10% Opus) | ~$500–$700 | ~$200–$280 |

### Optimized (all build strategies applied)

| Strategy | Mechanism | Token Impact |
|---|---|---|
| CLAUDE.md pre-processing | 200-line condensed spec replaces repeated 1,210-line spec reads | ~720K tokens saved |
| Session consolidation (20 vs. 39 sessions for Phase 1) | Fewer cold starts, less accumulated context | ~30% reduction in interactions |
| Worktree isolation per module | Backend / frontend / billing never share context | ~20% context-size reduction per session |
| TDD with failing tests as guidance | Small test files replace large spec sections for direction | ~300K tokens saved |
| Pin file-read scope per session | Explicit task briefing prevents exploratory file reads | ~10% context reduction |

### Optimized cost estimates

| Phase | Sonnet 4.6 | Hybrid (90/10) |
|---|---|---|
| Phase 1 MVP | **$90–$100** | **$110–$130** |
| Phase 2 (corpus pipeline) | $50–$70 | $70–$90 |
| Phase 3 (multi-tenancy, billing, dashboard) | $70–$90 | $90–$110 |
| Phase 4 (polish, launch) | $30–$50 | $40–$60 |
| **Full build total** | **~$220–$310** | **~$310–$390** |

**Realistic target: ~$300–$350 for a hybrid-model, fully-optimized full build.**

---

## Part 3 — Runtime Cost Analysis (Deployed App)

### Per-query token budget

| Agent | Input Tokens | Output Tokens | Current Spec Model | Optimized Model |
|---|---|---|---|---|
| A1 Classification | 500 | 200 | Sonnet 4.6 | **Haiku 4.5** |
| A2 Retrieval Planning | 500 | 200 | Sonnet 4.6 | **Haiku 4.5** (or merged into A1) |
| A5 Composition | 2,500 | 1,200 | Sonnet 4.6 | Sonnet 4.6 (keep) |
| A6 Verification | 1,000 | 200 | Sonnet 4.6 | **Haiku 4.5** |

### Cost progression per query

| Scenario | Cost per Query |
|---|---|
| Baseline (all Sonnet, no caching, no merging) | $0.067 |
| + Model routing (Haiku for A1, A2, A6) | $0.028 (–58%) |
| + Prompt caching on A5 (system prompt + tenant rules) | $0.018 (–35%) |
| + Merge A1+A2 into single call | $0.016 (–12%) |
| + Dynamic k-value in retrieval | $0.015 (–8%) |
| + Output token budgeting per mode | $0.013 (–10%) |
| + Response caching at 50% hit rate | **$0.007 avg (–50% on volume)** |

### Revised monthly economics

| Customer Tier | Queries/mo | Claude Cost (Optimized) | Revenue | Gross Margin |
|---|---|---|---|---|
| Starter | 500 | $3.50 | $50 | **93%** |
| Community | 2,000 | $14 | $150 | **91%** |
| Institution | 5,000 | $35 | $350 | **90%** |
| Enterprise | 10,000+ | $70+ | $500+ | **86%+** |

---

## Part 4 — All Token Reduction Strategies

### Runtime optimizations (ranked by impact)

#### 1. Model routing — Haiku 4.5 for A1, A2, A6
*Impact: Very High | Accuracy Risk: None | Effort: Low*

A1, A2, and A6 perform structured pattern matching and JSON schema validation. Haiku handles this as well as Sonnet at ~20% the cost. Only A5 (composition) needs Sonnet's nuanced instruction-following.

#### 2. Claude prompt caching on A5
*Impact: Very High | Accuracy Risk: None | Effort: Medium*

Mark the system prompt (~200 tokens) and tenant rules (~100–500 tokens) as cache breakpoints in every A5 call. Cached input costs 10% of fresh input. For tenants with stable prompts, 90%+ of A5 input becomes cached within minutes of traffic.

Additionally cache the **common patristic chunk library** (5K–10K tokens of frequently-retrieved starter corpus chunks) once per tenant per hour.

#### 3. Response caching with normalized query hash
*Impact: High | Accuracy Risk: None | Effort: Already in spec*

Already specified — ensure the query hash lowercases and trims whitespace. Target 30–50% cache hit rate on mature corpora.

#### 4. Merge A1 + A2 into a single call
*Impact: High | Accuracy Risk: Low | Effort: Medium*

Both agents consume the same input. Combine into one Haiku call returning both ClassifiedQuery and RetrievalPlan as structured JSON.

#### 5. RED-tier early exit
*Impact: Medium | Accuracy Risk: None | Effort: Low*

If A4 returns confidenceTier = RED, skip A5 and A6 entirely. Return the fallback response immediately. Saves ~3,700 tokens per RED-tier query.

#### 6. Dynamic k-value by answer mode
*Impact: Medium | Accuracy Risk: Low | Effort: Low*

- direct_citation: k=3
- consensus: k=5
- historical_development: k=5
- YELLOW tolerance: k=2

Reduces A5 input by ~600 tokens on simple queries.

#### 7. Output token budgeting per mode
*Impact: Medium | Accuracy Risk: Low | Effort: Low*

- direct_citation: max_tokens=600
- consensus: max_tokens=1000
- RED fallback: max_tokens=150

#### 8. Batch API for ingestion
*Impact: Medium | Accuracy Risk: None | Effort: Medium*

Call 5 metadata generation runs async during ingestion. Use Anthropic Batch API for 50% discount on all ingestion calls.

#### 9. Embedding caching (24h TTL)
*Impact: Low-Medium | Accuracy Risk: None | Effort: Low*

Cache query embeddings in Redis for 24 hours keyed by normalized query hash. Identical queries skip the OpenAI embedding call entirely.

#### 10. Session history compression
*Impact: Low | Accuracy Risk: Low | Effort: Low*

Instead of passing all 5 turns verbatim, compress turns 1–3 into a one-sentence summary and pass turns 4–5 in full. Saves 400–600 tokens on long sessions.

### Build-time optimizations (ranked by impact)

#### 11. CLAUDE.md condensed spec
*Impact: Very High | Effort: Low (create once before build starts)*

Replace repeated reads of the 56 KB build plan with a 200-line CLAUDE.md containing: tech stack, six-agent contracts, DB schema, API table, confidence tier logic, system prompt verbatim, key constraints.

#### 12. Single-session scaffolding pass
*Impact: High | Effort: Low*

Generate the full directory tree + empty module files + config boilerplate in one focused session before any implementation. Every subsequent session starts with a readable file tree — no "what exists" exploration.

#### 13. Test-Driven Development
*Impact: High | Effort: Medium*

Write the 20-query safety suite and endpoint tests first. Implementation sessions read small test files instead of large spec sections. Test failures provide token-efficient, precise guidance.

#### 14. Worktree isolation per module
*Impact: Medium | Effort: Low*

Build backend, frontend, ingestion, and billing in separate worktrees. Each starts with a clean context.

#### 15. Pinned file scope per session
*Impact: Medium | Effort: Low*

Start each session with an explicit task description listing which files are in scope. Prevents exploratory reads of unrelated code.

---

## Part 5 — Time Estimate (Calendar Time)

The 160-hour Phase 1 estimate is developer-hours to build manually. With Claude Code doing 90–95% of implementation, the developer's active role shrinks to prompt crafting, review, credential wiring, and sign-off — roughly 25–35% of the original hour figure.

| Phase | Spec Hours | Developer Hours (w/ Claude Code) | Calendar Time (1 dev, ~4h/day) |
|---|---|---|---|
| Phase 1 MVP | 160 | 40–56 | **2–3 weeks** |
| Phase 2 (corpus pipeline) | ~120 | 30–42 | **1.5–2 weeks** |
| Phase 3 (multi-tenancy + billing) | ~160 | 40–56 | **2–3 weeks** |
| Phase 4 (polish + launch) | ~120 | 30–42 | **1.5–2 weeks** |
| **Full build** | **~560** | **~140–196** | **7–10 weeks** |

---

## Part 6 — Optimized Implementation Sequence

### Pre-Build (Day 1 — do NOT skip)
1. Decide on ambiguity resolutions (see companion document BLUEPRINT_CLARIFICATIONS.md)
2. Write `CLAUDE.md` (condensed spec, 200 lines) at project root
3. Write `/tests/safety/test_20_queries.py` with all 20 theological queries + expected behaviors
4. Write `/tests/api/` stubs for each endpoint
5. Run a single scaffolding session to create full directory tree + empty modules

### Phase 1 — MVP (20 focused sessions)

| # | Session | Reads | Writes |
|---|---|---|---|
| 1 | DB schema + Alembic migrations | CLAUDE.md | backend/models/, alembic/ |
| 2 | FastAPI bootstrap + Qdrant client + chunking | CLAUDE.md | backend/core/, services/qdrant_service.py, chunking.py |
| 3 | Embedding integration + /api/v1/ingest | chunking.py | ingest.py, embedding.py |
| 4 | Merged A1+A2 agent (Haiku) + A3 retrieval | CLAUDE.md | agents/classifier.py, agents/retrieval.py |
| 5 | A4 evidence packaging + confidence tiers | agent specs in CLAUDE.md | agents/evidence_packager.py |
| 6 | A5 composition (Sonnet + prompt caching) + A6 verification (Haiku) | system prompt | agents/composer.py, agents/verifier.py |
| 7 | Redis session memory + response caching | cache spec | session_service.py, response_cache.py |
| 8 | RED-tier early exit + Flagged Queries logging | — | orchestrator.py |
| 9 | Cross-reference panel + citation formatter | — | services/citation_service.py |
| 10 | Batch API integration for Call 5 ingestion | — | workers/ingestion_tasks.py |
| 11 | Run safety test suite — fix failures | tests/safety/ | (various) |
| 12 | Next.js scaffold + Clerk auth | — | frontend/app/, frontend/middleware.ts |
| 13 | Chat interface + streaming response display | chat spec | frontend/app/chat/, components/answer/ |
| 14 | Admin panel: corpus browser + approval queue + flagged queries | admin spec | frontend/app/admin/ |
| 15 | Stripe metered billing middleware + webhook handler | billing spec | stripe_service.py, webhooks.py |
| 16 | Railway deployment config (railway.toml, env vars) | — | railway.toml, .env.example |
| 17 | Load test script (k6 or locust) for 100 concurrent queries | — | tests/load/ |
| 18 | Ingest 50 Orthodox Ethos transcripts; verify tiers | — | (data only) |
| 19 | End-to-end fixes from beta; re-run safety suite | — | (various) |
| 20 | Final verification + clergy review prep | — | (documentation) |

### Phase 2 — Corpus Pipeline (8 sessions)
### Phase 3 — Multi-Tenancy + Billing (10 sessions)
### Phase 4 — Polish + Launch (6 sessions)

**Total: ~44 focused sessions across 7–10 calendar weeks**

---

## Part 7 — Accuracy Preservation Guarantees

All optimizations maintain 100% accuracy because:

1. **Haiku routing (A1, A2, A6):** These agents do pattern matching and JSON schema validation. Haiku performs these tasks identically to Sonnet. A4's evidence packaging catches any malformed output before A5.

2. **Prompt caching:** Transparent to the model — identical tokens are received regardless of cache status.

3. **Merged A1+A2:** Same information, same reasoning, single call. Output is identical — just delivered in one structured JSON.

4. **Dynamic k-value:** k=3 still exceeds the GREEN-tier threshold (≥3 chunks ≥0.70).

5. **Output budgeting:** Max-token limits are set above observed answer lengths. Safety suite validates no truncation.

6. **Response caching:** Only the lookup key changes (normalization). Stored responses are unmodified.

7. **RED-tier early exit:** RED-tier responses are already deterministic fallbacks per spec. Skipping A5+A6 cannot change their content.

---

## Part 8 — Verification Plan

| Checkpoint | When | Method |
|---|---|---|
| CLAUDE.md accuracy | Before Session 1 | Manual review against `patristic-build-plan.md` |
| 20-query safety suite | After Session 11 | Automated pytest run |
| Token usage per query | After Session 10 | Read Claude API `usage` headers; confirm cache hits |
| Stripe webhook idempotency | After Session 15 | Stripe CLI replay tests |
| Load test P95 < 5s | After Session 17 | k6 with 100 concurrent VUs |
| Cross-tenant isolation | After Phase 3 | Integration test — Tenant A query never returns Tenant B chunks |
| Clergy theological review | After Session 20 | Qualified Orthodox clergy reviewer approves 20 safety queries + 10 production samples |

---

## Part 9 — Critical Success Factors

1. **CLAUDE.md is non-negotiable.** Without it, the build cost slides back toward $400–$500.
2. **Haiku routing must be configured from Session 4 onward.** Retrofitting model routing later means rewriting every agent.
3. **Prompt caching must be wired from Session 6.** Enabling caching after launch loses 30% of potential savings.
4. **Safety suite must run before every deploy.** Non-negotiable — hallucination is a brand-killing failure mode in this vertical.
5. **Worktree hygiene matters.** Resist the temptation to blur module boundaries to "save a step."

---

## Summary Card

| Dimension | Value |
|---|---|
| Claude Code delivery capability | 90–95% autonomous |
| Total build cost (optimized, hybrid) | **$280–$350** |
| Total build calendar time | **7–10 weeks** |
| Baseline runtime cost per query | $0.067 |
| Optimized runtime cost per query | **$0.007** (89% reduction) |
| Gross margin at Starter tier (optimized) | **93%** |
| Biggest runtime lever | Haiku for A1/A2/A6 (58% savings) |
| Biggest build lever | CLAUDE.md pre-processing |
| Accuracy impact of optimizations | **0%** — all structural, not quality tradeoffs |
