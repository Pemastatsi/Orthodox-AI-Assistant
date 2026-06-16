import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, PageBody, Section } from "@/components/page";
import { queries } from "@/data/mock";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/_app/history")({ component: History });

function History() {
  return (
    <>
      <PageHeader
        title="Query History"
        description="Searchable, filterable log. Each row opens the full evidence packet and run trace."
      />
      <PageBody>
        <Section>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[10px] uppercase tracking-wider text-muted-foreground">
                <th className="py-2 pr-3 font-medium">When</th>
                <th className="py-2 pr-3 font-medium">Asker</th>
                <th className="py-2 pr-3 font-medium">Question</th>
                <th className="py-2 pr-3 font-medium">Mode</th>
                <th className="py-2 pr-3 font-medium">Variant</th>
                <th className="py-2 pr-3 font-medium">Confidence</th>
                <th className="py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {queries.map((q) => (
                <tr key={q.id} className="hover:bg-accent/30">
                  <td className="py-2.5 pr-3 font-mono text-xs">{q.asked}</td>
                  <td className="py-2.5 pr-3 text-xs text-muted-foreground">{q.asker}</td>
                  <td className="py-2.5 pr-3 max-w-md truncate">{q.question}</td>
                  <td className="py-2.5 pr-3 text-xs capitalize">{q.mode.replace(/_/g, " ")}</td>
                  <td className="py-2.5 pr-3">
                    <Badge variant="outline" className="text-[10px] capitalize">
                      {q.variant.replace(/_/g, " ")}
                    </Badge>
                  </td>
                  <td className="py-2.5 pr-3 text-xs capitalize">{q.confidence}</td>
                  <td className="py-2.5">
                    <Button variant="ghost" size="sm" className="h-7 text-xs">
                      Open
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      </PageBody>
    </>
  );
}
