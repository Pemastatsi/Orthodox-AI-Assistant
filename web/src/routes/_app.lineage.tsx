import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, PageBody, Section, Stat } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { lineageEdges, sources } from "@/data/mock";
import { ArrowRight, Network } from "lucide-react";

export const Route = createFileRoute("/_app/lineage")({ component: Lineage });

function Lineage() {
  return (
    <>
      <PageHeader
        title="Lineage Graph"
        description="Approved evidence relationships across the corpus."
      />
      <PageBody className="space-y-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Nodes" value={sources.length} />
          <Stat
            label="Approved edges"
            value={lineageEdges.filter((e) => e.approved).length}
            tone="success"
          />
          <Stat
            label="Candidate edges"
            value={lineageEdges.filter((e) => !e.approved).length}
            tone="warning"
          />
          <Stat label="Relation types" value={9} tone="gold" />
        </div>
        <Section title="Graph view (preview)">
          <div className="relative h-80 overflow-hidden rounded-md border border-dashed border-border bg-surface-muted p-6">
            <Network className="absolute inset-0 m-auto h-32 w-32 text-muted-foreground/20" />
            <p className="relative text-center text-sm text-muted-foreground">
              Force-directed graph of approved edges. Filter by relation type, click a node for
              source detail.
            </p>
          </div>
        </Section>
        <Section title="Edges">
          <ul className="divide-y divide-border text-sm">
            {lineageEdges.map((e) => {
              const f = sources.find((s) => s.id === e.from);
              const t = sources.find((s) => s.id === e.to);
              return (
                <li key={e.id} className="flex items-center gap-3 py-2.5">
                  <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                    {e.relation}
                  </span>
                  <span className="font-medium">{f?.author}</span>
                  <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="font-medium">{t?.author}</span>
                  <Badge
                    variant="outline"
                    className={`ml-auto ${e.approved ? "border-success/30 bg-success-soft text-success" : "border-warning/40 bg-warning-soft text-warning-foreground"}`}
                  >
                    {e.approved ? "approved" : "candidate"}
                  </Badge>
                  <Button variant="ghost" size="sm" className="h-7 text-xs">
                    Inspect
                  </Button>
                </li>
              );
            })}
          </ul>
        </Section>
      </PageBody>
    </>
  );
}
