import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, PageBody, Section, Stat } from "@/components/page";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Quote, ArrowRight, Check, X, AlertCircle } from "lucide-react";
import { sources } from "@/data/mock";

export const Route = createFileRoute("/_app/citations")({
  component: Citations,
});

const QUEUE = [
  {
    id: "cit-441",
    extracted: "the Son of God became man so that we might become God",
    candidate: "src-athanasius-incarnatione",
    canonical: "On the Incarnation, §54.3 — '… so that we might become God.'",
    lex: 0.94,
    embed: 0.97,
    combined: 0.96,
    proposed: "exact",
  },
  {
    id: "cit-442",
    extracted: "the light of Tabor is uncreated",
    candidate: "src-palamas-triads",
    canonical: "Triads III.1.33 — 'The light of Tabor … uncreated and divine.'",
    lex: 0.71,
    embed: 0.92,
    combined: 0.84,
    proposed: "paraphrase",
  },
  {
    id: "cit-443",
    extracted: "deification is participation in the divine essence",
    candidate: "—",
    canonical: "(no high-confidence canonical match)",
    lex: 0.33,
    embed: 0.41,
    combined: 0.37,
    proposed: "misattributed",
  },
];

function Citations() {
  return (
    <>
      <PageHeader
        title="Citation Resolver"
        description="Classify extracted citations against the canonical corpus. Strengthen quote integrity tenant-wide."
        actions={<Button size="sm">Open queue</Button>}
      />
      <PageBody className="space-y-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <Stat label="Pending" value={QUEUE.length} tone="warning" />
          <Stat label="Exact (30d)" value={418} tone="success" />
          <Stat label="Paraphrase" value={91} />
          <Stat label="Misattributed" value={7} tone="danger" />
          <Stat label="Integrity" value="96%" tone="gold" />
        </div>

        {QUEUE.map((q) => {
          const src = sources.find((s) => s.id === q.candidate);
          return (
            <Section
              key={q.id}
              title={`Candidate ${q.id}`}
              actions={
                <Badge variant="outline" className="capitalize">
                  {q.proposed}
                </Badge>
              }
            >
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-md border border-border bg-muted/40 p-3">
                  <div className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">
                    Extracted
                  </div>
                  <p className="font-serif text-sm italic">"{q.extracted}"</p>
                </div>
                <div className="rounded-md border border-gold/30 bg-gold-soft/40 p-3">
                  <div className="mb-1 flex items-center gap-1 text-[10px] uppercase tracking-wider text-gold-foreground">
                    <Quote className="h-3 w-3" /> Canonical match
                  </div>
                  <p className="font-serif text-sm italic">{q.canonical}</p>
                  {src && <div className="mt-1.5 text-xs text-muted-foreground">{src.author}</div>}
                </div>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                <ScoreBar label="Lexical" v={q.lex} />
                <ScoreBar label="Embedding" v={q.embed} />
                <ScoreBar label="Combined" v={q.combined} />
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button size="sm" variant="outline" className="gap-1.5">
                  <Check className="h-3.5 w-3.5" /> Exact
                </Button>
                <Button size="sm" variant="outline">
                  Paraphrase
                </Button>
                <Button size="sm" variant="outline">
                  Allusion
                </Button>
                <Button size="sm" variant="outline" className="gap-1.5">
                  <AlertCircle className="h-3.5 w-3.5" /> Misattributed
                </Button>
                <Button size="sm" variant="outline">
                  Unresolved
                </Button>
                <Button size="sm" variant="ghost" className="ml-auto gap-1.5">
                  Override history <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            </Section>
          );
        })}
      </PageBody>
    </>
  );
}

function ScoreBar({ label, v }: { label: string; v: number }) {
  const pct = Math.round(v * 100);
  const tone = v > 0.85 ? "bg-success" : v > 0.6 ? "bg-info" : "bg-warning";
  return (
    <div className="rounded-md border border-border bg-card p-2">
      <div className="flex items-baseline justify-between text-[10px] text-muted-foreground">
        <span>{label}</span>
        <span className="tabular font-medium text-foreground">{pct}%</span>
      </div>
      <div className="mt-1 h-1 overflow-hidden rounded-full bg-muted">
        <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
