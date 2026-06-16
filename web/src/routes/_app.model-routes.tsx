import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, PageBody, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { modelRoutes } from "@/data/mock";

export const Route = createFileRoute("/_app/model-routes")({ component: ModelRoutes });

function ModelRoutes() {
  return (
    <>
      <PageHeader
        title="Model Routes"
        description="Provider/model registry. Only certified routes serve production users."
        actions={<Button size="sm">New route</Button>}
      />
      <PageBody>
        <Section>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[10px] uppercase tracking-wider text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Route</th>
                <th className="py-2 pr-3 font-medium">Provider / model</th>
                <th className="py-2 pr-3 font-medium">Purpose</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 pr-3 font-medium">P50 latency</th>
                <th className="py-2 pr-3 font-medium">$/1k tok</th>
                <th className="py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {modelRoutes.map((m) => (
                <tr key={m.id}>
                  <td className="py-2.5 pr-3 font-mono text-xs">{m.name}</td>
                  <td className="py-2.5 pr-3 text-xs">
                    <span className="capitalize">{m.provider}</span> · {m.model}
                  </td>
                  <td className="py-2.5 pr-3 text-xs capitalize">{m.purpose}</td>
                  <td className="py-2.5 pr-3 space-x-1">
                    <Badge
                      variant="outline"
                      className={
                        m.certified
                          ? "border-success/30 bg-success-soft text-success"
                          : "border-warning/40 bg-warning-soft text-warning-foreground"
                      }
                    >
                      {m.certified ? "certified" : "candidate"}
                    </Badge>
                    {m.inProduction && (
                      <Badge
                        variant="outline"
                        className="border-primary/30 bg-primary-soft text-primary"
                      >
                        prod
                      </Badge>
                    )}
                  </td>
                  <td className="py-2.5 pr-3 tabular text-xs">{m.latencyP50} ms</td>
                  <td className="py-2.5 pr-3 tabular text-xs">${m.costPer1k.toFixed(4)}</td>
                  <td className="py-2.5">
                    <Button variant="ghost" size="sm" className="h-7 text-xs">
                      Test
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
