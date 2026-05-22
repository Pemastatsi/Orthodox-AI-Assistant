# ADR 0006: PAG-RAG Lineage Architecture

Date: 2026-04-26 (amended 2026-05-02 to add Embedding Model Upgrade placeholder section per decision register row 17)
Status: Accepted

## Context

The Patristic Library Assistant must answer from a closed, tenant-approved corpus. Standard vector RAG is useful for finding semantically similar passages, but patristic and Orthodox theological questions often depend on lineage, authority, translation history, quotation chains, and whether a later source is structurally downstream from an earlier witness.

The project will use "PAG-RAG" as internal shorthand for Private Agentic Graph-RAG. This is not an external industry standard. It combines established patterns:

- GraphRAG / graph-enhanced vector search
- Agentic or hybrid RAG planning
- closed-corpus evidence packaging
- deterministic citation and lineage verification
- private/local deployment options

## Decision

The long-term retrieval architecture is graph-enhanced, but MVP remains vector-first.

Phase 1 uses Qdrant vector retrieval, tenant filters, approved-source gating, deterministic A4 evidence packaging, A5 composition from evidence only, and A6 citation verification.

Phase 2 adds graph metadata capture and admin review. Candidate entities and candidate lineage edges may be produced during ingestion, but they are not evidence until approved.

Phase 3 may enable graph-aware retrieval. A2 can request graph expansion for answer modes such as `consensus`, `historical_development`, `scholarly_dispute`, and selected `institutional_policy` queries. A3 may combine vector/BM25 retrieval with approved graph traversal. A4 must admit only approved graph edges into `EvidencePacket.lineageContext`. ADR 0007 defines the related query-transformation boundary: Phase 1 does not use generic LLM query rewriting, and any later concept expansion must be graph-grounded, tenant-scoped, and approved.

Phase 4+ extends the same contract to passage alignment, translation variants, and manuscript witness graphs.

## Rules

1. Qdrant remains the semantic retrieval engine in MVP.
2. PostgreSQL stores canonical graph edges first. Neo4j or Apache AGE is optional later, not required for MVP.
3. An LLM-extracted edge is a candidate, not authority.
4. Every graph edge must include tenant scope, relation type, relation basis, extraction method, confidence score, review status, and provenance note.
5. Only approved edges may affect answer composition, confidence tier, lineage explanations, or source prioritization.
6. A5 may not claim "X builds on Y", "X quotes Y", "X is a translation of Y", or "X contrasts with Y" unless that relation appears as an approved edge in the evidence packet.
7. A6 must verify all lineage claims against approved edge IDs.
8. Candidate edges are visible to admins/reviewers but suppressed from user-facing answers.
9. Local/private inference is a deployment option, not a retrieval guarantee by itself. Cloud model routes may still be certified if they pass privacy, safety, and closed-corpus requirements.

## Data Model

Canonical graph tables:

- `graph_entities`: persons, works, concepts, councils, passages, sources, and tradition tags.
- `chunk_entity_mentions`: reviewed mentions linking chunks to graph entities.
- `lineage_edges`: reviewed relations such as `quotes`, `references`, `builds_on`, `contrasts_with`, `same_passage_as`, `translation_of`, `paraphrases`, `supports`, and `contested_by`.
- `graph_candidates` (REC-013, Phase 1 capture): unreviewed candidate edges emitted at ingestion. The schema mirrors `lineage_edges` but adds `extraction_method` (`'regex' | 'llm' | 'hybrid'`), `extractor_route_id` (FK to `model_routes` when LLM-extracted), `confidence` (float, 0–1), and a `review_status` enum starting at `'candidate'`. Candidate edges never enter `EvidencePacket.lineageContext`; promotion to `lineage_edges` requires admin approval through a Phase-2 admin UI. See `docs/contracts/db-schema.md` §`graph_candidates` for the DDL.

Existing Qdrant payload fields such as `related_chunks`, `references_father`, and `builds_on` remain lightweight retrieval hints. The authoritative version of a relation lives in PostgreSQL and must carry review status.

### Phase 1 candidate-edge emission (REC-013)

Candidate edges are emitted at ingestion time rather than backfilled after Phase-2 launch. The ingestion worker runs a two-stage extraction:

1. **Deterministic stage** — regex over the chunk text catches citation-style edges (e.g., `quotes`, `cites`, `translation_of`) with high precision. Emits `extraction_method='regex'`.
2. **LLM residual stage** — for passages where the regex stage finds no edges, a single LLM call against a `ModelRoute` with `purpose='edge_extraction'` (D-MDL-003, default Haiku 4.5) proposes additional candidate edges. Emits `extraction_method='llm'` or `'hybrid'` when both stages contribute.

The LLM stage runs **at ingestion only** — it never sees the user's question and never runs on the answer path. This preserves ADR-0007's boundary (chunk-side ingestion enrichment is not query rewriting; see ADR-0007 §Clarification).

Candidate edges are invisible to A4/A5 until promoted, so A6's lineage gate still requires approved edges only and the closed-corpus invariant is intact. Re-running the extraction on a new `corpusVersion` is supported and idempotent (candidate edges keyed on `(source_chunk_id, target_chunk_id, relation_type, extraction_method)` are deduplicated).

## Embedding Model Upgrade (Placeholder — Detailed SOP in Phase 2)

Phase 1 uses `openai:text-embedding-3-small`. When upgrading to a different embedding model the rough flow is:

1. Add the new model to `model_routes` with `purpose='embedding'`, `certification_status='draft'`.
2. Run a dual-index window: index a representative chunk sample under both the old and new vectors; compare retrieval quality on the per-tenant retrieval evaluation set defined in ADR 0007 (recall@k, MRR, no-result follow-up rate).
3. Backfill all approved chunks with the new vectors via `workers/tasks/embedding.py` in batched mode; do not delete old vectors until cutover is complete (Qdrant tolerates extra payload but `chunk.embeddingDimension` must match the active route).
4. Owner certifies the new route per ADR 0004; `.env`'s `ACTIVE_MODEL_ROUTE_EMBEDDING` is updated atomically with a deploy.
5. Cutover bumps `corpusVersion` (cache flush) and deprecates the old route after a stability window.

The detailed SOP — including rollback, partial-tenant cutover, and dimension mismatch handling — is added in Phase 2 alongside the multi-tenant ingestion stress-test plan.

## Consequences

This architecture is stronger than plain vector RAG for doctrinal-development, consensus, scholarly-dispute, and witness-aware queries. It also adds ingestion and review cost, so graph-driven answering is deliberately deferred until the closed-corpus MVP is stable.

The project should avoid marketing claims like "deterministic lineage" unless the underlying edges are curated or formally approved. The correct claim is: deterministic handling of validated lineage metadata.

## Phase 2 Embedding Upgrade: Recommended Candidates

When the Phase 1 → Phase 2 transition begins, evaluate the following models against `text-embedding-3-small` using a held-out sample of ≥50 Polytonic Greek patristic chunk pairs before committing to a replacement. The concern is that `text-embedding-3-small`, while multilingual, was not trained heavily on Polytonic Greek orthography (diacritics, ligatures, archaic forms) and may underperform on Greek query → English chunk and English query → Greek chunk retrieval pairs.

| Model | Strengths | Risk |
|---|---|---|
| `multilingual-e5-large-instruct` | Strong ancient-language coverage, instruction-tuned | Larger, slower, higher memory |
| `openai/text-embedding-3-large` | Higher dimension (3072), better semantic precision | ~2× cost increase |
| Domain fine-tuned (custom) | Best precision for Patristic Greek-English pairs | Requires labelled training data + infra |

Evaluation criteria: cross-lingual recall@10 on Greek query → English chunk pairs, and English query → Greek chunk pairs, measured against a curated held-out set drawn from the actual tenant corpus. Minimum acceptable threshold: recall@10 ≥ 0.80 on both directions before certifying a replacement route.

The dual-indexing + backfill + cutover SOP defined in the "Embedding Model Upgrade" section above applies unchanged to any embedding model swap.
