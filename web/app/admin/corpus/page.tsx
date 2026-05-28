/**
 * `/admin/corpus` — server-fetched first page wrapped in a client island so
 * Approve / Reject / Visibility actions can call PATCH /api/v1/corpus/{chunkId}
 * optimistically without a full page reload.
 */
import { CorpusReviewer } from "@/components/admin/CorpusReviewer";
import { AdminApiError, listCorpus } from "@/lib/admin-api";

interface PageProps {
  searchParams?: { cursor?: string };
}

export default async function CorpusPage({ searchParams }: PageProps) {
  let page;
  try {
    page = await listCorpus({
      cursor: searchParams?.cursor,
      approved: false,
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
        <h2 className="font-serif text-xl font-semibold">Corpus approval</h2>
        <p className="text-xs text-muted-foreground">
          Chunks pending review. Approve to admit to retrieval; suppress to hide regardless of approval.
        </p>
      </div>
      <CorpusReviewer initial={page} />
    </div>
  );
}
