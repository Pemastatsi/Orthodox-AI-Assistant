import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, PageBody, Section, Stat } from "@/components/page";

export const Route = createFileRoute("/_app/analytics")({ component: Analytics });

const TOPICS = [
  { t: "Theosis", n: 184 },
  { t: "Jesus Prayer", n: 142 },
  { t: "Christology", n: 98 },
  { t: "Eucharist", n: 76 },
  { t: "Confession", n: 64 },
  { t: "Iconography", n: 41 },
];

function Analytics() {
  return (
    <>
      <PageHeader
        title="Analytics"
        description="Usage, confidence, fallback rate, and citation integrity over time."
      />
      <PageBody className="space-y-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <Stat label="Queries (30d)" value="2,418" />
          <Stat label="Verified rate" value="94%" tone="success" />
          <Stat label="Fallback rate" value="3.1%" tone="warning" />
          <Stat label="Cache hit" value="38%" />
          <Stat label="Citation integrity" value="96%" tone="gold" />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Section title="Top topics (30d)">
            <ul className="space-y-2">
              {TOPICS.map((t) => (
                <li key={t.t}>
                  <div className="flex items-baseline justify-between text-sm">
                    <span>{t.t}</span>
                    <span className="tabular text-muted-foreground">{t.n}</span>
                  </div>
                  <div className="mt-1 h-1.5 rounded-full bg-muted overflow-hidden">
                    <div className="h-full bg-primary" style={{ width: `${(t.n / 184) * 100}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          </Section>
          <Section title="Confidence distribution">
            <div className="grid grid-cols-4 gap-2 text-center text-xs">
              <Bar tone="bg-success" label="High" v={68} />
              <Bar tone="bg-info" label="Moderate" v={22} />
              <Bar tone="bg-warning" label="Low" v={7} />
              <Bar tone="bg-danger" label="Insufficient" v={3} />
            </div>
          </Section>
        </div>
      </PageBody>
    </>
  );
}

function Bar({ tone, label, v }: { tone: string; label: string; v: number }) {
  return (
    <div>
      <div className="flex h-32 items-end justify-center">
        <div className={`${tone} w-8 rounded-t`} style={{ height: `${v}%` }} />
      </div>
      <div className="mt-1.5">{label}</div>
      <div className="tabular text-muted-foreground">{v}%</div>
    </div>
  );
}
