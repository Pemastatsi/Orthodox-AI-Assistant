/**
 * `<ReframingDisclosure>` — always-transparent reframing per ADR 0002.
 * Renders ONLY when `reframing.wasReframed === true`. Shows the original and
 * reframed queries plus the disclosure text; never offers a "view as
 * originally asked" toggle (decision register row F).
 */
import { CornerDownRight } from "lucide-react";
import type { Reframing } from "@/lib/schemas";

export interface ReframingDisclosureProps {
  reframing: Reframing;
}

export function ReframingDisclosure({ reframing }: ReframingDisclosureProps) {
  if (!reframing.wasReframed) return null;

  return (
    <section
      aria-label="Reframing disclosure"
      className="rounded-md border border-warning/40 bg-warning-soft/40 p-3 text-sm"
    >
      <p className="mb-2 text-xs font-medium uppercase tracking-wider text-warning-foreground">
        We answered a teaching-oriented version of your question.
      </p>
      {reframing.disclosureText && (
        <p className="mb-2 text-sm text-warning-foreground">{reframing.disclosureText}</p>
      )}
      <dl className="grid gap-2 text-xs">
        {reframing.originalQuery && (
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Original
            </dt>
            <dd className="text-foreground">{reframing.originalQuery}</dd>
          </div>
        )}
        {reframing.reframedQuery && (
          <div>
            <dt className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground">
              <CornerDownRight className="h-3 w-3" /> Reframed
            </dt>
            <dd className="font-medium text-foreground">{reframing.reframedQuery}</dd>
          </div>
        )}
      </dl>
    </section>
  );
}
