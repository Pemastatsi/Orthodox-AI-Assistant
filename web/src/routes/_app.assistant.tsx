import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { PageHeader } from "@/components/page";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  Send,
  Sparkles,
  Quote,
  Layers,
  Network,
  Activity,
  CheckCircle2,
  AlertTriangle,
  Ban,
  Clock,
  CircleDashed,
  ShieldCheck,
  Database,
  ChevronRight,
  History,
  CornerDownRight,
  Loader2,
} from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { sources, chunks } from "@/data/mock";
import type { Query, Citation, AnswerMode } from "@/data/types";
import { cn } from "@/lib/utils";
import { postQuery } from "@/lib/api";
import { toQuery } from "@/lib/adapt";

export const Route = createFileRoute("/_app/assistant")({
  component: AssistantWorkbench,
});

function findSource(id: string) {
  return sources.find((s) => s.id === id);
}
function findChunk(id: string) {
  return chunks.find((c) => c.id === id);
}

function AssistantWorkbench() {
  const [mode, setMode] = useState<AnswerMode>("direct_citation");
  const [text, setText] = useState("");
  const [conversation, setConversation] = useState<Query[]>([]);
  const [active, setActive] = useState<Query | null>(null);
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async (input: { queryText: string; mode: AnswerMode }) => {
      const startedAt = performance.now();
      const resp = await postQuery(input.queryText);
      return toQuery(resp, {
        question: input.queryText,
        mode: input.mode,
        scope: "Tenant corpus only",
        language: "en",
        asker: "You",
        latencyMs: Math.round(performance.now() - startedAt),
      });
    },
    onSuccess: (q) => {
      setActive(q);
      setConversation((prev) => [q, ...prev]);
      setPendingQuestion(null);
    },
  });

  function submit() {
    const queryText = text.trim();
    if (!queryText || mutation.isPending) return;
    setActive(null);
    setPendingQuestion(queryText);
    mutation.mutate({ queryText, mode });
    setText("");
  }

  function newConversation() {
    mutation.reset();
    setActive(null);
    setPendingQuestion(null);
  }

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col">
      <PageHeader
        title="Assistant Workbench"
        description="Closed-corpus theological assistant. Every answer traceable to approved evidence."
        badges={
          <Badge
            variant="outline"
            className="ml-2 gap-1.5 border-success/40 bg-success-soft text-success"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-success" /> Verified routes
          </Badge>
        }
        actions={
          <>
            <Button variant="ghost" size="sm" className="gap-1.5">
              <History className="h-3.5 w-3.5" /> Session history
            </Button>
            <Button size="sm" className="gap-1.5" onClick={newConversation}>
              <Sparkles className="h-3.5 w-3.5" /> New conversation
            </Button>
          </>
        }
      />

      <div className="grid min-h-0 flex-1 grid-cols-12 gap-0">
        {/* Left: thread navigator */}
        <aside className="col-span-12 hidden border-r border-border bg-surface-muted lg:col-span-2 lg:block">
          <div className="border-b border-border px-3 py-2 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            Recent
          </div>
          {conversation.length === 0 ? (
            <div className="px-3 py-4 text-[11px] leading-relaxed text-muted-foreground">
              No queries yet. Ask from the approved library to begin.
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {conversation.slice(0, 8).map((q) => (
                <li key={q.id}>
                  <button
                    onClick={() => setActive(q)}
                    className={cn(
                      "block w-full px-3 py-2.5 text-left transition-colors hover:bg-accent/50",
                      active?.id === q.id && "bg-accent",
                    )}
                  >
                    <div className="line-clamp-2 text-xs leading-snug">{q.question}</div>
                    <div className="mt-1 flex items-center gap-1 text-[10px] text-muted-foreground">
                      <ConfidenceDot c={q.confidence} />
                      <span className="capitalize">{q.mode.replace(/_/g, " ")}</span>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        {/* Center: conversation + composer */}
        <section className="col-span-12 flex min-h-0 flex-col lg:col-span-7">
          <div className="flex-1 overflow-auto bg-background">
            <div className="mx-auto max-w-3xl px-6 py-6">
              {mutation.isPending && pendingQuestion ? (
                <PendingView question={pendingQuestion} mode={mode} />
              ) : mutation.isError ? (
                <>
                  {pendingQuestion && <QuestionBubble question={pendingQuestion} mode={mode} />}
                  <ErrorCard error={mutation.error} />
                </>
              ) : active ? (
                <>
                  <UserBubble query={active} />
                  <ProgressTrace query={active} />
                  <AnswerCard query={active} />
                </>
              ) : (
                <EmptyState />
              )}
            </div>
          </div>
          <Composer
            mode={mode}
            setMode={setMode}
            text={text}
            setText={setText}
            onSubmit={submit}
            pending={mutation.isPending}
          />
        </section>

        {/* Right: tabs panel */}
        <aside className="col-span-12 border-t border-border bg-surface lg:col-span-3 lg:border-l lg:border-t-0">
          {active ? (
            <RightPanel query={active} />
          ) : (
            <div className="p-4 text-center text-xs leading-relaxed text-muted-foreground">
              Citations, evidence, lineage and the run trace appear here after you ask a question.
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

/* ---------------- Live-chat states ---------------- */

function QuestionBubble({ question, mode }: { question: string; mode: AnswerMode }) {
  return (
    <div className="mb-4 flex items-start gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
        You
      </div>
      <div className="flex-1 rounded-lg border border-border bg-surface p-3">
        <div className="text-[11px] text-muted-foreground">
          You · just now · <span className="capitalize">{mode.replace(/_/g, " ")}</span>
        </div>
        <div className="mt-1 text-sm">{question}</div>
      </div>
    </div>
  );
}

function PendingView({ question, mode }: { question: string; mode: AnswerMode }) {
  return (
    <>
      <QuestionBubble question={question} mode={mode} />
      <div className="mb-4 flex items-center gap-2 rounded-lg border border-border bg-surface-muted px-3 py-2.5 text-[11px] text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
        Verifying against approved evidence…
      </div>
    </>
  );
}

function ErrorCard({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div className="rounded-lg border border-danger/40 bg-card">
      <div className="flex items-start gap-2 p-4">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-danger" />
        <div>
          <div className="font-medium text-danger">Request failed</div>
          <p className="mt-1 text-sm text-muted-foreground">{message}</p>
          <p className="mt-2 text-[11px] text-muted-foreground">
            Confirm the backend is running on <span className="font-mono">:8000</span> — the dev
            server proxies <span className="font-mono">/api</span> to it.
          </p>
        </div>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center py-24 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
        <Sparkles className="h-6 w-6 text-primary" />
      </div>
      <h3 className="mt-4 font-serif text-lg font-semibold">Ask from the approved library</h3>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">
        Every answer is composed only from approved corpus evidence and returned with verifiable
        citations.
      </p>
    </div>
  );
}

/* ---------------- Pieces ---------------- */

function ConfidenceDot({ c }: { c: Query["confidence"] }) {
  const tone =
    c === "high"
      ? "bg-success"
      : c === "moderate"
        ? "bg-info"
        : c === "low"
          ? "bg-warning"
          : "bg-danger";
  return <span className={cn("h-1.5 w-1.5 rounded-full", tone)} />;
}

function UserBubble({ query }: { query: Query }) {
  return (
    <div className="mb-4 flex items-start gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
        JB
      </div>
      <div className="flex-1 rounded-lg border border-border bg-surface p-3">
        <div className="text-[11px] text-muted-foreground">
          {query.asker} · {query.asked} ·{" "}
          <span className="capitalize">{query.mode.replace(/_/g, " ")}</span> · {query.scope}
        </div>
        <div className="mt-1 text-sm">{query.question}</div>
      </div>
    </div>
  );
}

const STEP_LABEL: Record<string, string> = {
  classified: "Classified",
  retrieval_planned: "Retrieval planned",
  vector_search: "Vector search complete",
  graph_expansion: "Graph expansion checked",
  evidence_admitted: "Evidence admitted",
  answer_composed: "Answer composed",
  citations_verified: "Citations verified",
  policy_verified: "Policy verified",
  ready: "Ready",
};

function ProgressTrace({ query }: { query: Query }) {
  return (
    <div className="mb-4 rounded-lg border border-border bg-surface-muted px-3 py-2.5">
      <div className="mb-2 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        <Activity className="h-3 w-3" /> Verification trace
      </div>
      <ol className="flex flex-wrap items-center gap-x-1 gap-y-1.5">
        {query.trace.steps.map((s, i) => {
          const last = i === query.trace.steps.length - 1;
          return (
            <li key={s} className="flex items-center gap-1">
              <span className="inline-flex items-center gap-1 rounded-md border border-success/30 bg-success-soft px-1.5 py-0.5 text-[10px] text-success">
                <CheckCircle2 className="h-2.5 w-2.5" />
                {STEP_LABEL[s]}
              </span>
              {!last && <ChevronRight className="h-3 w-3 text-muted-foreground/50" />}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function AnswerCard({ query }: { query: Query }) {
  switch (query.variant) {
    case "verified_cited":
      return <VerifiedCard query={query} />;
    case "consensus":
      return <ConsensusCard query={query} />;
    case "historical_development":
      return <TimelineCard query={query} />;
    case "scholarly_dispute":
      return <DisputeCard query={query} />;
    case "institutional_policy":
      return <PolicyCard query={query} />;
    case "reframed_sensitive":
      return <ReframedCard query={query} />;
    case "insufficient_evidence":
      return <InsufficientCard query={query} />;
    case "blocked_redirect":
      return <BlockedCard query={query} />;
  }
}

function CardShell({
  tone = "default",
  banner,
  children,
  query,
  hideMeta,
}: {
  tone?: "default" | "warning" | "danger";
  banner?: React.ReactNode;
  children: React.ReactNode;
  query: Query;
  hideMeta?: boolean;
}) {
  const border =
    tone === "warning"
      ? "border-warning/40"
      : tone === "danger"
        ? "border-danger/40"
        : "border-border";
  return (
    <div className={cn("rounded-lg border bg-card", border)}>
      {banner}
      <div className="space-y-3 p-4">
        {!hideMeta && (
          <div className="flex flex-wrap items-center gap-1.5">
            <Chip tone="primary" icon={ShieldCheck}>
              Verified
            </Chip>
            <Chip
              tone={
                query.confidence === "high"
                  ? "success"
                  : query.confidence === "moderate"
                    ? "info"
                    : "warning"
              }
            >
              {query.confidence} confidence
            </Chip>
            <Chip>{query.handling}</Chip>
            {query.cached && <Chip tone="gold">served from cache</Chip>}
            <span className="ml-auto text-[11px] text-muted-foreground">
              {Math.round(query.evidence.coverage * 100)}% evidence coverage ·{" "}
              {query.evidence.admittedChunks} chunks
            </span>
          </div>
        )}
        {children}
      </div>
    </div>
  );
}

function Chip({
  children,
  tone = "default",
  icon: Icon,
}: {
  children: React.ReactNode;
  tone?: "default" | "primary" | "success" | "info" | "warning" | "danger" | "gold";
  icon?: React.ComponentType<{ className?: string }>;
}) {
  const map = {
    default: "border-border bg-muted text-muted-foreground",
    primary: "border-primary/30 bg-primary-soft text-primary",
    success: "border-success/30 bg-success-soft text-success",
    info: "border-info/30 bg-info-soft text-info",
    warning: "border-warning/40 bg-warning-soft text-warning-foreground",
    danger: "border-danger/40 bg-danger-soft text-danger",
    gold: "border-gold/30 bg-gold-soft text-gold-foreground",
  } as const;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-medium capitalize",
        map[tone],
      )}
    >
      {Icon && <Icon className="h-2.5 w-2.5" />}
      {children}
    </span>
  );
}

function CitationMarker({ n }: { n: number }) {
  return (
    <button className="citation-marker mx-0.5 inline-flex h-4 min-w-[18px] items-center justify-center rounded bg-gold-soft px-1 text-[10px] hover:bg-gold/30">
      [{n}]
    </button>
  );
}

function renderBody(body: string) {
  // Render [n] markers as styled buttons
  const parts = body.split(/(\[\d+\])/g);
  return parts.map((p, i) => {
    const m = p.match(/^\[(\d+)\]$/);
    if (m) return <CitationMarker key={i} n={parseInt(m[1])} />;
    // Render *italics*
    const sub = p.split(/(\*[^*]+\*)/g);
    return (
      <span key={i}>
        {sub.map((s, j) =>
          s.startsWith("*") && s.endsWith("*") ? (
            <em key={j} className="font-serif italic">
              {s.slice(1, -1)}
            </em>
          ) : (
            s
          ),
        )}
      </span>
    );
  });
}

function VerifiedCard({ query }: { query: Query }) {
  return (
    <CardShell query={query}>
      <p className="text-[15px] leading-relaxed text-foreground">{renderBody(query.body)}</p>
      <div className="border-t border-border pt-3">
        <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          Source coverage
        </div>
        <div className="flex flex-wrap gap-1.5">
          {query.citations.map((c) => {
            const s = findSource(c.sourceId);
            const title = c.title ?? s?.title;
            const author = c.author ?? s?.author;
            return (
              <span
                key={c.marker}
                className="inline-flex items-center gap-1.5 rounded-md border border-gold/30 bg-gold-soft/60 px-2 py-1 text-[11px]"
              >
                <Quote className="h-3 w-3 text-gold-foreground" />
                <span className="font-medium">{title}</span>
                {author && <span className="text-muted-foreground">· {author}</span>}
              </span>
            );
          })}
        </div>
      </div>
    </CardShell>
  );
}

function ConsensusCard({ query }: { query: Query }) {
  return (
    <CardShell query={query}>
      <p className="text-[15px] leading-relaxed">{renderBody(query.body)}</p>
      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-md border border-success/30 bg-success-soft/40 p-3">
          <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-success">
            Agreement
          </div>
          <ul className="space-y-1 text-sm">
            {query.consensus?.agreement.map((a) => (
              <li key={a} className="flex gap-1.5">
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" /> {a}
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-md border border-warning/40 bg-warning-soft/40 p-3">
          <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-warning-foreground">
            Divergence
          </div>
          <ul className="space-y-1 text-sm">
            {query.consensus?.divergence.map((a) => (
              <li key={a} className="flex gap-1.5">
                <CornerDownRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" /> {a}
              </li>
            ))}
          </ul>
        </div>
      </div>
      {query.consensus?.resolution && (
        <div className="rounded-md border border-primary/30 bg-primary-soft/60 p-3 text-sm">
          <div className="mb-0.5 text-[10px] font-medium uppercase tracking-wider text-primary">
            Conciliar resolution
          </div>
          {query.consensus.resolution}
        </div>
      )}
    </CardShell>
  );
}

function TimelineCard({ query }: { query: Query }) {
  return (
    <CardShell query={query}>
      <p className="text-[15px] leading-relaxed">{renderBody(query.body)}</p>
      <ol className="relative space-y-3 border-l border-border pl-4">
        {query.timeline?.map((e) => (
          <li key={e.period} className="relative">
            <span className="absolute -left-[19px] flex h-3 w-3 items-center justify-center rounded-full bg-primary ring-4 ring-background" />
            <div className="flex items-baseline gap-2">
              <span className="font-serif text-base font-semibold">{e.period}</span>
              <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                {e.century} AD
              </span>
            </div>
            <p className="mt-0.5 text-sm text-muted-foreground">{e.event}</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {e.sourceIds.map((sid) => (
                <span key={sid} className="text-[10px] text-gold-foreground">
                  · {findSource(sid)?.author}
                </span>
              ))}
            </div>
          </li>
        ))}
      </ol>
    </CardShell>
  );
}

function DisputeCard({ query }: { query: Query }) {
  return (
    <CardShell query={query}>
      <p className="text-[15px] leading-relaxed">{renderBody(query.body)}</p>
      <div className="grid gap-3 md:grid-cols-2">
        {query.positions?.map((p, i) => (
          <div key={p.name} className="rounded-md border border-border bg-surface-muted p-3">
            <div className="mb-1 flex items-center gap-1.5">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
                {String.fromCharCode(65 + i)}
              </span>
              <h4 className="font-serif text-sm font-semibold">{p.name}</h4>
            </div>
            <p className="text-sm">{p.thesis}</p>
            <div className="mt-2 flex flex-wrap gap-1">
              {p.sourceIds.map((sid) => (
                <span
                  key={sid}
                  className="rounded border border-gold/30 bg-gold-soft px-1.5 py-0.5 text-[10px]"
                >
                  {findSource(sid)?.author}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="rounded-md border border-warning/40 bg-warning-soft/40 px-3 py-2 text-xs text-warning-foreground">
        Contested area — both positions remain within Orthodox theological discourse.
      </div>
    </CardShell>
  );
}

function PolicyCard({ query }: { query: Query }) {
  return (
    <CardShell query={query}>
      <p className="text-[15px] leading-relaxed">{renderBody(query.body)}</p>
      <div className="grid gap-2 rounded-md border border-primary/30 bg-primary-soft/40 p-3 text-sm md:grid-cols-3">
        <div>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Scope</div>
          <div className="font-medium capitalize">{query.policy?.scope}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Policy node
          </div>
          <div className="font-medium">{query.policy?.node}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Effective
          </div>
          <div className="font-mono text-xs">{query.policy?.effective}</div>
        </div>
      </div>
    </CardShell>
  );
}

function ReframedCard({ query }: { query: Query }) {
  return (
    <CardShell
      query={query}
      tone="warning"
      banner={
        <div className="flex items-start gap-2 border-b border-warning/40 bg-warning-soft/60 px-4 py-2.5 text-sm text-warning-foreground">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <div className="font-medium">Sensitive query — reframed for safe handling.</div>
            <div className="text-xs opacity-80">
              Personal pastoral counsel is outside this assistant's scope. Original query was
              redacted from the public log.
            </div>
          </div>
        </div>
      }
    >
      <div className="grid gap-2 rounded-md bg-muted p-3 text-sm">
        <div>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Original (redacted)
          </span>
          <div className="text-foreground">{query.reframed?.original}</div>
        </div>
        <div>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Reframed teaching question
          </span>
          <div className="font-medium">{query.reframed?.reframed}</div>
        </div>
      </div>
      <p className="text-[15px] leading-relaxed">{renderBody(query.body)}</p>
    </CardShell>
  );
}

function InsufficientCard({ query }: { query: Query }) {
  return (
    <CardShell query={query} tone="danger" hideMeta>
      <div className="flex items-start gap-2">
        <CircleDashed className="mt-0.5 h-5 w-5 shrink-0 text-danger" />
        <div className="flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <Chip tone="danger" icon={AlertTriangle}>
              Insufficient evidence
            </Chip>
            <Chip tone="danger">Confidence: {query.confidence}</Chip>
          </div>
          <p className="mt-2 text-[15px]">{query.body}</p>
          <div className="mt-3 flex gap-2">
            <Button size="sm" variant="outline" className="gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5" /> Flag as corpus gap
            </Button>
            <Button size="sm" variant="ghost">
              Suggest a source
            </Button>
          </div>
        </div>
      </div>
    </CardShell>
  );
}

function BlockedCard({ query }: { query: Query }) {
  return (
    <CardShell query={query} tone="danger" hideMeta>
      <div className="flex items-start gap-2">
        <Ban className="mt-0.5 h-5 w-5 shrink-0 text-danger" />
        <div className="flex-1">
          <div className="flex items-center gap-1.5">
            <Chip tone="danger" icon={Ban}>
              Blocked at safety gate
            </Chip>
          </div>
          <div className="mt-2 text-sm">
            <span className="font-medium">Reason: </span>
            {query.blocked?.reason}
          </div>
          <div className="mt-2 rounded-md border border-info/30 bg-info-soft/40 p-3 text-sm">
            <div className="mb-0.5 text-[10px] uppercase tracking-wider text-info">
              Suggested redirect
            </div>
            {query.blocked?.redirect}
          </div>
        </div>
      </div>
    </CardShell>
  );
}

/* ---------------- Composer ---------------- */

const MODES = [
  { value: "direct_citation", label: "Direct citation" },
  { value: "consensus", label: "Consensus" },
  { value: "historical_development", label: "Historical development" },
  { value: "scholarly_dispute", label: "Scholarly dispute" },
  { value: "institutional_policy", label: "Institutional policy" },
];

const SCOPES = [
  "Tenant corpus only",
  "Tenant + approved shared corpus",
  "Scholarly-only sources",
  "Institutional policy scope",
];

function Composer({
  mode,
  setMode,
  text,
  setText,
  onSubmit,
  pending,
}: {
  mode: AnswerMode;
  setMode: (m: AnswerMode) => void;
  text: string;
  setText: (s: string) => void;
  onSubmit: () => void;
  pending: boolean;
}) {
  return (
    <div className="border-t border-border bg-surface px-4 py-3">
      <div className="mx-auto max-w-3xl">
        <div className="mb-2 flex flex-wrap items-center gap-1.5">
          <Select value={mode} onValueChange={(v) => setMode(v as AnswerMode)}>
            <SelectTrigger className="h-7 w-auto border-dashed text-xs">
              <Sparkles className="mr-1 h-3 w-3 text-primary" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MODES.map((m) => (
                <SelectItem key={m.value} value={m.value}>
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select defaultValue={SCOPES[0]}>
            <SelectTrigger className="h-7 w-auto border-dashed text-xs">
              <Database className="mr-1 h-3 w-3" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SCOPES.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select defaultValue="en">
            <SelectTrigger className="h-7 w-auto border-dashed text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="en">English</SelectItem>
              <SelectItem value="el">Ελληνικά</SelectItem>
              <SelectItem value="ru">Русский</SelectItem>
              <SelectItem value="ro">Română</SelectItem>
            </SelectContent>
          </Select>
          <span className="ml-auto inline-flex items-center gap-1 text-[10px] text-muted-foreground">
            <Clock className="h-3 w-3" /> Session memory: 4 turns
          </span>
        </div>
        <div className="flex items-end gap-2 rounded-lg border border-border bg-background p-2 focus-within:border-primary">
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSubmit();
              }
            }}
            placeholder="Ask from the approved library…"
            className="min-h-[40px] resize-none border-0 bg-transparent px-2 py-1.5 text-sm shadow-none focus-visible:ring-0"
            rows={1}
          />
          <Button
            size="sm"
            className="gap-1.5"
            onClick={onSubmit}
            disabled={pending || text.trim().length === 0}
          >
            {pending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Send className="h-3.5 w-3.5" />
            )}{" "}
            Ask
          </Button>
        </div>
        <p className="mt-1 text-[10px] text-muted-foreground">
          No open-web retrieval. Answers compose only after citation and policy verification pass.
        </p>
      </div>
    </div>
  );
}

/* ---------------- Right Panel ---------------- */

function RightPanel({ query }: { query: Query }) {
  return (
    <Tabs defaultValue="citations" className="flex h-full flex-col">
      <TabsList className="m-2 grid grid-cols-4 bg-muted">
        <TabsTrigger value="citations" className="gap-1 text-xs">
          <Quote className="h-3 w-3" /> Cite
        </TabsTrigger>
        <TabsTrigger value="evidence" className="gap-1 text-xs">
          <Layers className="h-3 w-3" /> Evidence
        </TabsTrigger>
        <TabsTrigger value="lineage" className="gap-1 text-xs">
          <Network className="h-3 w-3" /> Lineage
        </TabsTrigger>
        <TabsTrigger value="trace" className="gap-1 text-xs">
          <Activity className="h-3 w-3" /> Trace
        </TabsTrigger>
      </TabsList>

      <div className="flex-1 overflow-auto px-3 pb-4">
        <TabsContent value="citations" className="mt-0 space-y-2.5">
          {query.citations.length === 0 && (
            <div className="rounded-md border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
              No citations — answer was not composed.
            </div>
          )}
          {query.citations.map((c) => (
            <CitationItem key={c.marker} c={c} />
          ))}
        </TabsContent>
        <TabsContent value="evidence" className="mt-0 space-y-2.5">
          <EvidencePacket query={query} />
        </TabsContent>
        <TabsContent value="lineage" className="mt-0">
          <LineagePanel query={query} />
        </TabsContent>
        <TabsContent value="trace" className="mt-0 space-y-2.5">
          <TracePanel query={query} />
        </TabsContent>
      </div>
    </Tabs>
  );
}

function CitationItem({ c }: { c: Citation }) {
  const s = findSource(c.sourceId);
  const ch = findChunk(c.chunkId);
  const title = c.title ?? s?.title;
  const author = c.author ?? s?.author;
  const hash = c.chunkHash ?? ch?.hash;
  const integrity = Math.round(c.quoteIntegrity * 100);
  return (
    <div className="rounded-md border border-border bg-card p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <span className="citation-marker rounded bg-gold-soft px-1.5 py-0.5 text-xs">
            [{c.marker}]
          </span>
          <span className="font-serif text-sm font-semibold leading-tight">{title}</span>
        </div>
        <Chip
          tone={
            c.classification === "exact"
              ? "success"
              : c.classification === "paraphrase"
                ? "info"
                : "warning"
          }
        >
          {c.classification}
        </Chip>
      </div>
      <div className="mt-0.5 text-[11px] text-muted-foreground">
        {author} {c.page && <span>· p. {c.page}</span>}
      </div>
      <blockquote className="mt-2 border-l-2 border-gold pl-2 font-serif text-sm italic text-foreground/90">
        "{c.excerpt}"
      </blockquote>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-2 text-[10px] text-muted-foreground">
        <span className="font-mono">{hash ? `${hash.slice(0, 22)}…` : "—"}</span>
        <span>quote integrity {integrity}%</span>
      </div>
    </div>
  );
}

function EvidencePacket({ query }: { query: Query }) {
  return (
    <div className="space-y-2">
      <Row label="Tenant" value="St. Vladimir's Seminary" />
      <Row label="Corpus version" value="v2024.11.3" mono />
      <Row label="Confidence tier" value={<span className="capitalize">{query.confidence}</span>} />
      <Row label="Admitted chunks" value={query.evidence.admittedChunks} />
      <Row label="Suppressed" value={query.evidence.suppressed} />
      <Row label="Policy exclusions" value={query.evidence.policyExclusions} />
      <div className="rounded-md border border-border bg-card p-3">
        <div className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">
          Coverage meter
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-muted">
          <div
            className={cn(
              "h-full rounded-full",
              query.evidence.coverage > 0.85
                ? "bg-success"
                : query.evidence.coverage > 0.6
                  ? "bg-info"
                  : "bg-warning",
            )}
            style={{ width: `${query.evidence.coverage * 100}%` }}
          />
        </div>
        <div className="mt-1 text-right text-xs font-medium tabular">
          {Math.round(query.evidence.coverage * 100)}%
        </div>
      </div>
    </div>
  );
}

function LineagePanel({ query }: { query: Query }) {
  const sourceIds = Array.from(new Set(query.citations.map((c) => c.sourceId)));
  return (
    <div className="space-y-2">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
        Approved graph edges
      </div>
      {sourceIds.length === 0 && (
        <div className="rounded-md border border-dashed p-4 text-center text-xs text-muted-foreground">
          No lineage for this answer.
        </div>
      )}
      {sourceIds.map((id) => {
        const s = findSource(id);
        return (
          <div key={id} className="rounded-md border border-border bg-card p-2.5 text-xs">
            <div className="font-medium">{s?.title}</div>
            <div className="text-muted-foreground">{s?.author}</div>
            <div className="mt-1.5 space-y-0.5 text-[11px]">
              <EdgeRow rel="quotes" target="Athanasius — Inc." />
              <EdgeRow rel="builds_on" target="Basil — Spirit" />
              <EdgeRow rel="references" target="Chalcedon Acts" />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function EdgeRow({ rel, target }: { rel: string; target: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="rounded bg-muted px-1 font-mono text-[9px] text-muted-foreground">
        {rel}
      </span>
      <ChevronRight className="h-2.5 w-2.5 text-muted-foreground/50" />
      <span>{target}</span>
    </div>
  );
}

function TracePanel({ query }: { query: Query }) {
  return (
    <div className="space-y-2">
      <Row label="Classification (A1)" value={query.trace.classification} />
      <Row label="Retrieval plan (A2)" value={query.trace.retrievalPlan} />
      <Row label="Model route" value={query.trace.modelRoute} mono />
      <Row label="Latency" value={`${query.trace.latencyMs} ms`} />
      <Row label="Tokens" value={query.trace.tokens.toLocaleString()} />
      <Row label="Cache" value={query.cached ? "hit" : "miss"} />
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3 rounded-md border border-border bg-card px-3 py-2 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("text-right font-medium", mono && "font-mono text-[11px]")}>{value}</span>
    </div>
  );
}
