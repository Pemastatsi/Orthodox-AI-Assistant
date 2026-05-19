# T-105: Patristic Lineage Graph

## Goal

Implement the Patristic Lineage Graph artifact: an interactive D3.js force-directed graph showing doctrinal influence relationships between fathers, works, concepts, and councils. This is the platform's unique differentiator — no competitor offers a provenance-backed, corpus-grounded theological influence graph. LLM composition assembles node and edge data from the evidence packet; D3.js renders it client-side. Citation popovers are mandatory on every node.

## Required Reads

- [`docs/contracts/artifact-provider-interface.md`](../../contracts/artifact-provider-interface.md) — `GraphRenderer` protocol.
- [`docs/schemas/lineage-graph.schema.json`](../../schemas/lineage-graph.schema.json) — target output schema.
- [`docs/adr/0013-rich-output-format-strategy.md`](../../adr/0013-rich-output-format-strategy.md) — Tier 2 visual artifact rules.
- [`docs/adr/0006-pag-rag-lineage-architecture.md`](../../adr/0006-pag-rag-lineage-architecture.md) — graph metadata architecture; only approved edges.
- [`docs/contracts/workflow-orchestration-contract.md`](../../contracts/workflow-orchestration-contract.md) — pipeline stages.
- [`docs/contracts/rich-output-rendering.md`](../../contracts/rich-output-rendering.md) — `<LineageGraphView>` component contract.

## Files In Scope

**Backend:**
- `backend/app/adapters/artifact_providers/graph/d3_adapter.py` — implement `GraphRenderer`; replaces the stub from T-103; packages `LineageGraphArtifact` as JSON for client-side D3 rendering.
- `backend/app/domain/services/lineage_graph_composer.py` — A5-class LLM composition: extracts Person/Work/Concept/Council nodes and edge types from the evidence packet; outputs `LineageGraphArtifact` JSON validated against `lineage-graph.schema.json`.
- `backend/app/domain/services/artifact_service.py` — extend to handle `lineage_graph` artifact type routing.
- `docs/schemas/lineage-graph.schema.json` — (already exists; no changes needed).
- `.env.example` — `ACTIVE_ARTIFACT_ROUTE_GRAPH`, `ACTIVE_MODEL_ROUTE_ARTIFACT_COMPOSE_LINEAGE`.

**Frontend:**
- `web/components/artifacts/LineageGraphView.tsx` — D3 force-directed graph; interactive nodes (click → entity detail drawer); edge citation popovers on hover; pan/zoom.
- `web/components/artifacts/EntityDetailDrawer.tsx` — node detail panel showing entity description, tradition, century, and all associated citations.
- `package.json` — add `d3` (and types).

## Acceptance Tests

1. `POST /artifacts` with `artifactType='lineage_graph'` and a valid evidence packet containing patristic data produces a `LineageGraphArtifact`.
2. The graph JSON validates against `lineage-graph.schema.json`.
3. Every node has at least one `citationRef` pointing to an admitted chunk.
4. Every edge has at least one `citationRef`.
5. No `lineage_graph` artifact contains edges derived from unapproved graph metadata (ADR 0006 rule; verified by checking `run_traces` for the source run).
6. `<LineageGraphView>` renders in a browser without console errors; nodes are clickable; entity drawer opens with citation links.
7. Citation popover on an edge shows the quoted text from the evidence chunk.
8. `provenance.allClaimsVerified=true` on the artifact.
9. Graph with `admittedChunkCount < 5` fails with `insufficient_evidence_coverage`.
10. `D3Adapter` route certified with `certification_status='certified'`; startup accepts it.

## Forbidden Scope

- Using unapproved candidate graph edges from the PAG-RAG system (ADR 0006: approved edges only).
- Neo4j or external graph database (vector-first per AGENTS.md).
- AI-generated node thumbnails or illustrations.
- Cross-tenant graph data.
