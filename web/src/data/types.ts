// Shared types for the Orthodox AI Assistant prototype.
// These are presentation-only — no backend, no persistence.

export type Tenant = {
  id: string;
  name: string;
  type: "seminary" | "diocese" | "monastery" | "publisher" | "parish";
  region: string;
  corpusVersion: string;
  policyScope: string;
};

export type Role = "admin" | "reviewer" | "scholar" | "clergy" | "member";

export type ApprovalState =
  | "candidate"
  | "approved"
  | "rejected"
  | "suppressed"
  | "admin_only"
  | "scholarly_only";

export type Visibility = "tenant" | "shared" | "scholarly_only" | "admin_only";

export type SourceType = "PDF" | "TXT" | "Markdown" | "DOCX" | "Audio" | "YouTube";

export type Source = {
  id: string;
  title: string;
  work: string;
  author: string;
  authorRole?: string; // e.g. "Church Father, 4th c."
  type: SourceType;
  language: string;
  approval: ApprovalState;
  visibility: Visibility;
  hash: string;
  embeddingModel: string;
  reviewer?: string;
  reviewNote?: string;
  pages?: number;
  uploadedAt: string;
  attestation: {
    extraction: "OCR" | "Native" | "Whisper" | "Manual";
    transcriptionConfidence?: number; // 0-1
    translationStatus: "original" | "translation" | "bilingual";
    quoteIntegrity: number; // 0-1
    parallelWitnesses: number;
    signedOff: boolean;
  };
};

export type Chunk = {
  id: string;
  sourceId: string;
  text: string;
  page?: number;
  timestamp?: string;
  depth: "introductory" | "intermediate" | "advanced";
  categories: string[];
  liturgicalPeriod?: string;
  hash: string;
  approval: ApprovalState;
  visibility: Visibility;
  reviewer?: string;
  reviewNote?: string;
};

export type Citation = {
  marker: number;
  sourceId: string;
  chunkId: string;
  excerpt: string;
  page?: number;
  classification: "exact" | "paraphrase" | "allusion" | "misattributed" | "unresolved";
  quoteIntegrity: number;
  approval: ApprovalState;
  // Optional display fields carried directly on live API citations (the mock data resolves
  // these from `sources`/`chunks` instead). Render sites prefer these when present.
  title?: string;
  author?: string;
  work?: string;
  chunkHash?: string;
};

export type ConfidenceTier = "high" | "moderate" | "low" | "insufficient";
export type Handling = "standard" | "reframed" | "blocked";

export type AnswerMode =
  | "direct_citation"
  | "consensus"
  | "historical_development"
  | "scholarly_dispute"
  | "institutional_policy";

export type ProgressStep =
  | "classified"
  | "retrieval_planned"
  | "vector_search"
  | "graph_expansion"
  | "evidence_admitted"
  | "answer_composed"
  | "citations_verified"
  | "policy_verified"
  | "ready";

export type Query = {
  id: string;
  question: string;
  mode: AnswerMode;
  scope: string;
  language: string;
  asked: string;
  asker: string;
  variant:
    | "verified_cited"
    | "consensus"
    | "historical_development"
    | "scholarly_dispute"
    | "institutional_policy"
    | "reframed_sensitive"
    | "insufficient_evidence"
    | "blocked_redirect";
  confidence: ConfidenceTier;
  handling: Handling;
  cached: boolean;
  body: string; // answer paragraph(s) with [n] markers
  citations: Citation[];
  evidence: {
    admittedChunks: number;
    suppressed: number;
    policyExclusions: number;
    coverage: number; // 0-1
  };
  trace: {
    classification: string;
    retrievalPlan: string;
    modelRoute: string;
    latencyMs: number;
    tokens: number;
    steps: ProgressStep[];
  };
  // for variants
  consensus?: { agreement: string[]; divergence: string[]; resolution?: string };
  timeline?: { period: string; century: string; event: string; sourceIds: string[] }[];
  positions?: { name: string; thesis: string; sourceIds: string[] }[];
  policy?: {
    scope: "universal" | "diocese" | "seminary" | "parish";
    node: string;
    effective: string;
    precedence: number;
  };
  reframed?: { original: string; reframed: string; reason: string };
  blocked?: { reason: string; redirect: string };
};

export type WorkflowKind =
  | "study_packet"
  | "bishop_briefing"
  | "feast_day_bundle"
  | "syllabus_bundle"
  | "catechism_guide"
  | "lecture_to_guide"
  | "parish_faq"
  | "content_brief";

export type WorkflowState =
  | "queued"
  | "running"
  | "waiting_for_evidence"
  | "pending_approval"
  | "approved"
  | "exported"
  | "failed";

export type WorkflowRun = {
  id: string;
  kind: WorkflowKind;
  title: string;
  owner: string;
  state: WorkflowState;
  coverage: number;
  citations: number;
  createdAt: string;
  approver?: string;
};

export type LineageRelation =
  | "quotes"
  | "references"
  | "builds_on"
  | "contrasts_with"
  | "same_passage_as"
  | "translation_of"
  | "paraphrases"
  | "supports"
  | "contested_by";

export type LineageEdge = {
  id: string;
  from: string;
  to: string;
  relation: LineageRelation;
  approved: boolean;
};

export type PolicyNode = {
  id: string;
  scope: "universal" | "diocese" | "seminary" | "monastery" | "parish";
  name: string;
  parent?: string;
  effective: string;
  precedence: number;
  description: string;
};

export type Member = {
  id: string;
  name: string;
  email: string;
  role: Role;
  active: boolean;
  joined: string;
  avatar?: string;
};

export type AuditEntry = {
  id: string;
  at: string;
  actor: string;
  action: string;
  target: string;
  detail?: string;
};

export type ModelRoute = {
  id: string;
  name: string;
  provider: string;
  model: string;
  purpose: "classification" | "retrieval" | "composition" | "verification";
  certified: boolean;
  inProduction: boolean;
  latencyP50: number;
  costPer1k: number;
};

export type Gap = {
  id: string;
  topic: string;
  reports: number;
  lastReported: string;
  suggestedSources: string[];
  assignedTo?: string;
  status: "open" | "in_progress" | "resolved";
};
