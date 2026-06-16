import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, PageBody, Section, Stat } from "@/components/page";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Plus,
  Workflow,
  Download,
  FileText,
  BookOpen,
  Calendar,
  GraduationCap,
  MessageSquare,
  Mic,
  FileEdit,
  ClipboardList,
} from "lucide-react";
import { workflows } from "@/data/mock";
import type { WorkflowKind, WorkflowState } from "@/data/types";

export const Route = createFileRoute("/_app/workflows")({
  component: Workflows,
});

const ICON: Record<WorkflowKind, React.ComponentType<{ className?: string }>> = {
  study_packet: BookOpen,
  bishop_briefing: ClipboardList,
  feast_day_bundle: Calendar,
  syllabus_bundle: GraduationCap,
  catechism_guide: FileText,
  lecture_to_guide: Mic,
  parish_faq: MessageSquare,
  content_brief: FileEdit,
};

const STATE_TONE: Record<WorkflowState, string> = {
  queued: "border-border bg-muted text-muted-foreground",
  running: "border-info/30 bg-info-soft text-info",
  waiting_for_evidence: "border-warning/40 bg-warning-soft text-warning-foreground",
  pending_approval: "border-gold/30 bg-gold-soft text-gold-foreground",
  approved: "border-success/30 bg-success-soft text-success",
  exported: "border-primary/30 bg-primary-soft text-primary",
  failed: "border-danger/40 bg-danger-soft text-danger",
};

const CATALOG: { kind: WorkflowKind; title: string; desc: string }[] = [
  {
    kind: "study_packet",
    title: "Study Packet",
    desc: "Reading + question packet for catechumens or parish groups.",
  },
  {
    kind: "bishop_briefing",
    title: "Bishop Briefing",
    desc: "Concise theological brief on a current question.",
  },
  {
    kind: "feast_day_bundle",
    title: "Feast-Day Bundle",
    desc: "Texts, hymnography, homiletic notes for a feast.",
  },
  {
    kind: "syllabus_bundle",
    title: "Syllabus Bundle",
    desc: "Structured course materials with citations.",
  },
  { kind: "catechism_guide", title: "Catechism Guide", desc: "Catechumen-facing teaching guide." },
  {
    kind: "lecture_to_guide",
    title: "Lecture-to-Guide",
    desc: "Convert a lecture transcript into a reading guide.",
  },
  {
    kind: "parish_faq",
    title: "Parish FAQ Draft",
    desc: "Bounded FAQ generation from approved sources.",
  },
  {
    kind: "content_brief",
    title: "Content Brief",
    desc: "Evidence-backed brief for editorial teams.",
  },
];

function Workflows() {
  return (
    <>
      <PageHeader
        title="Workflows"
        description="Bounded, corpus-safe institutional outputs. Every artifact passes coverage and approval before publication."
        actions={
          <Button size="sm" className="gap-1.5">
            <Plus className="h-3.5 w-3.5" /> New workflow run
          </Button>
        }
      />
      <PageBody className="space-y-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat
            label="Active runs"
            value={
              workflows.filter((w) =>
                ["running", "queued", "waiting_for_evidence"].includes(w.state),
              ).length
            }
          />
          <Stat
            label="Pending approval"
            value={workflows.filter((w) => w.state === "pending_approval").length}
            tone="gold"
          />
          <Stat label="Exported (30d)" value={12} tone="success" />
          <Stat label="Failed" value={1} tone="danger" />
        </div>

        <Section title="Catalog">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {CATALOG.map((c) => {
              const Icon = ICON[c.kind];
              return (
                <button
                  key={c.kind}
                  className="flex flex-col items-start gap-2 rounded-lg border border-border bg-card p-3 text-left transition hover:border-primary hover:shadow-sm"
                >
                  <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary-soft text-primary">
                    <Icon className="h-4 w-4" />
                  </span>
                  <div>
                    <div className="font-serif text-sm font-semibold">{c.title}</div>
                    <div className="mt-0.5 text-xs text-muted-foreground">{c.desc}</div>
                  </div>
                </button>
              );
            })}
          </div>
        </Section>

        <Section title="Recent runs">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-[10px] uppercase tracking-wider text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">Run</th>
                  <th className="py-2 pr-3 font-medium">Owner</th>
                  <th className="py-2 pr-3 font-medium">State</th>
                  <th className="py-2 pr-3 font-medium">Coverage</th>
                  <th className="py-2 pr-3 font-medium">Citations</th>
                  <th className="py-2 pr-3 font-medium">Approver</th>
                  <th className="py-2 pr-3 font-medium">Created</th>
                  <th className="py-2 font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {workflows.map((w) => {
                  const Icon = ICON[w.kind];
                  return (
                    <tr key={w.id} className="hover:bg-accent/30">
                      <td className="py-2.5 pr-3">
                        <div className="flex items-center gap-2">
                          <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                          <span className="font-medium">{w.title}</span>
                        </div>
                      </td>
                      <td className="py-2.5 pr-3 text-xs text-muted-foreground">{w.owner}</td>
                      <td className="py-2.5 pr-3">
                        <span
                          className={`inline-flex rounded-md border px-1.5 py-0.5 text-[10px] font-medium capitalize ${STATE_TONE[w.state]}`}
                        >
                          {w.state.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td className="py-2.5 pr-3">
                        <div className="flex items-center gap-2">
                          <Progress value={w.coverage * 100} className="h-1 w-24" />
                          <span className="tabular text-xs">{Math.round(w.coverage * 100)}%</span>
                        </div>
                      </td>
                      <td className="py-2.5 pr-3 tabular text-xs">{w.citations}</td>
                      <td className="py-2.5 pr-3 text-xs text-muted-foreground">
                        {w.approver ?? "—"}
                      </td>
                      <td className="py-2.5 pr-3 font-mono text-xs text-muted-foreground">
                        {w.createdAt}
                      </td>
                      <td className="py-2.5 text-right">
                        <Button variant="ghost" size="sm" className="h-7 gap-1.5 text-xs">
                          <Download className="h-3 w-3" /> Open
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Section>

        <Section title="Active run — Patristics 201 Syllabus" description="Run progress timeline">
          <ol className="relative space-y-3 border-l border-border pl-4">
            {[
              { t: "Queued", state: "done" },
              { t: "Running — corpus retrieval", state: "done" },
              { t: "Waiting for evidence (3 chunks below threshold)", state: "active" },
              { t: "Composition", state: "todo" },
              { t: "Citation verification", state: "todo" },
              { t: "Pending approval (Dean)", state: "todo" },
              { t: "Exported", state: "todo" },
            ].map((s, i) => (
              <li key={i} className="relative">
                <span
                  className={`absolute -left-[19px] flex h-3 w-3 rounded-full ring-4 ring-background ${
                    s.state === "done"
                      ? "bg-success"
                      : s.state === "active"
                        ? "bg-warning animate-pulse"
                        : "bg-muted"
                  }`}
                />
                <div className="text-sm">{s.t}</div>
              </li>
            ))}
          </ol>
        </Section>
      </PageBody>
    </>
  );
}
