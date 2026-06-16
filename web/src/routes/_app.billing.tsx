import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, PageBody, Section, Stat } from "@/components/page";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export const Route = createFileRoute("/_app/billing")({ component: Billing });

function Billing() {
  return (
    <>
      <PageHeader
        title="Billing"
        description="Plan, seats, usage meters, and invoices."
        badges={
          <Badge variant="outline" className="ml-2 border-primary/30 bg-primary-soft text-primary">
            Institution
          </Badge>
        }
      />
      <PageBody className="space-y-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Plan" value="Institution" hint="$2,400 / mo" />
          <Stat label="Seats" value="34 / 50" />
          <Stat label="Queries (mo)" value="2,418" hint="of 10,000" tone="success" />
          <Stat label="Storage" value="42 GB" hint="of 500 GB" />
        </div>
        <Section title="Invoices">
          <ul className="divide-y divide-border text-sm">
            {[
              { d: "2025-04-01", a: "$2,400.00", s: "paid" },
              { d: "2025-03-01", a: "$2,400.00", s: "paid" },
              { d: "2025-02-01", a: "$2,400.00", s: "paid" },
            ].map((i) => (
              <li key={i.d} className="flex items-center gap-3 py-2.5">
                <span className="font-mono text-xs">{i.d}</span>
                <span className="ml-auto tabular">{i.a}</span>
                <Badge variant="outline" className="border-success/30 bg-success-soft text-success">
                  {i.s}
                </Badge>
                <Button variant="ghost" size="sm" className="h-7 text-xs">
                  Download
                </Button>
              </li>
            ))}
          </ul>
        </Section>
      </PageBody>
    </>
  );
}
