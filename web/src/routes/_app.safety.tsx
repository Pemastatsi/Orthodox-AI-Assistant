import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, PageBody, Section, Stat } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ShieldAlert, EyeOff, Lock } from "lucide-react";

export const Route = createFileRoute("/_app/safety")({ component: Safety });

const RULES = [
  {
    name: "Personal pastoral counsel",
    action: "reframe",
    desc: "Reframe to teaching question with disclaimer.",
  },
  {
    name: "Predictive about individuals",
    action: "block",
    desc: "Block; suggest pastoral conversation.",
  },
  {
    name: "Medical / mental health crisis",
    action: "block",
    desc: "Block; surface crisis resources.",
  },
  {
    name: "Disputed political matter",
    action: "reframe",
    desc: "Teaching reframe within Orthodox tradition.",
  },
  {
    name: "Sacramental advice without priest",
    action: "reframe",
    desc: "Surface canonical teaching only.",
  },
];

function Safety() {
  return (
    <>
      <PageHeader
        title="Safety Gate"
        description="Sensitive-query handling rules and audit. Raw text redacted by default; access is gated and audited."
        badges={
          <Badge variant="outline" className="ml-2 gap-1">
            <ShieldAlert className="h-3 w-3" /> Active
          </Badge>
        }
      />
      <PageBody className="space-y-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Reframed (30d)" value={47} tone="warning" />
          <Stat label="Blocked (30d)" value={12} tone="danger" />
          <Stat label="Redacted entries" value={59} />
          <Stat label="Raw-access requests" value={3} tone="gold" />
        </div>
        <Section title="Handling rules">
          <ul className="divide-y divide-border">
            {RULES.map((r) => (
              <li key={r.name} className="flex items-start justify-between gap-3 py-3">
                <div>
                  <div className="font-medium">{r.name}</div>
                  <div className="text-xs text-muted-foreground">{r.desc}</div>
                </div>
                <Badge
                  variant="outline"
                  className={
                    r.action === "block"
                      ? "border-danger/40 bg-danger-soft text-danger"
                      : "border-warning/40 bg-warning-soft text-warning-foreground"
                  }
                >
                  {r.action}
                </Badge>
              </li>
            ))}
          </ul>
        </Section>
        <Section
          title="Audited raw-text access"
          description="Redacted by default. Access requires reviewer credentials and produces an audit entry."
        >
          <div className="rounded-md border border-dashed border-border bg-surface-muted p-6 text-center">
            <Lock className="mx-auto mb-2 h-6 w-6 text-muted-foreground" />
            <div className="text-sm font-medium">59 redacted entries</div>
            <div className="text-xs text-muted-foreground">
              Reviewer sign-off required to view raw text.
            </div>
            <Button size="sm" variant="outline" className="mt-3 gap-1.5">
              <EyeOff className="h-3.5 w-3.5" /> Request audited access
            </Button>
          </div>
        </Section>
      </PageBody>
    </>
  );
}
