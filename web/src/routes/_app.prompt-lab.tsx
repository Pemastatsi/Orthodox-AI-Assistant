import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, PageBody, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Beaker, ShieldCheck, GitBranch, Play, RotateCcw } from "lucide-react";

export const Route = createFileRoute("/_app/prompt-lab")({ component: PromptLab });

function PromptLab() {
  return (
    <>
      <PageHeader
        title="Prompt Lab"
        description="Governed prompt editor — draft, test, certify, activate, rollback. Free-form bypass of closed-corpus rules is not permitted."
        badges={
          <Badge variant="outline" className="ml-2 gap-1">
            <ShieldCheck className="h-3 w-3" /> Safety suite required
          </Badge>
        }
      />
      <PageBody className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Section
            title="Composer prompt — draft v17"
            actions={
              <>
                <Button size="sm" variant="outline" className="gap-1.5">
                  <RotateCcw className="h-3.5 w-3.5" /> Rollback
                </Button>
                <Button size="sm" className="gap-1.5">
                  <Play className="h-3.5 w-3.5" /> Run safety suite
                </Button>
              </>
            }
          >
            <Textarea
              rows={10}
              className="font-mono text-xs"
              defaultValue={`Compose an answer using only the admitted_chunks.\nEvery material claim must be supported by an [n] citation marker.\nIf evidence is insufficient, return the bounded fallback template.\n…`}
            />
            <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
              <Field label="Mode" value="composition" />
              <Field label="Tenant" value="SVOTS" />
              <Field label="Diff vs prod" value="+34 / −12" />
            </div>
          </Section>
          <Section title="Preview query">
            <div className="text-sm text-muted-foreground">
              Sample query runs against the candidate prompt with the safety suite. Results replace
              this panel.
            </div>
          </Section>
        </div>
        <div className="space-y-3">
          <Section title="Versions">
            <ul className="space-y-1 text-sm">
              {[
                { v: "v17", s: "draft" },
                { v: "v16", s: "prod" },
                { v: "v15", s: "archived" },
                { v: "v14", s: "archived" },
              ].map((x) => (
                <li
                  key={x.v}
                  className="flex items-center gap-2 rounded-md border border-border px-2.5 py-1.5"
                >
                  <GitBranch className="h-3 w-3 text-muted-foreground" />
                  <span className="font-mono text-xs">{x.v}</span>
                  <Badge variant="outline" className="ml-auto text-[10px]">
                    {x.s}
                  </Badge>
                </li>
              ))}
            </ul>
          </Section>
          <Section title="Safety suite">
            <ul className="space-y-1 text-xs">
              <li className="flex justify-between">
                <span>Closed-corpus assertion</span>
                <span className="text-success">pass</span>
              </li>
              <li className="flex justify-between">
                <span>Citation discipline</span>
                <span className="text-success">pass</span>
              </li>
              <li className="flex justify-between">
                <span>Sensitive reframe</span>
                <span className="text-warning-foreground">pending</span>
              </li>
              <li className="flex justify-between">
                <span>Insufficient fallback</span>
                <span className="text-muted-foreground">not run</span>
              </li>
            </ul>
          </Section>
        </div>
      </PageBody>
    </>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-muted/40 px-2.5 py-1.5">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="text-sm font-medium">{value}</div>
    </div>
  );
}
