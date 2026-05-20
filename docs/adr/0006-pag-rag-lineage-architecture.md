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

Existing Qdrant payload fields such as `related_chunks`, `references_father`, and `builds_on` remain lightweight retrieval hints. The authoritative version of a relation lives in PostgreSQL and must carry review status.

## Embedding Model Upgrade

Phase 1 uses `openai:text-embedding-3-small`. The detailed runbook for upgrading to a different embedding model — dual-index provisioning, backfill, retrieval-eval + safety-suite certification gates, cutover, rollback, snapshot pinning, and old-index decommissioning — lives in **`docs/contracts/embedding-upgrade-sop.md`** and is constrained by ADR-0011 (hybrid retrieval) and ADR-0013 (collection topology). That SOP is the authoritative procedure; do not rederive it.

Summary flow (the SOP elaborates each step):

1. Provision a parallel index (Option A: second named vector on the existing collection; Option B: second collection) at the new model's dimension.
2. Backfill all approved chunks under the new `ModelRoute` via `workers/tasks/embedding_backfill.py`.
3. Run the retrieval-eval suite (`docs/contracts/retrieval-eval-suite.md`) AND the safety suite against the new route; promote to `certified` only when both pass.
4. Cutover atomically by switching the active route (env-var pinned in Phase 1; a redeploy is the cutover). `corpusVersion` bumps automatically via the cache-key invalidation rule in `docs/contracts/cache-key.md`.
5. Park the old index for the retention window; decommission only after a second founder signoff.

Rollback is the cutover in reverse and is available throughout the retention window.

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
