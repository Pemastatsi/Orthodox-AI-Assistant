# Book Retrieval Resource Estimate (5,000 and 150,000 books)

**Status:** Reference-only. Not a contract or ADR. Numbers are engineering estimates derived from the canonical architecture (AGENTS.md, ADR-0006, ADR-0009, ADR-0010, `chunking-contract.md`, `vector-store-interface.md`, `chunk.schema.json`).

Reference docs are superseded by canonical files when in conflict (`docs/reference/README.md`). If the chunking contract, embedding model, or vector store changes, this estimate must be recomputed.

---

## 1. Inputs from canonical docs

| Parameter | Value | Source |
|---|---|---|
| Embedding model | `openai:text-embedding-3-small` | AGENTS.md; ADR-0006 |
| Embedding dimension | 1536 | `chunk.schema.json` (`embeddingDimension`); ADR-0006 |
| Vector encoding | float32 (4 bytes/element) | OpenAI API default |
| Vector store | Qdrant (Docker on Railway) | ADR-0010 |
| HNSW params | `m=16`, `ef_construct=100`, cosine | `patristic-build-plan.md` §Qdrant schema |
| Chunk soft target | 800–1200 tokens | `chunking-contract.md`; ADR-0009 |
| Chunk hard cap | 1500 tokens | `chunking-contract.md`; ADR-0009 |
| Token encoder | `cl100k_base` (`tiktoken`) | ADR-0006 |
| Retrieval `top_k` | 5 | archive clarifications (Phase 1 baseline) |
| Vector search SLO | < 100 ms | `patristic-build-plan.md` |
| End-to-end p95 SLO | < 8 s (exit criterion #4) | `phase1-implementation-contract.md` |
| Phase 1 vector budget | < 100 K vectors | `patristic-build-plan.md`; ADR-0010 |
| Concurrency load target | 100 concurrent queries | sprint planning (build plan) |
| Relational DB | PostgreSQL (Railway managed) | AGENTS.md |
| Session/cache | Redis (Railway managed) | AGENTS.md |
| Cache TTL | 1 hour | AGENTS.md §Cache |
| Session TTL | 30 min, 5-turn memory | `patristic-build-plan.md` |

## 2. Derived assumptions (NOT in docs — stated explicitly)

The canonical docs do not specify an average book size. The estimates below depend on the following derived inputs. If the corpus profile differs, recompute.

| Assumption | Value | Justification |
|---|---|---|
| Avg pages per book | 250 | Mixed patristic corpus: Philokalia volumes (~600 pp) balanced by short homilies (~30 pp) |
| Avg words per page | 300 | Standard typeset trade-book density |
| Avg tokens per word | 1.3 | `cl100k_base` averages ~1.0–1.3 for English, ~1.4–1.7 for Polytonic Greek; mixed corpus → 1.3 |
| Avg tokens per book | **~100,000** | 250 × 300 × 1.3 ≈ 97,500 → round to 100K |
| Avg chunk size (target) | 1000 tokens | Midpoint of 800–1200 soft target |
| Avg chunks per book | **~100** | 100,000 ÷ 1000 |
| Avg payload text per chunk | ~4 KB | 1000 tokens × ~4 bytes/token (UTF-8 mixed Greek/English) |
| Avg source PDF size | 5 MB | Typical born-digital or 300-dpi scanned PDF |

**Sensitivity:** Final totals scale roughly linearly in `chunks_per_book`. If actual books average 60–150 chunks, multiply storage and ingest cost accordingly (0.6×–1.5×).

## 3. Per-chunk footprint

| Component | Bytes/chunk | Notes |
|---|---|---|
| Qdrant vector (float32) | 6,144 | 1536 × 4 bytes |
| Qdrant HNSW graph edges (`m=16`) | ~4,000–8,000 | Empirical: 0.5×–1.5× vector size for HNSW links |
| Qdrant payload (schema fields per `chunk.schema.json` + `patristic_chunks` payload list) | ~5,000–7,000 | `chunk_id`, `tenant_id`, `source_id`, `source_hash`, `chunk_hash`, `page_start`, `page_end`, `section_path`, `content_text` (~4 KB), `embedding_model_version`, etc. |
| **Qdrant total per chunk** | **~16–21 KB** | Without quantization |
| Qdrant w/ int8 scalar quantization | ~10–13 KB | Vector compresses 4× (~1.5 KB), graph ≈ unchanged |
| PostgreSQL `chunks` row + indexes | ~7–8 KB | text (~4 KB) + JSONB metadata + B-tree/GIN overhead |
| PostgreSQL `run_traces` / `audit_entries` (per query, amortized) | small | Not chunk-bound; sized by QPS |
| **Combined storage per chunk (Qdrant + PG)** | **~24–30 KB** | Working figure |

## 4. 5,000-book estimate

**Chunks:** 5,000 × 100 = **500,000 chunks**

> Note: 500K vectors already exceeds the documented Phase 1 sweet spot (< 100 K). HNSW continues to give sub-100 ms search up to several million vectors on a single well-resourced node, so Qdrant remains viable — but the docs flag this as the point where capacity should be re-validated, not assumed (ADR-0010, `patristic-build-plan.md` line 34).

### Storage

| Tier | Size | Notes |
|---|---|---|
| Qdrant (vectors + HNSW + payload) | **~10 GB** | 500K × ~20 KB |
| PostgreSQL (chunks, sources, metadata, indexes) | **~5–7 GB** | Includes `run_traces`, `audit_entries` for ~1M queries |
| Object storage (source PDFs) | **~25 GB** | 5,000 × 5 MB |
| Redis (sessions + 1-hour answer cache) | **~1–2 GB** | Working set, not capped |
| Logs / observability (1 yr retention, redacted) | **~5–10 GB** | structlog + metrics |
| Backups / snapshots (3× DB, weekly retention) | **~20–30 GB** | |
| **Total storage** | **~70–85 GB** | |

### Memory (RAM)

| Service | RAM | Notes |
|---|---|---|
| Qdrant | **6–8 GB** | HNSW must stay resident for <100 ms search. 500K × 6 KB raw + graph + payload cache |
| PostgreSQL | **4–6 GB** | `shared_buffers` ≈ 25 % of hot DB |
| Redis | **2 GB** | sessions + cache |
| FastAPI workers (4–8 uvicorn workers × ~500 MB–1 GB) | **4–8 GB** | Orchestration, mostly waiting on LLM/embedding APIs |
| Headroom + OS + sidecars | **4–6 GB** | |
| **Total RAM** | **~24–32 GB** across services | |

### CPU

| Service | vCPU | Notes |
|---|---|---|
| Qdrant | **2–4 vCPU** | HNSW at 500K is CPU-cheap (<10 ms/query); easily handles 100 QPS |
| FastAPI workers | **4–8 vCPU** | Mostly I/O-bound on Anthropic/OpenAI calls |
| PostgreSQL | **2–4 vCPU** | Trace writes + occasional analytic queries |
| Embedding/ingest workers (background) | **2–4 vCPU** | Only active during ingestion |
| **Total vCPU (serving)** | **~12–16 vCPU** | |

### Ingestion (one-time, 5K books)

- Parse: pdfplumber ~0.1 s/page; Tesseract 1–3 s/page (ADR-0008). Mixed corpus ≈ 1 s/page average.
  - 5,000 × 250 pages × 1 s ≈ **350 CPU-hours single-thread** → ~40–50 wall-hours with 8 parallel workers.
- Embeddings (OpenAI `text-embedding-3-small` @ $0.02 / 1 M tokens):
  - 5,000 × 100,000 = 500 M tokens → **~$10 one-time** (rate-limited; finishes in hours, not days).
- Net ingestion compute: doesn't change steady-state sizing; can run on the same nodes.

### Practical instance shape (Railway-style)

- **Qdrant:** 4 vCPU / 8 GB / 50 GB SSD (with margin for growth)
- **Postgres:** 4 vCPU / 8 GB / 50 GB SSD
- **Redis:** 1 vCPU / 2 GB
- **FastAPI:** 2–4 replicas × (2 vCPU / 2 GB) behind a load balancer
- **Object storage:** 50 GB blob (S3/R2-compatible)

### Monthly cost (5K books)

List prices as of model knowledge cutoff (Jan 2026). Cloud contracts typically include committed-use or startup discounts. Verify against current Railway / OpenAI / Anthropic pricing before procurement.

| Line item | Monthly | Basis |
|---|---|---|
| Qdrant container (Railway, 4 vCPU / 8 GB / 50 GB) | **$40–80** | Railway compute + storage list |
| Postgres (Railway managed, 4 vCPU / 8 GB / 50 GB) | **$50–100** | Railway Postgres tier |
| Redis (Railway managed, 2 GB) | **$10–20** | Railway Redis tier |
| FastAPI replicas (2–4 × 2 vCPU / 2 GB) | **$40–80** | Railway compute |
| Object storage (PDFs, ~25 GB on R2/S3) | **$1–5** | R2 $0.015/GB; S3 $0.023/GB |
| Bandwidth/egress (API JSON traffic) | **$5–20** | usage-dependent |
| Observability (Sentry/Grafana Cloud free tier or paid) | **$20–50** | Vendor list |
| **Fixed infra subtotal** | **~$170–355/mo** | |
| **One-time embedding cost** | **~$10** | 500 M tokens × $0.02/1M |

**Variable LLM cost per fresh query** (Anthropic list prices, snapshot):
- A1+A2 (`claude-sonnet-4-6`, ~1 K in / 200 out): **~$0.006**
- A5 Composer (`claude-opus-4-7`, ~5 K in / 500 out): **~$0.11**
- **Per fresh answer: ~$0.10–0.12.** Cached answers (1-hour TTL per AGENTS.md): ~$0.

Monthly LLM spend at different query volumes (assuming 30 % cache hit rate after warm-up):

| Fresh queries/mo | Monthly LLM cost | Notes |
|---|---|---|
| 500 | ~$60 | Early beta / internal use |
| 2,000 | ~$240 | First paying tenant (Starter/Community tier) |
| 10,000 | ~$1,200 | Multiple tenants warming up |

**Total monthly all-in (5 K-book corpus, ~2 K fresh queries/mo):** **~$400–600/month** + variable LLM cost above.

---

## 5. 150,000-book estimate (30× scale)

**Chunks:** 150,000 × 100 = **15,000,000 chunks**

> **Architectural break point.** This is ~150× the documented Phase 1 vector budget and ~30× the 5K case. ADR-0010 explicitly anticipates this: "the question of 'should we move to pgvector in Phase 2?' comes up — and at the size of the corpus and the operational simplicity story, it will." Real options at this scale:
> 1. **Qdrant cluster + scalar/binary quantization** (3–5 nodes, int8 quant → 4× compression, ~0.1 % recall loss).
> 2. **pgvector with HNSW** on a beefier Postgres (consolidates store; trades raw QPS for ops simplicity).
> 3. **Managed vector DB** (Pinecone, Weaviate Cloud, Qdrant Cloud) for capacity-as-a-service.
>
> The estimates below assume **option 1** (Qdrant cluster with int8 scalar quantization) because it preserves the current `VectorStore` Protocol surface.

### Storage

| Tier | Size | Notes |
|---|---|---|
| Qdrant w/ int8 quantization | **~150 GB** | 15 M × ~10 KB; without quant ≈ 300 GB |
| PostgreSQL (chunks + metadata + indexes) | **~150–200 GB** | 15 M × ~8 KB + heavier audit/trace volume |
| Object storage (source PDFs) | **~750 GB – 1 TB** | 150 K × 5 MB |
| Redis (more sessions, larger cache) | **~8–16 GB** | |
| Logs / observability (1 yr) | **~100–200 GB** | Higher QPS |
| Backups / snapshots | **~500 GB** | |
| **Total storage** | **~2 – 3 TB** | dominated by source PDFs (cheap blob storage) and DB+vector tier (premium block storage) |

### Memory (RAM)

| Service | RAM | Notes |
|---|---|---|
| Qdrant cluster (HNSW must be RAM-resident for SLO) | **96–128 GB w/ quant** (192–256 GB without) | 15 M × ~6 KB raw + graph + payload cache. Distribute across 3–5 nodes. |
| PostgreSQL primary + replica | **32–64 GB shared_buffers** | Working set is much larger; expect heavier disk reads on cold paths |
| Redis | **16–32 GB** | |
| FastAPI workers (horizontally scaled) | **32–64 GB total** | 8–16 replicas × ~4 GB |
| Headroom + OS | **16–32 GB** | |
| **Total RAM** | **~256–512 GB** across cluster | with int8 quantization on Qdrant |

### CPU

| Service | vCPU | Notes |
|---|---|---|
| Qdrant cluster | **16–32 vCPU** | HNSW traversal cost grows with `log(N)`; quantization adds a small re-rank pass |
| FastAPI workers | **16–32 vCPU** | Scaled for higher concurrent user base implied by 150 K-book corpus |
| PostgreSQL primary + replica | **16–32 vCPU** | |
| Embedding / ingest workers (continuous) | **8–16 vCPU** | Sustained ingest of new books |
| **Total vCPU** | **~64–128 vCPU** | across cluster |

### Ingestion (150 K books)

- Parse: 150 K × 250 pages × 1 s ≈ **10,400 CPU-hours**. With 32 parallel workers → ~13 days continuous wall-time. Likely batched over weeks.
- Embeddings: 150 K × 100,000 = **15 B tokens** → **~$300 one-time** at $0.02 / 1 M tokens. OpenAI tier-limit dependent.
- Storage cost (cloud blob) ≈ $20–50/month for 1 TB; vector tier ≈ $300–600/month at managed pricing.

### Query-time LLM cost (recurring, Anthropic)

Per query (rough, per AGENTS.md routes):
- A1+A2 (`claude-sonnet-4-6`): ~1 K input + 200 output ≈ $0.005
- A5 Composer (`claude-opus-4-7`): ~5 K input (top_k=5 × 1 K tokens) + 500 output ≈ $0.10
- Per-answer total: **~$0.10–0.12** before caching; cached answers cost ~$0.

This is billed back through Stripe `served_answer_count`; not infrastructure cost per se, but it dominates unit economics at 150 K-book scale.

### Monthly cost (150 K books)

At this scale Railway managed services hit their practical ceilings; the numbers below assume migration to a hyperscaler (AWS / GCP / Azure) or Qdrant Cloud + a managed Postgres equivalent. Reserved-instance / committed-use discounts of 30–50 % typically apply at this commitment level — list-price ranges shown.

| Line item | Monthly | Basis |
|---|---|---|
| Qdrant cluster (3–5 nodes × 8 vCPU / 32 GB / 200 GB SSD) | **$600–2,000** | Self-managed on cloud VMs; Qdrant Cloud is 1.5–2× higher |
| Postgres primary + replica (2 × 16 vCPU / 64 GB / 500 GB SSD) | **$500–1,000** | Managed Postgres (RDS / Cloud SQL) |
| Redis cluster (16–32 GB managed) | **$100–200** | ElastiCache / MemoryStore |
| FastAPI workers (8–16 replicas × 4 vCPU / 4 GB) | **$300–800** | Container service (ECS / Cloud Run / Fly) |
| Background workers (ingest, embedding queue, batch) | **$100–300** | Lower-tier compute |
| Load balancer + WAF | **$30–80** | ALB / Cloud Load Balancer |
| Object storage (PDFs, ~1 TB on R2/S3 standard) | **$15–30** | R2 $0.015/GB; S3 $0.023/GB |
| Bandwidth/egress (higher API traffic) | **$50–200** | usage-dependent |
| Observability (logs, traces, APM at scale) | **$200–500** | Datadog / Grafana Cloud / Honeycomb |
| Backups + snapshot storage | **$50–150** | DB snapshots + Qdrant snapshots |
| **Fixed infra subtotal** | **~$1,950–5,260/mo** | |
| **One-time embedding cost** | **~$300** | 15 B tokens × $0.02/1M |

**Variable LLM spend** dominates at this scale. Same per-query economics (~$0.10–0.12/fresh, ~$0/cached). Assume 30 % cache hit after warm-up:

| Fresh queries/mo | Monthly LLM cost | Implied tenant mix |
|---|---|---|
| 35,000 | ~$4,200 | ~10 Institution-tier tenants @ 5K queries/mo |
| 70,000 | ~$8,400 | Growth phase, mixed tiers |
| 200,000 | ~$24,000 | Mature multi-tenant Enterprise SaaS |

**Total monthly all-in (150 K-book corpus, 70 K fresh queries/mo):** **~$10,000–14,000/month**.

**Unit economics check** (per `patristic-build-plan.md` tier table, lines 1042–1045):
- Institution tier: $350/mo for 5,000 queries → effective price $0.07/query
- Server cost per fresh query at this scale: ~$0.12 LLM + ~$0.02 amortized infra = ~$0.14
- **Gross margin without cache is negative.** Cache hit rate (currently 1-hour TTL per AGENTS.md) is the single biggest lever for profitability. At 50 % cache hit, effective cost drops to ~$0.07 — break-even with Institution pricing. Phase 3 prompt-versioning + corpus-revision-aware cache should lift this further.

---

## 6. Side-by-side summary

| Dimension | 5,000 books | 150,000 books | Ratio |
|---|---|---|---|
| Chunks | 500 K | 15 M | 30× |
| Embeddings (tokens) | 500 M | 15 B | 30× |
| **Storage total** | **~70–85 GB** | **~2–3 TB** | ~35× |
| **RAM total** | **~24–32 GB** | **~256–512 GB** | ~12–16× |
| **vCPU total** | **~12–16** | **~64–128** | ~5–8× |
| **Fixed infra cost** | **~$170–355/mo** | **~$1,950–5,260/mo** | ~11–15× |
| **One-time embedding cost** | **~$10** | **~$300** | 30× |
| **Variable LLM cost (typical usage)** | ~$60–240/mo (500–2K queries) | ~$4,200–8,400/mo (35K–70K queries) | usage-driven |
| **All-in monthly (typical)** | **~$400–600/mo** | **~$10,000–14,000/mo** | ~20–30× |
| Vector store viability | Single Qdrant node, no quant | Cluster (3–5 nodes) + int8 quant OR pgvector migration | architectural change |
| Hosting | Railway (managed) | Hyperscaler (AWS/GCP/Azure) + Qdrant Cloud or self-managed cluster | provider change |
| Phase mapping | Late Phase 1 / Phase 2 | Phase 2+ (per ADR-0010 hint) | — |

The RAM ratio is sub-linear (~12–16× for 30× data) because (a) HNSW graph overhead grows roughly linearly with vectors but only the hot working set needs to be resident, and (b) quantization compresses the vector portion 4× at 150K-scale. Storage ratio is super-linear (~35×) because backups, logs, and source PDFs all grow, plus a richer index footprint.

CPU ratio is sub-linear (~5–8×) because vector-search cost scales as `log(N)` for HNSW; the dominant CPU growth is from higher concurrent user load, not corpus size.

## 7. Validations / what was checked

- Embedding dim (1536) and model (`text-embedding-3-small`) confirmed in `chunk.schema.json` and AGENTS.md.
- Chunk size (800–1200 soft / 1500 hard) confirmed in `chunking-contract.md` and ADR-0009. The reference build plan's legacy "300–500 tokens, 50-token overlap" (line 1085) is **superseded** by the hierarchical chunking ADR — used canonical values.
- Vector store choice (Qdrant on Railway) and Phase 1 capacity hint (< 100 K vectors) read from ADR-0010 and reference build plan.
- Latency SLOs (vector search < 100 ms, p95 < 8 s) confirmed in `phase1-implementation-contract.md`.
- Qdrant HNSW params (`m=16`, `ef_construct=100`) from `patristic-build-plan.md` §Qdrant schema.

## 8. Assumptions, gaps, and what's NOT covered

- **Average book size is a derived assumption (250 pp × 300 words/pp × 1.3 tokens/word → 100 K tokens → 100 chunks).** Canonical docs do not specify this. Verify against the actual corpus profile before procurement.
- **Pricing is a list-price snapshot** as of model knowledge cutoff (Jan 2026). Anthropic, OpenAI, Railway, AWS, GCP, and observability vendors update pricing periodically; committed-use, startup-credit, and volume discounts of 20–50 % are common. Re-quote before signing contracts.
- Network egress, CDN, and frontend (Next.js) hosting are listed only at a high level. The estimate covers the retrieval data plane.
- Anthropic/OpenAI API spend is variable and metered through Stripe (`served_answer_count`); treated as a separate cost row from fixed infra.
- Phase 1 architecture is explicitly **not** designed for 150 K books. Numbers for that tier require either Qdrant clustering, pgvector migration, or managed vector DB — each with different cost shapes. The estimate uses Qdrant cluster + int8 quantization as the reference scenario.
- Disaster recovery, multi-region failover, and cross-tenant isolation hardening (beyond ADR-0003 baseline) not sized.
- **Cache hit rate is the single biggest lever on unit economics** at 150 K-book scale. The 30 % assumption in this estimate is a guess; instrument `cache_hit_rate` from day 1 to validate.
- Anthropic prompt caching (input-cache discounts on repeated A1/A2/A5 contexts) is not modeled here; if enabled, it can reduce variable LLM cost by another 30–60 %.

## 9. Next useful actions

1. Sample 10–20 representative books from the seed corpus and measure actual `chunks_per_book` to replace the 100 assumption.
2. If 150 K-book scale is on the roadmap, open an ADR amendment for ADR-0010 capturing the cluster/quantization or pgvector migration decision.
3. Run a load test at 500 K vectors (the 5K-book point) against the current single-node Qdrant config to validate the <100 ms SLO before extrapolating further.
4. Instrument cache hit rate per AGENTS.md cache-key definition and report it in the margin dashboard from launch — it dominates the 150K-tier P&L.
5. Re-quote Anthropic, OpenAI, Railway, and target hyperscaler pricing before any procurement decision; the numbers in §4 and §5 are list-price snapshots, not negotiated rates.
