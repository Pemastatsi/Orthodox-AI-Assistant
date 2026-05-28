import { AdminAuditLog } from "@/components/admin/AdminAuditLog";
import { AdminApiError, listAdminAudit } from "@/lib/admin-api";

interface PageProps {
  searchParams?: {
    cursor?: string;
    action?: string;
    resourceType?: string;
    since?: string;
  };
}

export default async function AuditPage({ searchParams }: PageProps) {
  let page;
  try {
    page = await listAdminAudit({
      cursor: searchParams?.cursor,
      action: searchParams?.action,
      resourceType: searchParams?.resourceType,
      since: searchParams?.since,
    });
  } catch (err) {
    if (err instanceof AdminApiError) {
      return (
        <div className="rounded-md border border-warning/40 bg-warning-soft/40 p-4 text-sm">
          <div className="font-medium text-warning-foreground">Backend unavailable</div>
          <p className="mt-1 text-xs text-muted-foreground">{err.message}</p>
        </div>
      );
    }
    throw err;
  }
  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-serif text-xl font-semibold">Audit log</h2>
        <p className="text-xs text-muted-foreground">
          Append-only record of every privileged action and raw-sensitive view.
        </p>
      </div>
      <AdminAuditLog page={page} />
    </div>
  );
}
