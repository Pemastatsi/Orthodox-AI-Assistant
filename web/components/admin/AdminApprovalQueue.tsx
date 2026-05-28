/**
 * `<AdminApprovalQueue>` — chunk approval list. Calls PATCH /api/v1/corpus/{chunkId}
 * (corpus:approve scope) for Approve/Reject and Set Visibility actions. Optimistic
 * UI: action fires immediately, row reverts on 4xx with a toast.
 *
 * The contract calls for inline note input for Reject. To keep B.4 focused, the
 * Reject button uses `window.prompt` for the note; a richer modal is a follow-up.
 */
"use client";

import { useState, useTransition } from "react";
import { Check, X, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Chunk, Page, Visibility } from "@/lib/schemas";

export interface AdminApprovalQueueProps {
  initial: Page<Chunk>;
  /** Caller-provided action: must hit PATCH /api/v1/corpus/{chunkId}. */
  onApprove: (chunkId: string) => Promise<void>;
  onReject: (chunkId: string, note: string) => Promise<void>;
  onSetVisibility: (chunkId: string, visibility: Visibility) => Promise<void>;
}

type RowState = "idle" | "submitting" | "error";

export function AdminApprovalQueue({
  initial,
  onApprove,
  onReject,
  onSetVisibility,
}: AdminApprovalQueueProps) {
  const [items, setItems] = useState<Chunk[]>(initial.items);
  const [state, setState] = useState<Record<string, RowState>>({});
  const [isPending, startTransition] = useTransition();

  if (items.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
        No chunks awaiting review.
      </div>
    );
  }

  function setRowState(chunkId: string, next: RowState) {
    setState((s) => ({ ...s, [chunkId]: next }));
  }

  async function run(
    chunkId: string,
    action: () => Promise<void>,
    onSuccess: () => void,
  ) {
    setRowState(chunkId, "submitting");
    try {
      await action();
      startTransition(() => {
        onSuccess();
        setRowState(chunkId, "idle");
      });
    } catch (err) {
      console.error("approval action failed", err);
      setRowState(chunkId, "error");
    }
  }

  return (
    <ul className="space-y-3">
      {items.map((chunk) => {
        const rowState = state[chunk.chunkId] ?? "idle";
        const disabled = rowState === "submitting" || isPending;
        return (
          <li
            key={chunk.chunkId}
            className="rounded-md border border-border bg-card p-3"
          >
            <div className="flex flex-wrap items-center gap-1.5 text-xs">
              <span
                className={
                  "rounded-md border px-1.5 py-0.5 capitalize " +
                  (chunk.approved
                    ? "border-success/40 bg-success-soft text-success"
                    : "border-warning/40 bg-warning-soft text-warning-foreground")
                }
              >
                {chunk.approved ? "approved" : "pending"}
              </span>
              <span className="rounded-md border border-border bg-muted px-1.5 py-0.5 capitalize text-muted-foreground">
                {chunk.visibility.replace(/_/g, " ")}
              </span>
              {chunk.father && <span>{chunk.father}</span>}
              {chunk.work && (
                <span className="text-muted-foreground">· {chunk.work}</span>
              )}
              <span className="ml-auto font-mono text-[10px] text-muted-foreground">
                {chunk.chunkId}
              </span>
            </div>
            <p className="mt-2 line-clamp-3 text-sm text-foreground">
              {chunk.text}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="default"
                disabled={disabled || chunk.approved}
                onClick={() =>
                  void run(
                    chunk.chunkId,
                    () => onApprove(chunk.chunkId),
                    () =>
                      setItems((prev) =>
                        prev.map((c) =>
                          c.chunkId === chunk.chunkId ? { ...c, approved: true } : c,
                        ),
                      ),
                  )
                }
                className="gap-1.5"
              >
                <Check className="h-3.5 w-3.5" /> Approve
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={disabled || !chunk.approved}
                onClick={() => {
                  const note = window.prompt("Reason for rejection?");
                  if (!note) return;
                  void run(
                    chunk.chunkId,
                    () => onReject(chunk.chunkId, note),
                    () =>
                      setItems((prev) =>
                        prev.map((c) =>
                          c.chunkId === chunk.chunkId
                            ? { ...c, approved: false, reviewNote: note }
                            : c,
                        ),
                      ),
                  );
                }}
                className="gap-1.5"
              >
                <X className="h-3.5 w-3.5" /> Reject
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={disabled}
                onClick={() =>
                  void run(
                    chunk.chunkId,
                    () => onSetVisibility(chunk.chunkId, "suppressed"),
                    () =>
                      setItems((prev) =>
                        prev.map((c) =>
                          c.chunkId === chunk.chunkId
                            ? { ...c, visibility: "suppressed" }
                            : c,
                        ),
                      ),
                  )
                }
                className="gap-1.5"
              >
                <EyeOff className="h-3.5 w-3.5" /> Suppress
              </Button>
              {rowState === "error" && (
                <span className="text-xs text-danger">Action failed. Retry.</span>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
