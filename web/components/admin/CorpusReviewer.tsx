/**
 * `<CorpusReviewer>` — thin client wrapper that wires `<AdminApprovalQueue>`
 * to PATCH /api/v1/corpus/{chunkId}. Each action sends a Clerk JWT (or the dev
 * principal in dev mode) so the backend's require_scope("corpus:approve") passes.
 *
 * Server components can't ship fetchers that mutate state, so this island
 * lives separately and is imported into the server page.
 */
"use client";

import { AdminApprovalQueue } from "./AdminApprovalQueue";
import { authHeaderRecord, useAuthResolver } from "@/lib/auth-headers";
import type { Chunk, Page, Visibility } from "@/lib/schemas";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function CorpusReviewer({ initial }: { initial: Page<Chunk> }) {
  // Admin mutations need the corpus:approve scope; dev mode falls back to an admin dev principal.
  const resolveAuth = useAuthResolver("admin");

  async function patchCorpus(
    chunkId: string,
    body: { approved?: boolean; visibility?: Visibility; reviewNote?: string | null },
  ): Promise<void> {
    const auth = await resolveAuth();
    const res = await fetch(`${API_BASE}/api/v1/corpus/${encodeURIComponent(chunkId)}`, {
      method: "PATCH",
      headers: { "content-type": "application/json", ...authHeaderRecord(auth) },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`PATCH /corpus/${chunkId} → ${res.status}: ${text}`);
    }
  }

  return (
    <AdminApprovalQueue
      initial={initial}
      onApprove={(id) => patchCorpus(id, { approved: true })}
      onReject={(id, note) => patchCorpus(id, { approved: false, reviewNote: note })}
      onSetVisibility={(id, visibility) => patchCorpus(id, { visibility })}
    />
  );
}
