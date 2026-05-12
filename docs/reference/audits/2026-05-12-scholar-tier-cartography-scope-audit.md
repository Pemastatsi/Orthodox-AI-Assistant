# Audit: Scholar Tier / Dynamic Theological Cartography vs. Current Canonical Scope

Status: reference (non-canonical analysis)
Date: 2026-05-12
Source proposal: `/root/.claude/uploads/13a085ed-6aa3-4fc9-85db-91e8ff120e8e/29765111-scholar_tier_dynamic_theological_cartography_scope.md` (uploaded, not committed to repo)

## Purpose

The uploaded "Scholar Tier: Dynamic Theological Cartography & Patristic Genealogy" document proposes a 20-section feature set for the Orthodox AI Assistant. This audit maps each of its sections to the project's current canonical sources (`AGENTS.md`, ADRs 0001–0010, the Phase 1 implementation contract, the frontend component contract, the chunk schema, the approved-decisions register) and labels each as **Aligned**, **Deferred**, **Conflicts**, or **Rejected**, with a citation to the clause that justifies the label.

This file changes no contracts, schemas, ADRs, or task cards. It is decision support, not a decision. Where harvestable design ideas exist inside otherwise-rejected sections, they are collected in the **Harvest List** at the end.

## How to read this audit

- **Aligned** — already covered by canonical contracts/ADRs, or trivially compatible with Phase 1 behavior.
- **Deferred** — strategically endorsed and explicitly mapped to Phase 2 or Phase 3 in existing ADRs. No conflict in principle; only in timing.
- **Conflicts** — collides with a locked decision in an ADR or canonical contract. Adoption would require an explicit ADR amendment.
- **Rejected** — fundamentally incompatible with closed-corpus or other invariants. Should not be adopted in any form.

A single section may receive a **mixed** classification when its sub-elements diverge.

---

## Headline Verdict

The proposal's *strategic vision* — a research-grade Orthodox theological environment built around lineage, councils, language, geography, and authority — is **strongly aligned** with ADR 0006 (PAG-RAG) and ADR 0007 (query-transformation boundaries). The long-term north star is essentially the same.

The proposal's *concrete mechanisms* are **largely Phase-2/Phase-3 work** by the project's own phasing, and three specific mechanisms **conflict** with locked Phase-1 decisions:

1. **AI Graph Architect** (§ 7) generates relationship JSON at query time from a frontier LLM. This conflicts with ADR 0006 rules 3–8 (LLM-extracted edges are candidate, not authority; A5 may not claim lineage from unapproved edges; A6 must verify lineage claims against approved edge IDs) and ADR 0007 (no generic LLM transformation in Phase 1; expansion must be approved-graph-grounded).
2. **Implicit Echoes / `POSSIBLE_INFLUENCE` surfaced to end users** (§ 5.5) conflicts with ADR 0001 rule 6 and ADR 0006 rule 8 (candidate edges are admin-only and suppressed from user-facing answers).
3. **The proposal's "Phase 1" sequencing** (§§ 9, 17, 18) treats timeline + heatmap + synod overlay as MVP work. This collides with the actual Phase 1 task cards (T-001 through T-007), which deliver closed-corpus Q&A, evidence packaging, citation verification, and admin chat + safety gate. Visualization UI is not on the current Phase 1 critical path.

The closed-corpus contract is about *provenance and admission*, not display modality: rendering approved chunks on a timeline, heatmap, or graph is **not** against scope in principle. What is against scope is generating relationships dynamically with an LLM and exposing speculative/candidate metadata to users.

Net recommendation: the proposal is a viable seed for a future Phase-2 ADR pack. The audit's Harvest List below identifies the specific extractable pieces and their target canonical destinations.

---

## Per-Section Matrix

### § 1. Executive Summary

**Classification:** Aligned (vision) / Deferred (mechanisms)

The 10 scholarly questions enumerated (who taught this first, who inherited it, which councils received it, etc.) all fit naturally within the ADR 0006 lineage data model (`graph_entities`, `chunk_entity_mentions`, `lineage_edges` at ADR 0006 lines 41–50). The MVP, however, answers from approved chunks only; multi-hop lineage answering is Phase 3 (ADR 0006 lines 27–29). The closing question — "Which claims are source-backed and which are AI-inferred?" — is *already* answerable in Phase 1: source-backed = admitted into the `EvidencePacket` (ADR 0001 rule 2); AI-inferred relationships do not appear because A5 may not claim lineage absent approved edges (ADR 0006 rule 6, AGENTS.md line 128).

### § 2. Product Principle ("visualizations must function as research instruments")

**Classification:** Aligned

This principle aligns directly with `frontend-components.md` accessibility rule "color is never the only signal for handling/confidence" (line 15) and ADR 0001's evidence-traceability requirement. There is no Phase-1 visualization to apply it to, but the principle itself constrains future Phase-2 UI work appropriately.

### § 3. Strategic Objective

**Classification:** Aligned (as a north-star statement)

The nine "Scholar Tier should allow users to see" bullets correspond approximately to:

- Item 1 (chronological development) → Phase 2 admin-curated `lineage_edges` rendered chronologically.
- Item 2 (relationship between saints/texts/councils/concepts) → ADR 0006 `graph_entities` + `chunk_entity_mentions`.
- Item 3 (influence chain) → ADR 0006 `lineage_edges` (relation_type ∈ `quotes`, `references`, `builds_on`, etc.).
- Item 4 (explicit citation vs. probable influence) → ADR 0006 rule 3 (LLM-extracted is candidate) + rule 8 (candidate suppressed from user-facing answers).
- Item 5 (geographic spread) → requires new schema (no GIS fields exist; see § 4.5 below).
- Item 6 (linguistic depth) → Phase 2 embedding upgrade (ADR 0006 lines 70–80) opens this; aligned chunk-level translations do not yet exist.
- Item 7 (synodal context) → requires new `councils` table (see § 8 + § 10 below).
- Item 8 (authority and reception) → Phase 2 admin signal; must derive only from approved metadata (ADR 0006 rule 5).
- Item 9 (consensus vs. opinion vs. disputed vs. condemned) → potential ADR 0002 extension (see Harvest item H6).

### § 4.1 Chronological Lineage ("The River of Tradition")

**Classification:** Deferred (Phase 2 UI; partial data-model gap)

Rendering approved chunks on a horizontal timeline with council overlays is fully compatible with the closed-corpus contract — every node would link back to approved source text (ADR 0001 rule 4). Two obstacles, both Phase 2:

1. **Data model gap.** `chunk.schema.json` has no `date`, `century`, `location`, `ecclesiasticalStatus`, or `councilReferences` fields; the upload's § 4.1 timeline requires all of these on every node. The Phase 2 graph metadata layer (ADR 0006 `graph_entities`, `chunk_entity_mentions`) is the right place to land them, joined via `parentChunkId` (ADR 0009 / chunk.schema.json line 64).
2. **UI scope.** `docs/contracts/frontend-components.md` lists the Phase 1 component contracts: `<ChatComposer>`, `<AnswerPanel>`, `<CitationPanel>`, `<ReframingDisclosure>`, `<ConfidenceBadge>`, `<DisclaimerBanner>`, `<StageStatus>`, `<AdminApprovalQueue>`, `<AdminQueryLog>`, `<AdminFlaggedList>`, `<AdminAuditLog>`, `<TenantSwitcher>`. No `<Timeline>` component is included; no `/scholar` or `/timeline` route exists. Introducing one is a contract amendment, not an implementation detail.

The proposal's own § 4.1 Technical Notes (lines 148–166) acknowledge this can be built without a graph database, on enriched metadata + React timeline, with each node linking back to source text. That approach is compatible with ADR 0006 Phase 2.

**Harvest pointer:** H1 (Synod Overlay timeline as admin-only Phase-2 visualization on approved metadata).

### § 4.2 Semantic Web ("The Constellation")

**Classification:** Mixed: Deferred (graph data model) / Conflicts (force-directed graph of inferred edges to end users)

The proposed node and edge taxonomies (§ 4.2 lines 191–233) largely overlap with the existing ADR 0006 `graph_entities` and `lineage_edges` taxonomies and provide a useful seed list (Harvest item H4). The conflict is the user-facing rendering of inferred or candidate edges:

- ADR 0006 rule 8: "Candidate edges are visible to admins/reviewers but suppressed from user-facing answers."
- ADR 0001 rule 6: "Unapproved chunks, candidate graph edges, admin-only content, and suppressed sources are never user-facing evidence."

A force-directed graph that mixes approved + candidate + inferred edges in the user view is the central thing those rules forbid. A graph showing **only approved edges**, with confidence labels, would be aligned (and is a natural Phase-3 surface).

The proposed § 4.2 "Weight of Authority" sub-feature also requires authority signals that don't yet exist on any approved schema (see § 12 below).

### § 4.3 Philokalic Heatmap

**Classification:** Aligned (extension of existing `chunk.categories`)

`chunk.schema.json` line 43 already carries a `categories: string[]` field. A category-distribution heatmap over retrieved-and-admitted chunks is a pure UI/aggregation layer with no new corpus or LLM cost. The 22-category taxonomy proposed at § 4.3 lines 299–325 is a richer version of what tenants would supply; it does not collide with anything.

The proposed click-to-filter behavior would require a new query parameter on `/query` or post-filter step on `VerifiedResponse.citations`. Not a blocker; not in Phase 1 scope (T-006 admin/chat UI does not include faceted-filter UI).

**Harvest pointer:** H5 (theological category taxonomy as a non-binding chunk-tagging reference).

### § 4.4 Cross-Linguistic Mirror View

**Classification:** Deferred (Phase 2+ multilingual; aligned chunks do not yet exist)

Greek-English split-pane comparison is endorsed by the ADR 0006 Phase 2 Embedding Upgrade section (ADR 0006 lines 70–80, multilingual-e5-large-instruct / text-embedding-3-large evaluation against held-out Polytonic Greek pairs). However, the proposed UI requires:

1. **Aligned bilingual chunks.** `chunk.schema.json` does not store an `originalText` / `translationText` pair; it stores a single `text` with a `language` field. Word- or phrase-level alignment requires new schema work.
2. **A theological glossary.** Not in any contract today.
3. **Multilingual theological embeddings.** ADR 0006 lines 70–80 set the evaluation criteria for an upgrade but do not commit to one.

The Greek term list at § 4.4 lines 404–421 (νοῦς, λόγος, θέωσις, νῆψις, ἀπάθεια, etc.) is a useful seed for the eventual glossary.

**Harvest pointer:** H7 (theological glossary seed list).

### § 4.5 Geographic Spread ("The Spread of the Word")

**Classification:** Deferred (no GIS fields exist; Phase 3 candidate)

`docs/contracts/db-schema.md` and `chunk.schema.json` have no geographic fields. ADR 0006 does not explicitly schedule a `Location` graph-entity type, though it allows "tradition tags" (ADR 0006 line 45). A Phase 3 map visualization with time slider is consistent with ADR 0006 Phase 4+ ("passage alignment, translation variants, and manuscript witness graphs"), but the data model is upstream of any UI work. The proposal's own technical notes (§ 4.5 lines 549–556) flag this as high-effort.

### § 5.1–5.3 Pedigree of Tradition / Influence Parser / Required Chunk Metadata

**Classification:** Mixed: Aligned (explicit-citation parser as Phase 2 candidate-edge ingestion) / Deferred (chunk metadata enrichment) / Conflicts (raw chunk metadata format)

Comparing the proposal's `chunk` JSON (§ 5.3 lines 595–628) to `chunk.schema.json`:

| Upload field (§ 5.3) | Status in `chunk.schema.json` | Notes |
|---|---|---|
| `chunk_id`, `author`, `work`, `language` | Aligned (as `chunkId`, `father`, `work`, `language`) | Naming differs; semantics match. |
| `topic_tags` | Aligned (as `categories`) | |
| `date_range`, `century`, `location`, `ecclesiastical_status`, `source_type` | Missing | Reasonable Phase-2 additions; better placed on the linked `Author` / `Source` / `graph_entities` row than duplicated per chunk. |
| `scripture_references`, `council_references`, `doctrinal_concepts`, `translation_notes` | Missing | Phase-2 candidates; should be admin-reviewed (ADR 0006 rule 3). |
| `explicit_citations[]` | Missing on chunk; **belongs on `lineage_edges` (ADR 0006)** | Each detected citation is a candidate `lineage_edges` row with `relation_type='quotes'` or `'references'`. Phase 2 ingestion pipeline. |
| `implicit_influences[]` (with `confidence: medium`) | Missing | Adding this to chunk metadata as user-facing detail = **Conflicts** with ADR 0006 rules 3, 6, 8 (candidate, suppressed, A5 cannot claim). Phase-2 admission via reviewed `lineage_edges` with `relation_type='paraphrases'` or `'supports'` is the canonical path. |
| `authority_weight: 0.87` | Missing | Phase-2 admin-derived signal; see § 12. |

**Harvest pointers:** H2 (explicit-citation parser as Phase 2 lineage-edge ingestion), H3 (chunk-metadata enrichment field list).

### § 5.4 Explicit Citations

**Classification:** Aligned in principle / Deferred in execution

Detecting "As Gregory says...", "the divine Chrysostom teaches...", direct quotations, council citations, and creedal references during ingestion is a natural Phase-2 ingestion enrichment. The proposed output (§ 5.4 lines 652–661) maps almost 1:1 onto an ADR 0006 `lineage_edges` row with `relation_type='quotes'`, `extraction_method='regex'` or `'llm'`, `confidence`, and `review_status='pending'`. The output **must enter the candidate-edge admin review workflow**, not become user-facing on first detection (ADR 0006 rules 3, 8).

**Harvest pointer:** H2.

### § 5.5 Implicit Echoes ("POSSIBLE_INFLUENCE")

**Classification:** Conflicts (as written) / Aligned if reframed

As written, the proposal renders a `display_warning: "This is an inferred relationship, not an explicit citation"` to end users. That display surfaces an unapproved edge in the user-facing view, which is exactly what ADR 0006 rule 8 forbids ("Candidate edges are visible to admins/reviewers but suppressed from user-facing answers") and what ADR 0001 rule 6 forbids ("Unapproved chunks, candidate graph edges, admin-only content, and suppressed sources are never user-facing evidence").

The aligned path: implicit echoes are persisted as `lineage_edges` rows with `extraction_method='llm'`, `confidence='medium'`, and `review_status='pending'`. They appear in admin review queues (T-006 scope) only. Once an admin marks them `approved`, they may appear in user answers — at which point A5 may claim lineage and A6 must verify the approved edge ID (AGENTS.md line 128, ADR 0006 rules 6–7).

The `display_warning` mechanism is not a permitted substitute for the admin approval gate. A6 verification does not look at display warnings; it looks at approved-edge IDs.

### § 6.1–6.5 Graph Database Layer

**Classification:** Aligned on direction / Aligned on infra recommendation / Harvestable taxonomy

The proposal's § 6.2 recommendation ("For MVP, begin with relational tables or PostgreSQL JSON relationships. For Phase 2, add Neo4j, Memgraph, or PostgreSQL AGE") agrees with ADR 0006 rule 2: "PostgreSQL stores canonical graph edges first. Neo4j or Apache AGE is optional later, not required for MVP." No conflict.

The node-type list (§ 6.3 lines 740–760) and edge-type list (§ 6.4 lines 766–791) are richer than the relation types named in ADR 0006 (`quotes`, `references`, `builds_on`, `contrasts_with`, `same_passage_as`, `translation_of`, `paraphrases`, `supports`, `contested_by` per ADR 0006 line 48). The upload's additional edge types — `INFLUENCED_BY`, `TEACHER_OF`, `STUDENT_OF`, `DEFENDS`, `OPPOSES`, `CONDEMNS`, `AFFIRMS`, `DEFINED_BY`, `USED_BY_COUNCIL`, `INTERPRETS_SCRIPTURE`, `LITURGICALLY_RECEIVED`, `PARTICIPATED_IN_CONTROVERSY`, `PRESERVES`, `EXPANDS_UPON` — are useful seed-list material for a Phase-2 enum extension to `lineage_edges.relation_type`.

§ 6.5's example graph query ("Show me the Orthodox tradition on Hesychasm" → graph of Desert Fathers → Evagrius → Macarius → Climacus → Symeon → Gregory of Sinai → Palamas → Palamite Councils → Athonite → Slavic) is exactly the Phase-3 ADR 0006 use case ("graph-aware retrieval" for `historical_development` answer mode).

**Harvest pointers:** H4 (node-type and edge-type enum seed lists).

### § 7. AI Graph Architect

**Classification:** Conflicts (central proposal collides with multiple locked decisions)

This is the proposal's most consequential conflict and the reason this section deserves its own audit-level callout.

§ 7.1 proposes a frontier reasoning model that, at query time, generates "visualization-ready JSON from retrieved chunks" by classifying, structuring, ranking, and "propos[ing] visual relationships based on source evidence." § 7.4 lines 877–919 shows the JSON output including an `edges[]` array with `relationship` (e.g., `doctrinally_precedes`), `explanation`, and `confidence` fields generated at query time.

This conflicts with:

1. **AGENTS.md "Do not build in Phase 1"** (lines 48–57): "generic LLM query rewriting", "graph-driven answering", "unbounded agent collaboration", "open-web answer-time browsing" — the Graph Architect is graph-driven answering with an additional inference layer.
2. **ADR 0006 rule 3**: "An LLM-extracted edge is a candidate, not authority." The Graph Architect produces edges and presents them to users in the same pass, with no candidate→approval boundary.
3. **ADR 0006 rule 6**: A5 may not claim lineage "unless that relation appears as an approved edge in the evidence packet." The Graph Architect generates lineage relations at query time, which by definition are not approved edges.
4. **ADR 0006 rule 7**: "A6 must verify all lineage claims against approved edge IDs." There are no edge IDs for query-time-generated edges.
5. **ADR 0007 decision** (lines 13–22): "Phase 1 will not implement generic LLM query rewriting... Retrieval quality should first improve through chunking, metadata, BM25 or hybrid retrieval, reranking, and approved graph structure." The Graph Architect is a generic LLM transformation step, even if labeled differently.
6. **AGENTS.md Known Gap #5** (lines 168–180): "Do not adopt pre-compilation or external Knowledge Artifact approaches — Pre-compiling corpus summaries as persistent Knowledge Artifacts conflicts with ADR 0001 (every claim must trace to an approved chunk with a verifiable quote span)..." Query-time JSON generation is the dynamic equivalent of a Knowledge Artifact and inherits the same traceability problem.

The proposal's own § 7.1 caveat ("The model should not invent relationships... It may only: classify, summarize, structure, rank, label confidence, propose visual relationships based on source evidence") is well-intentioned but unenforceable at the architecture level. The closed-corpus contract enforces evidence boundaries through *structural* gates (A4 admission, approved-edge IDs, A6 verification), not through prompt instruction. Asking the LLM to "only propose relationships based on source evidence" is the soft equivalent of asking it not to hallucinate — it is not a substitute for ADR 0006's approval workflow.

**An aligned alternative exists.** A future "visualization composer" at the post-A6 stage could read **already-approved** entities and edges from `EvidencePacket.lineageContext` (ADR 0006 Phase 3 design) and arrange them into a deterministic visualization layout. Such a composer is not an LLM; it is a layout function. That is a separate Phase-3 ADR; no LLM call is required because the relations are already approved and the field is structured.

### § 8. Synodal Context

**Classification:** Aligned (as filter framing) / Deferred (requires `councils` table)

The premise — filter results by "before a council", "after a council", "during a controversy", etc. — is directly compatible with `chunk.categories` plus a future `councils` reference. The list of safeguards in § 8.4 ("Never present speculative relationships as dogmatic fact. Every doctrinal claim must be traceable to a source.") is exactly ADR 0001 rule 4 and ADR 0006 rule 6.

What's missing is a canonical `councils` table. The proposal's § 10 includes one (lines 1175–1190); see § 10 below.

**Harvest pointer:** H8 (councils metadata model).

### § 9. MVP Implementation Hierarchy

**Classification:** Conflicts (on phase mapping)

The upload's "Phase 1 — Low Effort / High Impact" list (§ 9 lines 997–1032) names: chronological timeline + synod overlay + metadata tagging + date/council filters + clickable nodes + category heatmap. None of these are in the project's actual Phase 1 critical path (T-001 through T-007 cover: contracts/scaffold, ingestion, A1/A2/A3, A4/A5/A6, cache/logs/billing, admin chat + safety gate, real safety configs). The Phase 1 → 2 exit criteria in `phase1-implementation-contract.md` do not include any visualization-layer items.

The conflict is purely on sequencing — not on whether the work is worth doing. The upload's "Phase 2 — Medium Effort" and "Phase 3 — High Effort" sections (§§ 9, lines 1035–1108) align approximately with the project's actual Phase 2/3 plans in ADR 0006.

### § 10. Suggested Data Architecture

**Classification:** Mixed: Aligned (`texts`, `chunks`, `authors`) / Deferred (`councils`, `relationships`)

| Upload table | Status |
|---|---|
| `texts` | Aligned with `docs/schemas/source.schema.json` ("Tenant corpus source document"). Naming differs; semantics overlap. |
| `chunks` | Aligned with `chunk.schema.json` (with the metadata gaps already catalogued in § 5.3 above). |
| `authors` | Aligned in principle. The current schema reads `father` as a string on `chunk`; a future normalized `authors` table is reasonable. ADR 0006 `graph_entities` of type `Author` is the canonical landing place. |
| `councils` | Missing. New Phase-2 table proposal. Should join `lineage_edges` for `USED_BY_COUNCIL` / `DEFINED_BY` style relations. |
| `relationships` | Already exists as `lineage_edges` in ADR 0006 line 48 (with richer review/provenance fields). |

The upload's `relationships` row design includes `is_inferred` and `review_status` (§ 10 lines 1196–1209), which is exactly the ADR 0006 candidate→approval shape. Consistent.

**Harvest pointer:** H8 (councils), H9 (author normalization).

### § 11. Confidence System

**Classification:** Aligned (extends ADR 0002, additively)

ADR 0002 defines `confidenceTier: GREEN | YELLOW | RED` based on **evidence coverage**, not topic sensitivity (ADR 0002 rule 1, line 22). The upload's confidence scale (`High | Medium | Low | Speculative | Disputed`, § 11 lines 1219–1234) is finer-grained and oriented to relationship/claim confidence rather than evidence-coverage confidence — these are different axes.

Adoption path: rather than amend `confidenceTier`, add a separate `relationConfidence` (or `lineageConfidence`) field on `lineage_edges` rows. ADR 0006 line 35 already includes `confidence score` as a required field on each edge; the upload's 5-level taxonomy could be the enum.

The proposal's display rules ("Speculative: hidden by default unless user enables speculative links") are essentially a tenant-config affordance on top of ADR 0006 rule 8 — but ADR 0006 rule 8 is stricter: candidate edges are **always** suppressed from user view, not just hidden-by-default-with-opt-in. Any "let users opt into speculative links" toggle would itself be a contract amendment.

**Harvest pointer:** H6 (relation-confidence enum on `lineage_edges`; no end-user opt-in toggle in MVP).

### § 12. Authority Weighting System

**Classification:** Deferred (admin-derived signal; not currently scheduled)

`authority_weight` is a per-entity scalar derived from conciliar reception + later citation frequency + liturgical reception + manuscript reliability (§ 12 lines 1245–1273). All inputs require approved metadata that does not yet exist on chunks or authors. The upload's own § 16.3 risk mitigation correctly notes that authority must not depend on fame alone.

This is a reasonable Phase-2 admin-derived feature, **provided every input signal is itself approved metadata** (no LLM-inferred reception counts). The 0.87 / 0.94 numerics in the upload's examples (§ 5.3, § 12) are illustrative, not normative.

**Harvest pointer:** H10 (authority-weight signal definition; derivation rules; admin-derived only).

### § 13. Developer-Facing Component Requirements

**Classification:** Conflicts (vs. `docs/contracts/frontend-components.md`)

The upload's §§ 13.1–13.5 require Timeline, Graph, Heatmap, Mirror, and Map components. None exist in `docs/contracts/frontend-components.md` (canonical for Phase 1 components, dated 2026-05-02). The contract enumerates the Phase 1 component set on lines 32–214 and lists `<ChatComposer>`, `<AnswerPanel>`, `<CitationPanel>`, `<ReframingDisclosure>`, `<ConfidenceBadge>`, `<DisclaimerBanner>`, `<StageStatus>`, `<AdminApprovalQueue>`, `<AdminQueryLog>`, `<AdminFlaggedList>`, `<AdminAuditLog>`, `<TenantSwitcher>` — no visualization components. Adding any of them is a contract amendment, not an implementation detail.

The upload's library recommendations (React Flow, D3.js, Cytoscape.js, Vis.js, TimelineJS, MapLibre, Leaflet) are reasonable seeds for the eventual Phase-2/3 component proposals, but none has been certified as an approved dependency.

### § 14. User Stories

**Classification:** Deferred (Phase 2/3 personas)

All six stories assume Scholar Tier UI surfaces (timeline, graph, mirror, map, time slider). They are useful as Phase 2/3 acceptance-criteria seeds. None applies in Phase 1 because none of those surfaces exists yet.

### § 15. Competitive Differentiation

**Classification:** Aligned (vision)

The "AI search → source-grounded Orthodox theological intelligence platform" positioning matches AGENTS.md's product goal ("closed-corpus Orthodox theological assistant for tenant-approved libraries"). No engineering decision rides on this section.

### § 16. Risks and Safeguards

**Classification:** Aligned (mirrors ADR 0001 + ADR 0006)

Every mitigation listed (every edge must have evidence; every inferred relationship must be labeled; speculative links hidden by default; users must be able to inspect source passages; classify claims by status; geography uncertainty; lexical-vs-theological distinction) restates rules already encoded in ADR 0001 (closed corpus), ADR 0006 (candidate vs. approved edges; provenance; review status), and ADR 0002 (transparent sensitivity handling). § 16.1 ("Speculative links should be hidden by default") is a *weaker* form of ADR 0006 rule 8 (candidate edges are *suppressed*, not hidden-by-default).

### § 17. Recommended MVP Backlog

**Classification:** Conflicts (sequencing; epics duplicate Phase 2/3 work)

Epic 1 (Metadata Enrichment) overlaps with the Harvest list items H3, H8, H9. Epic 2 (Timeline) is Phase 2 UI. Epic 3 (Synodal Context) requires the councils table from Epic 1. Epic 4 (Heatmap) is the only one that could be backed entirely by Phase-1 fields (`chunk.categories`), but the heatmap **component** is not in `frontend-components.md`. Epics 5–7 (Graph, Linguistic, Geographic) are Phase 2/3 by the upload's own § 9 phasing.

None of these epics is on the Phase 1 → 2 exit criteria.

### § 18. MVP Scope Recommendation

**Classification:** Conflicts (proposes Phase-2 work as immediate MVP)

The upload's "Build Immediately" list (timeline, synod overlay, source-linked nodes, date/council filters, heatmap, synodal context query mode) lands entirely outside the current Phase 1 task cards. The "Defer Until Phase 2" and "Defer Until Phase 3" lists agree with the project's actual phasing.

### § 19. Final Acceptance Criteria

**Classification:** Mixed

Walking the 14 criteria:

| # | Criterion | Status |
|---|---|---|
| 1 | "Search a doctrine and see its development across time" | Deferred — Phase 2 timeline. |
| 2 | "Filter sources before or after a council" | Deferred — requires councils table + filter API. |
| 3 | "Click any visual node and inspect the underlying source text" | Aligned in principle (every citation is already inspectable per `<CitationPanel>` contract); the "visual node" part is Deferred. |
| 4 | "Platform clearly distinguishes source-backed claims from AI-inferred relationships" | **Already met in Phase 1.** Source-backed claims = `EvidencePacket` admitted; AI-inferred relationships are *not surfaced at all* per ADR 0006 rule 8 (stronger than the upload requires). |
| 5 | "System can show which Fathers influenced later Fathers" | Deferred — Phase 2 `lineage_edges`. |
| 6 | "System can show how a doctrine moved across geography and centuries" | Deferred — Phase 3. |
| 7 | "Theological categories visually, not only as lists" | Deferred — heatmap component. |
| 8 | "Compare original-language texts with English translations" | Deferred — Phase 2+ embedding work + aligned chunks. |
| 9 | "Every visualization remains source-grounded" | Already enforced by ADR 0001 rule 4. |
| 10 | "No graph relationship is displayed without a confidence label and explanatory basis" | Already enforced by ADR 0006 rules 4, 8. |
| 11 | "System distinguishes dogmatic consensus from private opinion" | Deferred — needs lineage edges + claim classification. |
| 12 | "System labels speculative relationships clearly" | **Stronger in current scope** — speculative relationships are suppressed entirely, not labeled (ADR 0006 rule 8). |
| 13 | "System can show synodal context before and after major councils" | Deferred — councils table + filter. |
| 14 | "Premium research experience that static libraries cannot easily replicate" | Aligned (positioning). |

### § 20. Final Positioning Statement

**Classification:** Aligned (vision)

The closing positioning matches AGENTS.md's product goal and the long-term ADR 0006 trajectory.

---

## Conflicts Catalog

Single-row summary of every Conflicts/Rejected classification with the canonical clause it collides with. Each row is a candidate for an explicit ADR amendment if the project decides to adopt that proposal element.

| Upload § | Issue | Collides with |
|---|---|---|
| § 5.5 | `POSSIBLE_INFLUENCE` edges with `display_warning` shown to end users | ADR 0001 rule 6; ADR 0006 rule 8 (candidate edges suppressed from user view) |
| § 7 | AI Graph Architect generates lineage edges at query time | AGENTS.md lines 48–57; ADR 0006 rules 3, 6, 7; ADR 0007 lines 13–22; AGENTS.md Known Gap #5 |
| § 7.4 | Per-query LLM-generated edges with confidence labels shown to users | ADR 0006 rules 3, 4, 5, 6, 7 |
| § 9 | "Phase 1" sequencing places timeline + heatmap + synod overlay before evidence pipeline | Phase 1 task cards T-001…T-007; phase1-implementation-contract.md exit criteria |
| § 11 (display rule) | "User can enable speculative links" opt-in toggle | ADR 0006 rule 8 (suppression is stricter than hidden-by-default) |
| § 13.1–13.5 | Timeline/Graph/Heatmap/Mirror/Map components as Phase 1 deliverables | `docs/contracts/frontend-components.md` lines 32–214 (no such components) |
| § 17 (backlog) | Epics 2–7 sequenced into MVP | Phase 1 task cards T-001…T-007 |
| § 18 (Build Immediately) | Timeline + heatmap + synodal context as first release | phase1-implementation-contract.md exit criteria |
| All | "Scholar Tier" pricing model | Business decision, not engineering; outside this audit's scope. Note: Stripe MVP meter is `served_answer_count` (AGENTS.md line 137); a tier model would require a separate billing ADR. |

---

## Harvest List

Concrete extractable elements worth promoting to future ADR drafts or schema additions. Each row names a single proposal element, the canonical destination it would land in, and the work it represents.

| # | Element (upload section) | Target canonical destination | Phase | Notes |
|---|---|---|---|---|
| H1 | Synod overlay markers on a chronological timeline (§ 4.1) | Future Phase-2 admin visualization. Not a user-facing surface in MVP. | 2 | Renders only approved metadata. Council list (Ecumenical I–VII + Palamite) is harvestable as a constants file. |
| H2 | Explicit-citation parser (§ 5.4) | Phase-2 ingestion pipeline → ADR 0006 `lineage_edges` with `relation_type='quotes'`, `extraction_method='regex'`/`'llm'`, `confidence`, `review_status='pending'`. | 2 | Output enters admin candidate-edge review queue. Never user-facing on detection. |
| H3 | Chunk-metadata enrichment fields (§ 5.3): `dateRange`, `century`, `location`, `ecclesiasticalStatus`, `sourceType`, `scriptureReferences`, `councilReferences`, `doctrinalConcepts`, `translationNotes` | `chunk.schema.json` extension proposal *or* ADR 0006 `chunk_entity_mentions` rows. Prefer the latter (normalized) over per-chunk denormalized fields. | 2 | Each field requires an approval workflow. |
| H4 | Node-type and edge-type enums (§ 6.3, § 6.4) | Phase-2 ADR extending ADR 0006 `graph_entities.entity_type` and `lineage_edges.relation_type` enums. | 2 | Existing ADR 0006 list: `quotes`, `references`, `builds_on`, `contrasts_with`, `same_passage_as`, `translation_of`, `paraphrases`, `supports`, `contested_by`. Upload adds 14+ more. |
| H5 | Theological category taxonomy (§ 4.3, 22 categories) | Non-binding reference (tenant chunk-tagging guidance). Could live in `docs/reference/` as a glossary file. | 1.5 | Already compatible with `chunk.categories` field; no schema change required. |
| H6 | Relation confidence enum (§ 11): `high | medium | low | speculative | disputed` | Phase-2 ADR addition to `lineage_edges` (ADR 0006 line 35 already includes `confidence score` as required). | 2 | Distinct from `confidenceTier` (evidence-coverage axis). No user-facing opt-in for speculative; admin review only. |
| H7 | Theological glossary seed list (§ 4.4 Greek term list) | Phase-2/3 lexicon reference. | 2–3 | Pairs with multilingual embedding work in ADR 0006 lines 70–80. |
| H8 | Councils metadata model (§ 8 + § 10) | New `councils` table proposal under ADR 0006 Phase-2 graph layer. Should join `lineage_edges`. | 2 | Initial seed: the 7 Ecumenical Councils + Palamite Councils (already enumerated in § 4.1 of upload). |
| H9 | Author normalization (§ 10) | ADR 0006 `graph_entities` of type `Author`. Existing `chunk.father` becomes a denormalized display field. | 2 | |
| H10 | Authority-weight signal (§ 12) | Phase-2 admin-derived enrichment on `graph_entities` (entity-type Author/Work). Inputs must themselves be approved metadata. | 2 | The 0.87/0.94 numerics in the upload are illustrative; derivation rules need their own ADR. |
| H11 | Risk safeguards list (§ 16) | Reference-by-link from any future Phase-2 graph ADR. Most items already encoded in ADR 0001/0002/0006. | 2 | Useful as a checklist for Phase-2 ADR review. |
| H12 | Synodal Context filter list (§ 8.3) | Phase-2 `/query` filter parameter proposal. | 2 | Requires H8 (councils) and H3 (date/century/topic metadata). |

---

## Note on the "Scholar Tier" pricing layer

The proposal frames its feature pack as a premium tier ("Scholar Tier") distinct from the base offering. This is a business decision, not an engineering one. AGENTS.md line 137 names the MVP Stripe meter as `served_answer_count`, and ADR 0005 specifies cache/billing rules for that single meter. A tiered offering would require:

1. A founder/business decision on tier structure.
2. A new ADR amending ADR 0005 to cover tier-based metering, gate logic, and entitlement checks.
3. Schema work on `tenant.config` and/or a new `tenants.tier` field.

None of that lies within this audit's scope. The current audit only flags that **adopting any of the engineering proposals does not require adopting the tier model**, and that the tier model would need its own decision path.

---

## What This Audit Does NOT Do

- It does not amend any ADR.
- It does not add fields to any schema.
- It does not modify any contract.
- It does not change any Phase 1 task card or exit criterion.
- It does not commit the source proposal file into the repo (the proposal remains in the upload sandbox at the path noted in the header).
- It does not make a business decision about a Scholar Tier pricing model.

It exists so that the founder + a future Phase-2 ADR author can pick items off the Harvest List with confidence about where each one collides or fits, without re-reading the 1,634-line upload from scratch.

---

## Related Canonical Sources

The classifications above cite the following files. Read these (not this audit) when implementing or deciding:

- `AGENTS.md`
- `docs/contracts/phase1-implementation-contract.md`
- `docs/contracts/frontend-components.md`
- `docs/contracts/db-schema.md`
- `docs/adr/0001-closed-corpus-contract.md`
- `docs/adr/0002-confidence-sensitivity-handling.md`
- `docs/adr/0006-pag-rag-lineage-architecture.md`
- `docs/adr/0007-query-transformation-boundaries.md`
- `docs/adr/0009-chunking-strategy.md`
- `docs/schemas/chunk.schema.json`
- `docs/schemas/source.schema.json`
- `docs/task_cards/phase1/T-006-admin-chat-safety-gate.md`
