import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, PageBody, Section, Stat } from "@/components/page";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CloudDownload, RefreshCw } from "lucide-react";

export const Route = createFileRoute("/_app/offline")({ component: Offline });

function Offline() {
  return (
    <>
      <PageHeader
        title="Offline Sync"
        description="Local-review packets for monasteries and remote locations. Conflict queue handled on next sync."
        actions={
          <Button size="sm" className="gap-1.5">
            <RefreshCw className="h-3.5 w-3.5" /> Sync now
          </Button>
        }
      />
      <PageBody className="space-y-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Packets" value={4} />
          <Stat label="Last sync" value="2h ago" tone="success" />
          <Stat label="Conflicts" value={1} tone="warning" />
          <Stat label="Storage offline" value="1.2 GB" />
        </div>
        <Section title="Packets">
          <ul className="divide-y divide-border text-sm">
            {[
              {
                name: "Holy Trinity Jordanville",
                size: "412 MB",
                state: "synced",
                ts: "2025-04-26 06:00",
              },
              {
                name: "Mount Athos — St. Anthony Skete",
                size: "298 MB",
                state: "synced",
                ts: "2025-04-26 05:14",
              },
              {
                name: "Optina Hermitage USA",
                size: "188 MB",
                state: "conflict",
                ts: "2025-04-25 22:02",
              },
              { name: "Diocese of Alaska — remote", size: "342 MB", state: "queued", ts: "—" },
            ].map((p) => (
              <li key={p.name} className="flex items-center gap-3 py-2.5">
                <CloudDownload className="h-3.5 w-3.5 text-muted-foreground" />
                <div className="flex-1">
                  <div className="font-medium">{p.name}</div>
                  <div className="text-xs text-muted-foreground">
                    {p.size} · last {p.ts}
                  </div>
                </div>
                <Badge
                  variant="outline"
                  className={
                    p.state === "synced"
                      ? "border-success/30 bg-success-soft text-success"
                      : p.state === "conflict"
                        ? "border-warning/40 bg-warning-soft text-warning-foreground"
                        : "border-border bg-muted text-muted-foreground"
                  }
                >
                  {p.state}
                </Badge>
              </li>
            ))}
          </ul>
        </Section>
      </PageBody>
    </>
  );
}
