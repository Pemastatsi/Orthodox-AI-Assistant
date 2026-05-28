/**
 * `<CorpusReviewer>` — thin client wrapper that wires `<AdminApprovalQueue>`
 * to PATCH /api/v1/corpus/{chunkId}. Each action sends the dev principal
 * header so the backend's require_scope("corpus:approve") passes.
 *
 * Server components can't ship fetchers that mutate state, so this island
 * lives separately and is imported into the server page.
 */
"use client";

import { AdminApprovalQueue } from "./AdminApprovalQueue";
import type { Chunk, Page, Visibility } from "@/lib/schemas";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function devPrincipalHeader(): Record<string, string> {
  const raw = process.env.NEXT_PUBLIC_DEV_PRINCIPAL ?? "tn_test:admin:usr_test";
  const [tenantId, role, userId] = raw.split(":");
  const json = JSON.stringify({
    tenantId: tenantId ?? "tn_test",
    role: role ?? "admin",
    userId: userId ?? "usr_test",
  });
  const encoded =
    typeof btoa === "function"
      ? btoa(json)
      : Buffer.from(json, "utf-8").toString("base64");
  return { "x-dev-principal": encoded };
}

async function patchCorpus(
  chunkId: string,
  body: { approved?: boolean; visibility?: Visibility; reviewNote?: string | null },
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/corpus/${encodeURIComponent(chunkId)}`, {
    method: "PATCH",
    headers: { "content-type": "application/json", ...devPrincipalHeader() },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`PATCH /corpus/${chunkId} → ${res.status}: ${text}`);
  }
}

export function CorpusReviewer({ initial }: { initial: Page<Chunk> }) {
  return (
    <AdminApprovalQueue
      initial={initial}
      onApprove={(id) => patchCorpus(id, { approved: true })}
      onReject={(id, note) => patchCorpus(id, { approved: false, reviewNote: note })}
      onSetVisibility={(id, visibility) => patchCorpus(id, { visibility })}
    />
  );
}
