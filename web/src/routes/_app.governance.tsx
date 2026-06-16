import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, PageBody, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { policies } from "@/data/mock";
import type { PolicyNode as PolicyNodeData } from "@/data/types";
import { Scale, ChevronRight } from "lucide-react";

export const Route = createFileRoute("/_app/governance")({ component: Governance });

function Governance() {
  const root = policies.find((p) => !p.parent)!;
  const childrenOf = (id: string) => policies.filter((p) => p.parent === id);
  return (
    <>
      <PageHeader
        title="Governance"
        description="Policy hierarchy — universal canons, jurisdictional policies, local customs. Precedence enforced at retrieval time."
        badges={
          <Badge variant="outline" className="ml-2 gap-1">
            <Scale className="h-3 w-3" /> Hierarchical
          </Badge>
        }
      />
      <PageBody className="space-y-4">
        <Section title="Policy tree">
          <PolicyNode node={root} children={childrenOf} depth={0} />
        </Section>
      </PageBody>
    </>
  );
}

function PolicyNode({
  node,
  children,
  depth,
}: {
  node: PolicyNodeData;
  children: (id: string) => PolicyNodeData[];
  depth: number;
}) {
  const kids = children(node.id);
  return (
    <div style={{ marginLeft: depth * 16 }}>
      <div className="flex items-start gap-2 rounded-md border border-border bg-card p-3">
        <ChevronRight className="mt-0.5 h-3.5 w-3.5 text-muted-foreground" />
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="font-serif text-sm font-semibold">{node.name}</span>
            <Badge variant="outline" className="capitalize text-[10px]">
              {node.scope}
            </Badge>
            <span className="ml-auto font-mono text-[10px] text-muted-foreground">
              eff. {node.effective}
            </span>
          </div>
          <p className="text-xs text-muted-foreground">{node.description}</p>
        </div>
      </div>
      {kids.length > 0 && (
        <div className="mt-2 space-y-2 border-l border-dashed border-border pl-4">
          {kids.map((k) => (
            <PolicyNode key={k.id} node={k} children={children} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}
