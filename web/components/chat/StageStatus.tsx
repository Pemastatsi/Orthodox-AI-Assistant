/**
 * `<StageStatus>` — renders the verification trace as a horizontal pill chain.
 * Per the contract, this is fed by the SSE progress stream emitted from
 * `<ChatComposer>`. Until SSE lands (deferred follow-up PR), the component
 * accepts a `stages` list directly and is used to show a coarse "verifying…"
 * state while a request is in-flight.
 */
"use client";

import { Activity, CheckCircle2, ChevronRight, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export interface StageStatusProps {
  stages: { stage: string; at: string }[];
  isComplete: boolean;
}

const stageLabel: Record<string, string> = {
  classified: "Classified",
  retrieval_planned: "Retrieval planned",
  vector_search: "Vector search complete",
  evidence_admitted: "Evidence admitted",
  answer_composed: "Answer composed",
  citations_verified: "Citations verified",
  policy_verified: "Policy verified",
  ready: "Ready",
};

export function StageStatus({ stages, isComplete }: StageStatusProps) {
  if (stages.length === 0) {
    return (
      <div className="rounded-md border border-border bg-surface-muted px-3 py-2 text-xs text-muted-foreground">
        <Loader2 className="mr-1.5 inline h-3 w-3 animate-spin" />
        Verifying answer…
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-border bg-surface-muted px-3 py-2.5">
      <div className="mb-2 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        <Activity className="h-3 w-3" /> Verification trace
      </div>
      <ol className="flex flex-wrap items-center gap-x-1 gap-y-1.5">
        {stages.map((s, i) => {
          const isLast = i === stages.length - 1;
          const inFlight = isLast && !isComplete;
          return (
            <li key={`${s.stage}-${s.at}`} className="flex items-center gap-1">
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px]",
                  inFlight
                    ? "border-info/30 bg-info-soft text-info"
                    : "border-success/30 bg-success-soft text-success",
                )}
              >
                {inFlight ? (
                  <Loader2 className="h-2.5 w-2.5 animate-spin" />
                ) : (
                  <CheckCircle2 className="h-2.5 w-2.5" />
                )}
                {stageLabel[s.stage] ?? s.stage}
              </span>
              {!isLast && <ChevronRight className="h-3 w-3 text-muted-foreground/50" />}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
