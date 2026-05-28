/**
 * `<AdminAuditLog>` — append-only audit log per `db-schema.md` cross-table
 * invariant #5. Columns: occurredAt, actorRole / actorUserId, action,
 * resourceType / resourceId, ipAddress.
 *
 * The endpoint is admin-role only (admin:audit:read scope), enforced at the
 * route layer. This component does no auth checks — by the time data
 * reaches it, the request was already authorized.
 */
import type { AuditEntry, Page } from "@/lib/schemas";

export interface AdminAuditLogProps {
  page: Page<AuditEntry>;
}

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toISOString().replace("T", " ").slice(0, 19) + " UTC";
  } catch {
    return iso;
  }
}

export function AdminAuditLog({ page }: AdminAuditLogProps) {
  if (page.items.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
        No audit entries.
      </div>
    );
  }
  return (
    <div className="overflow-x-auto rounded-md border border-border bg-card">
      <table className="w-full text-sm">
        <thead className="bg-surface-muted text-xs text-muted-foreground">
          <tr>
            <th className="px-3 py-2 text-left font-medium">When</th>
            <th className="px-3 py-2 text-left font-medium">Actor</th>
            <th className="px-3 py-2 text-left font-medium">Action</th>
            <th className="px-3 py-2 text-left font-medium">Resource</th>
            <th className="px-3 py-2 text-left font-medium">IP</th>
          </tr>
        </thead>
        <tbody>
          {page.items.map((entry) => (
            <tr key={entry.auditId} className="border-t border-border hover:bg-accent/30">
              <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                {fmtTime(entry.occurredAt)}
              </td>
              <td className="px-3 py-2 text-xs">
                <div className="capitalize">{entry.actorRole}</div>
                <div className="font-mono text-[10px] text-muted-foreground">
                  {entry.actorUserId}
                </div>
              </td>
              <td className="px-3 py-2">
                <span className="rounded-md border border-border bg-muted px-1.5 py-0.5 text-xs">
                  {entry.action.replace(/_/g, " ")}
                </span>
              </td>
              <td className="px-3 py-2 text-xs">
                <div className="capitalize text-muted-foreground">
                  {entry.resourceType}
                </div>
                <div className="font-mono text-[10px]">{entry.resourceId}</div>
              </td>
              <td className="px-3 py-2 font-mono text-[10px] text-muted-foreground">
                {entry.ipAddress ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
