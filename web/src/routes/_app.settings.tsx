import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, PageBody, Section } from "@/components/page";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

export const Route = createFileRoute("/_app/settings")({ component: Settings });

function Settings() {
  return (
    <>
      <PageHeader
        title="Tenant Settings"
        description="Branding, data region, default scope, retention, and integrations."
        actions={<Button size="sm">Save changes</Button>}
      />
      <PageBody className="grid gap-6 lg:grid-cols-2">
        <Section title="Identity">
          <div className="space-y-3">
            <Field label="Tenant name" defaultValue="St. Vladimir's Seminary" />
            <Field label="Display short name" defaultValue="SVOTS" />
            <Field label="Public contact" defaultValue="library@svots.edu" />
          </div>
        </Section>
        <Section title="Defaults">
          <div className="space-y-3">
            <Field label="Default language" defaultValue="English" />
            <Field label="Default scope" defaultValue="Tenant corpus only" />
            <Field label="Data region" defaultValue="US-East" />
          </div>
        </Section>
        <Section title="Retention">
          <Toggle label="Retain raw query text 30 days" defaultChecked />
          <Toggle label="Retain run traces 90 days" defaultChecked />
          <Toggle label="Anonymize after retention window" defaultChecked />
        </Section>
        <Section title="Integrations">
          <Toggle label="Slack notifications" />
          <Toggle label="LMS export (Canvas)" defaultChecked />
          <Toggle label="DOI lookup (Crossref)" defaultChecked />
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
function Toggle({ label, defaultChecked }: { label: string; defaultChecked?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-border py-2 last:border-0">
      <Label className="text-sm">{label}</Label>
      <Switch defaultChecked={defaultChecked} />
    </div>
  );
}
