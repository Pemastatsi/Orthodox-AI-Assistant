import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, PageBody, Section, Stat } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { gaps } from "@/data/mock";
import { AlertTriangle, Plus } from "lucide-react";

export const Route = createFileRoute("/_app/gaps")({ component: Gaps });

function Gaps() {
  return (
    <>
      <PageHeader
        title="Gaps & Content"
        description="Reported corpus gaps from real user queries — assign, source, and resolve."
        actions={
          <Button size="sm" className="gap-1.5">
            <Plus className="h-3.5 w-3.5" /> Report gap
          </Button>
        }
      />
      <PageBody className="space-y-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat
            label="Open"
            value={gaps.filter((g) => g.status === "open").length}
            tone="warning"
          />
          <Stat label="In progress" value={gaps.filter((g) => g.status === "in_progress").length} />
          <Stat
            label="Resolved (30d)"
            value={gaps.filter((g) => g.status === "resolved").length}
            tone="success"
          />
          <Stat label="Total reports" value={gaps.reduce((s, g) => s + g.reports, 0)} tone="gold" />
        </div>
        <Section title="Reported gaps">
          <ul className="divide-y divide-border">
            {gaps.map((g) => (
              <li key={g.id} className="py-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="h-3.5 w-3.5 text-warning" />
                      <span className="font-medium">{g.topic}</span>
                    </div>
                    <div className="mt-0.5 text-xs text-muted-foreground">
                      {g.reports} reports · last {g.lastReported}{" "}
                      {g.assignedTo && (
                        <>
                          · assigned <span className="text-foreground">{g.assignedTo}</span>
                        </>
                      )}
                    </div>
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {g.suggestedSources.map((s) => (
                        <Badge key={s} variant="outline" className="text-[10px]">
                          {s}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <Badge
                    variant="outline"
                    className={
                      g.status === "resolved"
                        ? "border-success/30 bg-success-soft text-success"
                        : g.status === "in_progress"
                          ? "border-info/30 bg-info-soft text-info"
                          : "border-warning/40 bg-warning-soft text-warning-foreground"
                    }
                  >
                    {g.status.replace("_", " ")}
                  </Badge>
                </div>
              </li>
            ))}
          </ul>
        </Section>
      </PageBody>
    </>
  );
}
