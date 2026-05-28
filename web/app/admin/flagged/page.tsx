import { AdminFlaggedList } from "@/components/admin/AdminFlaggedList";
import { AdminApiError, listAdminFlagged } from "@/lib/admin-api";

interface PageProps {
  searchParams?: { cursor?: string; flagReason?: string };
}

export default async function FlaggedPage({ searchParams }: PageProps) {
  let page;
  try {
    page = await listAdminFlagged({
      cursor: searchParams?.cursor,
      flagReason: searchParams?.flagReason,
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
        <h2 className="font-serif text-xl font-semibold">Flagged queries</h2>
        <p className="text-xs text-muted-foreground">
          Query text is redacted by default. Raw views require admin scope and produce an audit row.
        </p>
      </div>
      <AdminFlaggedList page={page} />
    </div>
  );
}
