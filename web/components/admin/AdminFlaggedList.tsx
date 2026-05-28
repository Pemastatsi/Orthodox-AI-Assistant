/**
 * `<AdminFlaggedList>` — paginated table of flagged queries. The backend has
 * already redacted the query text by the time it reaches this component, and
 * has stripped `rawSensitiveLogId` for non-admin readers. The component
 * therefore never decides what to redact — it just renders.
 *
 * Per `auth-context.md`, only admin role + `admin:raw_sensitive:read` scope
 * can deep-link to a raw view. The "View raw" link is rendered only when
 * `rawSensitiveLogId` is non-null (i.e., the caller already has the scope).
 */
import { AlertTriangle, Flag } from "lucide-react";
import type { FlaggedQueryWire, Page } from "@/lib/schemas";

export interface AdminFlaggedListProps {
  page: Page<FlaggedQueryWire>;
}

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toISOString().replace("T", " ").slice(0, 19) + " UTC";
  } catch {
    return iso;
  }
}

export function AdminFlaggedList({ page }: AdminFlaggedListProps) {
  if (page.items.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
        No flagged queries.
      </div>
    );
  }
  return (
    <ul className="space-y-2">
      {page.items.map((item) => {
        const isSelfHarm = item.riskFlags.includes("self_harm");
        return (
          <li
            key={item.flaggedQueryId}
            className="rounded-md border border-border bg-card p-3"
          >
            <div className="flex flex-wrap items-center gap-1.5 text-xs">
              <span
                className={
                  "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 font-medium " +
                  (isSelfHarm
                    ? "border-danger/40 bg-danger-soft text-danger"
                    : "border-warning/40 bg-warning-soft text-warning-foreground")
                }
              >
                {isSelfHarm ? (
                  <AlertTriangle className="h-3 w-3" />
                ) : (
                  <Flag className="h-3 w-3" />
                )}
                {item.flagReason.replace(/_/g, " ")}
              </span>
              {item.sensitivityPrimary && (
                <span className="rounded-md border border-border bg-muted px-1.5 py-0.5 text-muted-foreground">
                  {item.sensitivityPrimary.replace(/_/g, " ")}
                </span>
              )}
              <span className="ml-auto font-mono text-[10px] text-muted-foreground">
                {fmtTime(item.createdAt)}
              </span>
            </div>
            <p className="mt-2 text-sm text-foreground">
              {item.queryTextRedacted}
            </p>
            <div className="mt-2 flex items-center justify-between text-[10px] text-muted-foreground">
              <span className="font-mono">{item.flaggedQueryId}</span>
              {item.rawSensitiveLogId && item.runId && (
                <a
                  href={`/runs/${encodeURIComponent(item.runId)}/raw`}
                  className="text-primary underline-offset-4 hover:underline"
                >
                  View raw (writes audit row)
                </a>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
