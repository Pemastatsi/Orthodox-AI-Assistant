/**
 * `/admin/queries` — server component that fetches the first page of run_traces
 * and renders `<AdminQueryLog>`. URL search params drive the filters so the
 * page is bookmarkable.
 */
import { AdminQueryLog } from "@/components/admin/AdminQueryLog";
import { AdminApiError, listAdminQueries } from "@/lib/admin-api";

interface PageProps {
  searchParams?: {
    cursor?: string;
    handling?: string;
    confidenceTier?: string;
    since?: string;
  };
}

export default async function QueriesPage({ searchParams }: PageProps) {
  let page;
  try {
    page = await listAdminQueries({
      cursor: searchParams?.cursor,
      handling: searchParams?.handling,
      confidenceTier: searchParams?.confidenceTier as
        | "GREEN"
        | "YELLOW"
        | "RED"
        | undefined,
      since: searchParams?.since,
    });
  } catch (err) {
    if (err instanceof AdminApiError) {
      return <BackendUnavailable message={err.message} />;
    }
    throw err;
  }
  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-serif text-xl font-semibold">Query log</h2>
        <p className="text-xs text-muted-foreground">
          Every served request lands here. Click a row to inspect the full run trace.
        </p>
      </div>
      <AdminQueryLog page={page} filters={searchParams ?? {}} />
    </div>
  );
}

function BackendUnavailable({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-warning/40 bg-warning-soft/40 p-4 text-sm">
      <div className="font-medium text-warning-foreground">Backend unavailable</div>
      <p className="mt-1 text-xs text-muted-foreground">{message}</p>
    </div>
  );
}
