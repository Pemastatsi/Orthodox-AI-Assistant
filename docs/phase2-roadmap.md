# Phase 2 Roadmap

Status: Canonical
Date: 2026-05-19

This document maps the Phase 2 rich-output feature set to implementation waves, pricing tiers, dependencies, and exit criteria. For architectural decisions, see ADRs 0013–0016. For detailed task specs, see `docs/task_cards/phase2/`.

---

## Prerequisite: Phase 1 Exit Criteria

All 9 Phase 1 exit criteria (defined in `docs/contracts/phase1-implementation-contract.md`) must pass before any Phase 2 wave begins. Key gates: safety suite stable for 14 days, RED rate ≤ 30%, tenant isolation invariant, founder Phase 2 signoff.

---

## Wave 2.0 — Foundation (ship first)

**Goal:** Deliver the five highest-ROI features to the initial 1,000 user cohort. Establish the provider abstraction and billing infrastructure all subsequent waves depend on.

| Task | Feature | Unique differentiator |
|---|---|---|
| T-101 | Markdown + Mermaid rich-text answers | Baseline parity with Claude/NotebookLM |
| T-102 | PDF + DOCX export of any answer | Immediate value for academic users |
| T-103 | Artifact provider abstraction + registry | Infrastructure; no user-visible feature |
| T-104 | Study Packet workflow | First LLM-composed document |
| T-105 | Patristic Lineage Graph | **Platform's unique differentiator — no competitor has this** |
| T-106 | Audio Overview (two-voice TTS) | NotebookLM-style; corpus-grounded |
| T-107 | Multi-meter billing | Revenue infrastructure |

**Dependencies:** T-102 before T-104; T-103 before T-105; T-107 can run in parallel with T-101–T-106.

**Wave 2.0 Exit Criteria:**
1. All 7 task acceptance tests pass.
2. `generated_artifact_count` and `audio_minutes_generated` Stripe meters reporting correctly.
3. Patristic Lineage Graph renders for the Orthodox Ethos tenant corpus.
4. Audio overview for a 300-word answer completes in < 90 seconds.
5. No cross-tenant artifact access in integration tests.

---

## Wave 2.1 — Visual Depth

**Goal:** Complete the Tier 2 visual artifact set and extend Tier 3 documents.

| Task | Feature |
|---|---|
| T-108 | Council Timeline |
| T-109 | Dispute Map |
| T-110 | Citation Network Graph |
| T-111 | Manuscript Witness Tree |
| T-112 | Slide Deck Export (PPTX + Marp) |
| T-113 | Sermon / Homily Builder |
| T-114 | Mind Map / Outline View |

**Dependencies:** T-105 (GraphRenderer certified) before T-108, T-109, T-110, T-111.

---

## Wave 2.2 — Orthodox-Unique Multimedia

**Goal:** Deliver the features with no competitor equivalent. Requires curated content sets (icons, chant audio, geographical GeoJSON) to be assembled by the content team in parallel with implementation.

| Task | Feature | Content prerequisite |
|---|---|---|
| T-115 | Bilingual Greek+English + Morphology | MorphGNT/CATSS offline datasets |
| T-116 | Liturgical Calendar Overlay | None (algorithm only) |
| T-117 | Iconographic Reference Cards | ≥ 20 curated icons with licenses |
| T-118 | Byzantine Chant Integration | ≥ 30 curated chant recordings with licenses |
| T-119 | Holy Land + Monastery Map | `orthodox_sites.geojson` curated dataset + self-hosted tiles |
| T-120 | Disputation Simulator | None (reuses Q&A pipeline) |

**Content team workstream (parallel):** Icon curation, chant licensing, GeoJSON dataset assembly, and self-hosted tile server setup must be completed before T-117, T-118, T-119 can be certified.

---

## Wave 2.3 — Workflow Library (Approval-Gated)

**Goal:** Institutional-grade document generation with human sign-off. Required for seminary, diocesan, and Orthodox Ethos enterprise contracts.

| Task | Feature | Approval required |
|---|---|---|
| T-121 | Bishop Briefing | Yes (establishes approval UI) |
| T-122 | Syllabus Bundle | Yes |
| T-123 | Catechism Lesson Plan | Yes |
| T-124 | Parish Bulletin Insert | Yes |
| T-125 | Feast-Day Bundle | Yes |

**Dependencies:** T-121 (approval workflow UI) before T-122–T-125. T-116, T-117, T-118 (multimedia data) before T-125.

---

## Pricing Tier Map

All features are available on all paid tiers. Volume caps per meter differentiate tiers.

| Tier | Monthly (EUR) | Q&A/month | Artifacts/month | Audio min/month | Target buyer |
|---|---|---|---|---|---|
| Free / Demo | €0 | 30 | 2 | 5 | Evaluation |
| **Scholar** | **€19** | 400 | 10 | 30 | Individual professors, clergy |
| **Parish** | **€59** | 2,000 | 50 | 120 | Parishes, small communities |
| **Seminary** | **€179** | 6,000 | 200 | 400 | Theology departments, seminaries |
| **Enterprise** | €600–1,500 custom | High | High | High | Orthodox Ethos, dioceses |

Annual option: 2 months free (recommended for academic/ecclesiastical buyers with annual budget cycles).

---

## Feature-to-Tier Eligibility Reference

No feature is tier-gated. All tiers above Free have access to all five output tiers (ADR 0015 Feature Parity Rule). The table below shows where caps become binding for typical usage patterns:

| Feature | Light user (Scholar) | Moderate (Parish) | Heavy (Seminary) |
|---|---|---|---|
| Q&A + rich text | 400/month (sufficient) | 2,000/month (sufficient) | 6,000/month (sufficient) |
| Study Packets, Sermon Outlines | 10/month (sufficient) | 50/month (sufficient) | 200/month (sufficient) |
| Slide Decks, Bishop Briefings | Shares artifact cap | Shares artifact cap | Shares artifact cap |
| Audio Overviews | 30 min (≈ 3 overviews) | 120 min (≈ 12 overviews) | 400 min (≈ 40 overviews) |

---

## Phase 2 → Phase 3 Exit Criteria

Phase 3 (multilingual, advanced PAG-RAG graph, Prometheus metrics, RLS, cross-provider failover) begins when:

1. All Wave 2.0 features are stable in production for 14 consecutive days.
2. At least one Enterprise tenant is using approval-gated Tier 3 workflows.
3. `generated_artifact_count` and `audio_minutes_generated` Stripe meters reporting correctly for ≥ 30 days.
4. No Tier 2 artifact (graph/timeline) provenance failures in the previous 14-day window.
5. Multimedia curated sets assembled: ≥ 50 icons, ≥ 100 chant recordings, complete `orthodox_sites.geojson` (all major patriarchates + Athhos + Holy Land sites).
6. Founder Phase 3 signoff recorded as `audit_entries` row with `action='founder_phase3_signoff'`.
