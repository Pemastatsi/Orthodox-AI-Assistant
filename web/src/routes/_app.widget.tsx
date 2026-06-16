import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, PageBody, Section } from "@/components/page";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Code2, Copy } from "lucide-react";

export const Route = createFileRoute("/_app/widget")({ component: Widget });

function Widget() {
  const snippet = `<script src="https://cdn.patristic.ai/widget.js"\n  data-tenant="svots"\n  data-theme="light"\n  data-scope="tenant"\n  defer></script>`;
  return (
    <>
      <PageHeader
        title="Embeddable Widget"
        description="Drop the assistant into your site. Domain allowlist enforced."
        actions={
          <Button size="sm" className="gap-1.5">
            <Code2 className="h-3.5 w-3.5" /> Snippet
          </Button>
        }
      />
      <PageBody className="grid gap-6 lg:grid-cols-2">
        <Section title="Configuration">
          <div className="space-y-3">
            <Field label="Allowed domains" defaultValue="svots.edu, library.svots.edu" />
            <Field label="Theme" defaultValue="light" />
            <Field label="Default scope" defaultValue="Tenant corpus only" />
            <Field label="Welcome message" defaultValue="Ask a theological question…" />
          </div>
        </Section>
        <Section
          title="Snippet"
          actions={
            <Button size="sm" variant="outline" className="gap-1.5">
              <Copy className="h-3.5 w-3.5" /> Copy
            </Button>
          }
        >
          <pre className="overflow-auto rounded-md border border-border bg-muted p-3 font-mono text-xs">
            {snippet}
          </pre>
        </Section>
        <Section title="Live preview" className="lg:col-span-2">
          <div className="flex h-72 items-end justify-end rounded-md border border-dashed border-border bg-surface-muted p-4">
            <div className="w-72 rounded-lg border border-border bg-card shadow-lg">
              <div className="border-b border-border bg-primary px-3 py-2 text-xs font-medium text-primary-foreground">
                Patristic Assistant
              </div>
              <div className="space-y-2 p-3 text-xs">
                <div className="rounded-md bg-muted p-2">Welcome — ask a theological question.</div>
                <Input placeholder="Ask…" className="h-8 text-xs" />
              </div>
            </div>
          </div>
        </Section>
      </PageBody>
    </>
  );
}

function Field({ label, defaultValue }: { label: string; defaultValue: string }) {
  return (
    <div>
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Input defaultValue={defaultValue} className="mt-1 h-9 text-sm" />
    </div>
  );
}
