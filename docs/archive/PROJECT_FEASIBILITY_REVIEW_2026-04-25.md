# Archived: Decisions Extracted To Canonical Contracts

This review is retained for traceability. Its approved implementation decisions have been extracted into `AGENTS.md`, `docs/contracts/`, `docs/adr/`, schemas, task cards, fixtures, and tests. Use canonical files for normal coding.

# Project Feasibility Review and Token Reduction Plan

Date: 2026-04-25
Project: Orthodox AI Assistant / Patristic Library Assistant
Reviewed files:
- `patristic-build-plan.md`
- `FEASIBILITY_AND_TOKEN_PLAN.md`
- `BLUEPRINT_CLARIFICATIONS.md`

## 1. Executive Verdict

The project is feasible, but not as a fully autonomous build with no expert human oversight.

Best interpretation:
- A skilled AI coding agent can implement a large share of the codebase.
- A human still needs to own architecture decisions, credentials, production rollout, data governance, clergy/theological review, and final safety sign-off.
- The MVP is feasible for a solo technical founder using an AI coding agent.
- The full SaaS product is feasible, but the current 7-10 week full-build estimate is optimistic if "production launch" includes billing correctness, tenant isolation, security review, corpus QA, clergy review, and real customer onboarding.

Recommended planning numbers:

| Scope | Feasibility | AI-deliverable code | Human skill required | Realistic calendar |
|---|---:|---:|---|---:|
| Phase 1 prototype | High | 80-90% | Mid/senior full-stack with RAG basics | 3-6 weeks |
| Phase 1 production MVP | High, with discipline | 70-85% | Senior backend/RAG plus frontend comfort | 6-10 weeks |
| Full multi-tenant SaaS | Medium-high | 55-75% | Senior full-stack, SaaS billing, DevOps, security, QA | 12-24 weeks |
| Institution-grade product | Medium | 40-60% | Product, compliance, theological governance, partnerships | 6-12+ months |

The existing `FEASIBILITY_AND_TOKEN_PLAN.md` is useful, but it should be treated as a best-case execution plan, not a reliable budget guarantee.

## 2. Important Cost Corrections

The current token plan uses the right categories but overstates some savings.

### 2.1 Current Claude API prices checked

Official Claude pricing checked on 2026-04-25:
- Claude Sonnet 4.6: $3 / MTok input, $15 / MTok output.
- Claude Haiku 4.5: $1 / MTok input, $5 / MTok output.
- Claude Opus 4.7: $5 / MTok input, $25 / MTok output.
- Prompt cache reads cost 0.1x base input price.
- Batch processing gives a 50% discount on input and output tokens.
- Opus 4.7 may use up to 35% more tokens for the same fixed text because of its tokenizer.

### 2.2 Existing runtime baseline looks high

Using the plan's own per-query budget:

| Agent | Tokens | All Sonnet cost |
|---|---:|---:|
| A1 | 500 in / 200 out | $0.0045 |
| A2 | 500 in / 200 out | $0.0045 |
| A5 | 2500 in / 1200 out | $0.0255 |
| A6 | 1000 in / 200 out | $0.0060 |
| Total | 4500 in / 1800 out | about $0.0405 |

The existing plan states $0.067/query as baseline. That may include extra retries, tool schema overhead, hidden prompts, or larger evidence packets, but it is not explained by the visible budget alone.

### 2.3 Haiku routing savings are real but not 58% by itself

If A1, A2, and A6 move to Haiku while A5 stays Sonnet:

| Agent | Optimized model | Cost |
|---|---|---:|
| A1 | Haiku 4.5 | $0.0015 |
| A2 | Haiku 4.5 | $0.0015 |
| A5 | Sonnet 4.6 | $0.0255 |
| A6 | Haiku 4.5 | $0.0020 |
| Total | Mixed | about $0.0305 |

That is about 25% lower than the visible all-Sonnet baseline. It is still worth doing, but A5 dominates the bill.

### 2.4 Realistic optimized per-query target

The current `$0.007/query` estimate is achievable only as a best-case average with strong response caching, shorter outputs, RED early exits, and high repeat traffic.

More realistic planning target:

| Scenario | Expected LLM cost/query |
|---|---:|
| Unoptimized visible baseline | about $0.040 |
| Model routing only | about $0.030 |
| Model routing + A1/A2 merge + deterministic A6 prechecks | about $0.026-$0.029 |
| Add evidence trimming + output budgets | about $0.017-$0.024 |
| Add 30% response cache hit rate | about $0.012-$0.017 |
| Add 50% response cache hit rate | about $0.009-$0.012 |

Recommendation: use `$0.015/query` as the business-plan default, `$0.010/query` as the strong-optimization goal, and `$0.007/query` as upside rather than baseline.

### 2.5 Build-token cost correction

The existing build-cost estimate can remain as a target, but the assumptions need to be explicit.

If the original estimate is 160M input tokens and 12M output tokens, and 60% of input is cached:

| Build model mix | Approx API-equivalent cost |
|---|---:|
| All Sonnet 4.6 | about $401 |
| 90% Sonnet / 10% Opus 4.7 | about $428 |
| All Opus 4.7 | about $668, before tokenizer overhead |

The previous "all Opus about $2,000" is too high for current Opus 4.7 pricing, unless it assumes older Opus prices, less caching, or much higher token use.

Optimized full-build target:
- Best case: $220-$350 API-equivalent coding tokens.
- Safer budget: $400-$700 including rework, failed tests, deployment debugging, and documentation.
- If using a subscription product rather than raw API billing, track actual token usage separately; subscription cost and API-equivalent cost will not match perfectly.

## 3. Token Reduction Strategy Without Sacrificing Accuracy

Important caveat: "100% accuracy" is not technically guaranteeable for a generated theological answer. What can be guaranteed is stricter:
- No answer claims without approved source support.
- No fabricated citations.
- No personal pastoral, medical, or political advice.
- Fail closed when source support is insufficient.
- Every production release passes a regression suite and clergy review gates.

That is the right standard for this product.

### 3.1 Runtime reductions

Use these in priority order:

| Strategy | Accuracy impact | Notes |
|---|---|---|
| Keep A5 as the only main generative call | Positive | Make A1/A2/A4/A6 mostly structured/deterministic. |
| Merge A1 and A2 logically | Low risk | Return `ClassifiedQuery` and `RetrievalPlan` from one Haiku call. Keep separate trace records. |
| Make A4 deterministic | Positive | Evidence filtering, policy checks, thresholds, and allowed chunks should be code, not LLM reasoning. |
| Make A6 level 1 and 2 deterministic | Positive | Citation ID existence and quote-overlap checks should run before any verifier LLM. |
| Use Haiku 4.5 for A1/A2/A6 level 3 | Low risk if tested | These are structured tasks; gate with schemas and tests. |
| Use Sonnet 4.6, not Opus, for normal A5 | Low risk | Escalate to Opus only for explicitly marked complex scholarly or conflict cases. |
| Avoid Opus 4.7 by default | Positive for cost | Current Claude docs warn its tokenizer can use up to 35% more tokens for the same text. |
| Prompt-cache only stable blocks | Neutral | Cache system prompt, tenant policy, answer schemas. Do not add large common libraries to every prompt unless retrieval selected them. |
| Do not cache dynamic evidence blindly | Positive | Caching irrelevant "common chunks" can increase cost and hurt closed-corpus discipline. |
| Response cache with full invalidation key | Neutral | Key must include tenant, normalized query, corpus version, prompt version, answer mode, sensitivity, user role, and session hash when applicable. |
| Cache only standalone questions by default | Positive | Follow-up questions depend on session context and should not share a cache key with standalone queries. |
| Embed-query cache | Neutral | Cheap but simple. Key by normalized query plus language. |
| RED early exit before A5 | Positive | If no approved evidence, return deterministic RED and log gap. |
| Sensitive hard-block early exit | Positive | Political/medical/pastoral advice requests should not burn A5 tokens unless reframed to a teaching query with evidence. |
| Retrieve broad, compose narrow | Positive | Pull candidate_k 12-20, dedupe/rerank, pass only the minimum exact spans to A5. |
| Use MMR or diversity reranking | Positive | Reduces redundant chunks and wasted context. |
| Pass quote spans, not entire large chunks | Medium risk if too aggressive | Include enough surrounding context for meaning; keep source IDs for verifier. |
| Dynamic answer budgets | Low risk if tested | Direct citation 300-600 tokens, RED 80-150, consensus 800-1200, scholarly 1200-1800. |
| Mode-specific evidence budgets | Positive | Direct citation needs fewer chunks than consensus or historical development. |
| Force structured outputs | Positive | Reduces retries and frontend ambiguity. |
| Cap regenerate attempts at 1 | Positive | After second failure, fail closed. |
| Avoid tool schemas in model calls unless needed | Neutral | Claude tool use adds extra input tokens. JSON mode / schema validation may be cheaper. |
| Batch all ingestion metadata | Neutral | Use Anthropic batch for Call 5 and OpenAI Batch for embeddings where latency does not matter. |
| Precompute metadata offline | Positive | Categories, fathers, summaries, citation candidates, source hashes belong in ingestion, not query-time. |
| Precompute lexical/BM25 index | Positive | Helps retrieval without LLM tokens. |
| Store source and prompt version IDs | Positive | Enables exact cache invalidation and reproducibility. |
| Compress session memory | Medium risk | Summarize older turns, but keep the last 1-2 turns verbatim and never summarize citations as if they were sources. |
| Use deterministic forbidden-phrase filter | Positive | Especially for pastoral contexts: block "you should", "you must", "in your case", etc. |
| Track token telemetry per agent | Positive | Without per-agent cost data, optimization becomes guesswork. |

### 3.2 Build-time reductions

Use these before any coding begins:

| Strategy | Why it saves tokens |
|---|---|
| Create a canonical `CLAUDE.md` / `AGENTS.md` | Prevents repeated reads of 50K+ word planning docs. |
| Freeze blueprint decisions in ADRs | Stops the agent from re-litigating architecture in every session. |
| Convert PDFs to markdown once | Never ask the agent to re-read PDFs for implementation context. |
| Build an implementation task deck | One task card per session: goal, files in scope, acceptance tests, forbidden scope. |
| Generate OpenAPI and Pydantic/TS schemas first | Lets backend and frontend work against stable contracts. |
| Scaffold once | Future sessions read small files instead of asking "what exists?" |
| Write safety tests before agents | Tests become concise executable requirements. |
| Write endpoint tests before UI | Reduces exploratory backend/frontend integration debugging. |
| Keep sessions module-scoped | Backend agents, frontend UI, billing, ingestion, and DevOps should not share large context. |
| Maintain a file map | Short `docs/file_map.md` is cheaper than repeated tree scans. |
| Maintain a decision log | Short `docs/decisions.md` prevents repeated explanation. |
| Use generated types | Avoid repeated manual sync between Pydantic and TypeScript. |
| Use small fixtures | Let tests reference fixtures instead of embedding huge source passages in prompts. |
| Use local test failures as feedback | A 30-line traceback is cheaper than re-reading the spec. |
| Do not use Opus for routine implementation | Reserve expensive models for architecture review, security review, and ambiguous failures. |
| Avoid broad "review entire codebase" sessions | Ask for targeted reviews by module and risk area. |
| Keep a build ledger | Track tokens, time, changed files, and blockers per session. |
| Minimize aesthetic churn in frontend | Lock design system early; avoid repeated UI redesigns. |
| Prefer boring libraries | FastAPI, SQLAlchemy, Alembic, Qdrant client, Redis, Clerk, Stripe. Novel abstractions burn tokens. |
| Gate each phase with tests and docs | Avoid late broad rewrites. |

## 4. Blueprint Changes I Recommend

### 4.1 Reframe "100% accuracy"

Replace "No hallucination. No outside knowledge." with an operational contract:

1. Every factual/theological paragraph must cite at least one approved chunk.
2. Every direct quote must pass exact or near-exact source overlap.
3. Every claim must be traceable to a chunk ID in the evidence packet.
4. If evidence is insufficient, the system returns RED or YELLOW; it does not fill gaps from model training.
5. The model may use general language ability for wording, but not uncited theological facts.

This makes accuracy testable instead of aspirational.

### 4.2 Split confidence from handling

Do not use `SENSITIVE` as a confidence tier. It is a handling flag.

Recommended shape:

```text
confidence_tier: GREEN | YELLOW | RED
sensitivity: normal | pastoral_advice | political | medical | comparative_religion | canonical_dispute | other_sensitive
handling: answer | reframe | block | redirect | escalate
```

This avoids mixing "do we have enough evidence?" with "is this user asking for risky advice?"

### 4.3 Build multi-tenant foundations on day 1

Even if MVP has one tenant, every table, Qdrant payload, cache key, log event, and storage path should include `tenant_id`.

This is cheaper than refactoring single-tenant assumptions later and is essential for closed-corpus isolation.

### 4.4 Treat A1+A2 as one physical call, two logical steps

Recommended implementation:
- `QueryAnalyzer` returns `ClassifiedQuery` and `RetrievalPlan`.
- Trace logs still show A1 and A2 outputs separately.
- Later, A2 can be split back into its own agent if retrieval complexity requires it.

This reduces tokens without making the architecture ambiguous.

### 4.5 Make A4 code-only in MVP

A4 should not be an LLM in Phase 1. It should:
- Filter approved chunks.
- Apply tenant, role, policy, language, and source-status rules.
- Calculate confidence tier.
- Produce `EvidencePacket`.
- Return retrieval explanations for admins.

### 4.6 Define cache invalidation now

Every cached answer must be invalidated when any of these changes:
- Corpus source approval/rejection.
- Chunk content.
- Prompt version.
- Tenant policy.
- Answer schema version.
- Model version if regression suite is not yet passed.
- User role or scholarly mode.
- Session context for follow-ups.

Without this, response caching can silently preserve wrong or outdated answers.

### 4.7 Do not stream unverified final text

If A6 verification can reject or downgrade output, the UX must avoid showing unverified prose as final.

Recommended:
- Stream retrieval/progress states.
- Generate A5 internally.
- Run A6.
- Stream the verified answer, or stream draft text clearly labeled as "verifying" and replace only after approval.

For this product, verified-late is safer than fast-but-retracted.

### 4.8 Add privacy handling for sensitive logs

Pastoral, medical, and political queries may contain highly sensitive user data.

Add:
- `sensitive_log_redacted` field.
- Raw query retention window.
- Tenant-level retention setting.
- Admin access audit for raw sensitive queries.

### 4.9 Add corpus versioning

Add a `corpus_versions` table or tenant-level `corpus_revision` counter.

Every query response should store:
- `corpus_revision`
- `prompt_version`
- `model_versions`
- `retrieval_config_version`
- `answer_schema_version`

This is required for reproducibility, cache safety, and theological audit.

### 4.10 Add acceptance criteria per answer mode

Each answer mode should have:
- Required evidence count.
- Required fields.
- Max output tokens.
- Citation style.
- Failure behavior.
- Whether divergences must be shown.

This makes A5 cheaper and easier to validate.

### 4.11 Treat PAG-RAG as a phased lineage layer, not the MVP core

The graph-RAG direction is a good fit for this product, especially for patristic lineage, doctrinal development, translation variants, and scholarly dispute handling. But it should not replace the Phase 1 vector-first MVP.

Recommended implementation:
- Keep Qdrant/vector retrieval as the MVP search path.
- Add PostgreSQL graph tables for `graph_entities`, `chunk_entity_mentions`, and `lineage_edges`.
- Allow ingestion to create candidate edges, but require reviewer approval before an edge affects user answers.
- Let A2 request graph expansion only for graph-sensitive answer modes.
- Let A4 admit only approved graph edges into the evidence packet.
- Require A6 to verify every lineage claim against approved edge IDs.

Important wording correction: do not claim "deterministic lineage" from LLM-extracted graph data. The safer and more accurate claim is "deterministic handling of validated lineage metadata."

## 5. Skill Feasibility

### Can an AI coding agent deliver this on its own?

No, not responsibly. It can produce most code, but it cannot own:
- Theological authority.
- Source approval.
- Production secrets and provider accounts.
- Legal/compliance decisions.
- Customer discovery and onboarding.
- Final security assurance.
- Billing correctness in live Stripe.

### Can a solo technical founder deliver it with an AI coding agent?

Yes, if the founder can:
- Read and modify Python/FastAPI code.
- Debug TypeScript/Next.js build issues.
- Understand Postgres schemas and migrations.
- Test Clerk and Stripe webhooks.
- Interpret RAG failures.
- Run load tests and inspect logs.
- Maintain discipline around safety tests and source governance.

### Minimum human help I would budget

| Role | Need |
|---|---|
| Senior backend/RAG reviewer | Part-time for architecture and safety gates. |
| Orthodox clergy/theological reviewer | Required before real users. |
| DevOps/security reviewer | Recommended before paid production. |
| UX/product reviewer | Helpful, especially for admin workflows and sensitive reframing UX. |

## 6. Revised Implementation Sequence

Pre-build:
1. Approve blueprint clarifications.
2. Create `CLAUDE.md` / `AGENTS.md`.
3. Create ADRs for closed-corpus contract, confidence-vs-sensitivity, cache invalidation, and multi-tenancy.
4. Create Pydantic schemas and OpenAPI first.
5. Create 20-query safety suite and small corpus fixtures.
6. Scaffold backend, frontend, tests, and docs.

Phase 1:
1. Database schema with tenant_id everywhere.
2. Ingestion pipeline with source hash, chunk hash, approval status, and corpus revision.
3. Embeddings and Qdrant retrieval.
4. Query analyzer: combined A1/A2 with structured output.
5. Deterministic A4 evidence packet.
6. A5 composer with strict mode-specific schema.
7. A6 deterministic checks plus optional Haiku consistency judge.
8. RED/SENSITIVE early exits.
9. Admin corpus approval and query log.
10. Chat UI with citation panel and reframing disclosure.
11. Response cache with safe invalidation.
12. CI safety gate.

Phase 2:
1. Batch ingestion and progress tracking.
2. YouTube/transcript pipeline.
3. Liturgical service.
4. Query gap clustering.
5. Widget only after core chat is stable.

Phase 3:
1. Clerk org-to-tenant provisioning.
2. Stripe billing and idempotent webhooks.
3. System prompt versioning.
4. Tenant cost dashboard.
5. Policy/governance layer.

Phase 4:
1. Launch hardening.
2. Load testing.
3. Monitoring.
4. Documentation.
5. First customer onboarding.

## 7. Clarifying Questions

The main decisions I would lock before coding:

1. Is "Orthodox Ethos" the only Phase 1 tenant, or should Phase 1 expose multi-tenant admin UX even if there is one tenant?
2. Who is the named theological reviewer for the 20-query safety suite?
3. Will Phase 1 answers be public-facing or only internal/private beta?
4. Are raw sensitive queries allowed to be stored, and for how long?
5. Is the project committed to Claude for A5, or should we build a provider interface that can test GPT models later?
6. Do you need EU-only data processing at launch, or can that wait?
7. Should cached answers count toward customer usage/billing? Current plan says no, but that affects revenue and abuse behavior.
8. What is the minimum acceptable citation quality for launch: source-level, page/timestamp-level, or exact quote span?
9. Are generated study packets in scope for MVP, or should they wait until the normal Q&A path is stable?
10. Should tenants be allowed to edit prompts directly, or only choose from safe configurable policy fields?

## 8. Source Links Checked

- Claude pricing: https://platform.claude.com/docs/en/about-claude/pricing
- OpenAI `text-embedding-3-small`: https://developers.openai.com/api/docs/models/text-embedding-3-small
- OpenAI Batch API: https://developers.openai.com/api/docs/guides/batch
- Railway pricing: https://docs.railway.com/pricing
- Stripe Billing pricing: https://stripe.com/us/billing/pricing
- Stripe payments pricing: https://stripe.com/us/pricing
- Clerk pricing: https://clerk.com/pricing
- Qdrant pricing: https://qdrant.tech/pricing/

## 9. Decision Addendum From Founder Answers

Date: 2026-04-25

### Locked decisions

| Question | Decision |
|---|---|
| Phase 1 tenancy | Expose multi-tenant admin UX from day 1, even if only one tenant exists initially. |
| Theological reviewer | Founder is the initial theological reviewer. Add an external reviewer before public or paid launch if possible. |
| Launch audience | Internal/private beta. This lowers external risk but does not remove safety, privacy, or audit requirements. |
| EU-only processing | Can wait. Keep `data_region` architecture but do not make EU hosting a Phase 1 launch blocker. |
| Citation detail | Target the highest practical detail: exact quote span where possible, plus page/timestamp/source/chunk metadata. |

### Recommendations for open decisions

#### Sensitive query storage

Recommended default: store redacted sensitive logs by default, with tightly controlled short-term raw retention.

Implementation:
- Store `query_text_redacted` for all sensitive queries.
- Store raw `query_text` encrypted with a 30-day retention window during private beta.
- Add tenant setting later: `raw_sensitive_query_retention_days`.
- Restrict raw sensitive query viewing to admins only.
- Audit every raw sensitive query view.
- Never send raw sensitive logs to analytics tools.

Rationale: The product needs enough data to debug safety failures and improve corpus gaps, but pastoral and medical queries can contain deeply personal information. Redacted-by-default is the right posture.

#### Model provider strategy

Recommended default: build a provider interface from day 1, but certify only one production model path at a time.

Implementation:
- `LLMProvider` interface: `generate_structured`, `generate_text`, `stream_text`, `count_tokens`, `supports_prompt_cache`, `supports_batch`.
- Provider adapters: `AnthropicProvider`, `OpenAIProvider`.
- Model routing table per agent/mode.
- Golden evaluation set for every model swap.
- A model cannot be used in production unless it passes the closed-corpus safety suite.

Rationale: "Plug and play" is excellent for experimentation, but production theological behavior must be certified, not freely swapped.

#### Cached answer billing

Recommended default: cached answers count against included plan usage, but do not trigger overage charges until the tenant exceeds a separate fair-use/cache threshold.

Alternative simpler MVP default: cached answers count as normal billable queries.

Why: Users still receive product value from cached answers. Making cached answers completely free invites abuse and weakens revenue predictability. However, charging full overage for near-zero-cost cached answers can feel unfair if a parish has repeated common questions.

Practical policy:
- Internal metric: count every user-visible answer as `served_answer_count`.
- Cost metric: count every fresh model run as `billable_compute_count`.
- Stripe meter for MVP: `served_answer_count`.
- Customer-facing language: "Your plan includes N answered questions per month."
- Later premium policy: include generous cached-answer allowance or discount cached answers after plan limit.

#### Study packets

Recommended default: do not include generated study packets in the MVP. Build only the schema and workflow hooks needed to support them later.

MVP should prove:
- Ask a question.
- Retrieve approved evidence.
- Compose safe sourced answer.
- Verify citations.
- Log gaps.
- Admin approves content.

Study packets multiply the same safety problem across many generated sections. They are valuable, but they should wait until the answer pipeline is boringly reliable.

#### Tenant prompt editing

Recommended default: do not allow free-form tenant prompt editing in MVP.

Instead, provide safe configurable policy fields:
- Tone: `plain`, `pastoral`, `scholarly`.
- Default answer length.
- Allowed starter corpus.
- Jurisdiction/calendar style.
- Preferred citation style.
- Sensitive handling strictness.
- Approved disclaimer/footer text from templates.

Free-form prompt editing can arrive later through a versioned prompt editor with preview tests, rollback, and safety-suite gating.

Rationale: A tenant should not accidentally weaken the closed-corpus contract with a well-meaning prompt tweak.
