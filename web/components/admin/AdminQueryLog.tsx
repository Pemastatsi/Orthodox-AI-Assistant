/**
 * `<AdminQueryLog>` — renders a page of `RunTrace` rows per
 * `frontend-components.md`. Columns: time, runId (truncated), handling,
 * confidenceTier, cacheHit, durationMs.
 *
 * Row click → navigate to `/runs/[runId]` (route placeholder). Sensitive query
 * text never appears here — the redacted text lives on `/admin/flagged`.
 */
import Link from "next/link";
import type { Route } from "next";
import type { Page, RunTrace } from "@/lib/schemas";

export interface AdminQueryLogProps {
  page: Page<RunTrace>;
  filters?: { handling?: string; confidenceTier?: string; since?: string };
}

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toISOString().replace("T", " ").slice(0, 19) + " UTC";
  } catch {
    return iso;
  }
}

function durationMs(trace: RunTrace): number | null {
  if (!trace.finishedAt) return null;
  return Math.max(
    0,
    new Date(trace.finishedAt).getTime() - new Date(trace.startedAt).getTime(),
  );
}

export function AdminQueryLog({ page }: AdminQueryLogProps) {
  if (page.items.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
        No query log rows.
      </div>
    );
  }
  return (
    <div className="overflow-x-auto rounded-md border border-border bg-card">
      <table className="w-full text-sm">
        <thead className="bg-surface-muted text-xs text-muted-foreground">
          <tr>
            <th className="px-3 py-2 text-left font-medium">Time</th>
            <th className="px-3 py-2 text-left font-medium">Run ID</th>
            <th className="px-3 py-2 text-left font-medium">Handling</th>
            <th className="px-3 py-2 text-left font-medium">Confidence</th>
            <th className="px-3 py-2 text-left font-medium">Cache</th>
            <th className="px-3 py-2 text-right font-medium">Duration</th>
          </tr>
        </thead>
        <tbody>
          {page.items.map((trace) => {
            const dur = durationMs(trace);
            return (
              <tr
                key={trace.runId}
                className="border-t border-border hover:bg-accent/30"
              >
                <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                  {fmtTime(trace.startedAt)}
                </td>
                <td className="px-3 py-2 font-mono text-xs">
                  <Link
                    href={`/runs/${encodeURIComponent(trace.runId)}` as Route}
                    className="text-primary underline-offset-4 hover:underline"
                  >
                    {trace.runId.length > 18
                      ? trace.runId.slice(0, 8) + "…" + trace.runId.slice(-6)
                      : trace.runId}
                  </Link>
                </td>
                <td className="px-3 py-2 capitalize">
                  {(trace.finalHandling ?? "—").replace(/_/g, " ")}
                </td>
                <td className="px-3 py-2">
                  <ConfidencePill tier={trace.finalConfidenceTier ?? null} />
                </td>
                <td className="px-3 py-2 text-xs">
                  {trace.cacheHit ? (
                    <span className="rounded-md border border-gold/30 bg-gold-soft px-1.5 py-0.5 text-gold-foreground">
                      hit
                    </span>
                  ) : (
                    <span className="text-muted-foreground">miss</span>
                  )}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-xs">
                  {dur === null ? "—" : `${dur} ms`}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ConfidencePill({ tier }: { tier: string | null }) {
  if (!tier) return <span className="text-muted-foreground">—</span>;
  const tone =
    tier === "GREEN"
      ? "border-success/40 bg-success-soft text-success"
      : tier === "YELLOW"
        ? "border-info/40 bg-info-soft text-info"
        : "border-danger/40 bg-danger-soft text-danger";
  return (
    <span
      className={`inline-flex rounded-md border px-1.5 py-0.5 text-[10px] font-medium ${tone}`}
    >
      {tier}
    </span>
  );
}
