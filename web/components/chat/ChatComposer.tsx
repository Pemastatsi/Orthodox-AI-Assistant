/**
 * `<ChatComposer>` — textarea + submit. Enter submits, Shift+Enter inserts a
 * newline. While `isSubmitting`, the textarea is disabled and the button shows
 * a spinner. SSE streaming is deferred — until it lands, `streamProgress` stays
 * empty and `onResponse` fires once with the full `VerifiedResponse`.
 */
"use client";

import { useState, type KeyboardEvent } from "react";
import { Loader2, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { postQuery, ApiClientError, type AuthHeaders } from "@/lib/api-client";
import type { ApiError, VerifiedResponse } from "@/lib/schemas";

export interface ChatComposerProps {
  /** Resolves fresh auth headers per request (Clerk JWT in prod, dev principal in development).
   *  Async because Clerk session tokens are short-lived and fetched at submit time. */
  resolveAuth: () => Promise<AuthHeaders>;
  /** Fires the moment the user submits, before the network call returns. */
  onSubmit?: (queryText: string) => void;
  onResponse: (response: VerifiedResponse) => void;
  onError: (error: ApiError) => void;
  /** Disables submit; used by parent to lock the input while rendering a result. */
  disabled?: boolean;
  maxLength?: number;
}

export function ChatComposer({
  resolveAuth,
  onSubmit,
  onResponse,
  onError,
  disabled = false,
  maxLength = 4000,
}: ChatComposerProps) {
  const [value, setValue] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submit() {
    const trimmed = value.trim();
    if (!trimmed || isSubmitting) return;
    setIsSubmitting(true);
    onSubmit?.(trimmed);
    try {
      const auth = await resolveAuth();
      const response = await postQuery({ queryText: trimmed }, { auth });
      onResponse(response);
      setValue("");
    } catch (err) {
      if (err instanceof ApiClientError) {
        onError(
          err.apiError ?? {
            code: `http_${err.status}`,
            message: err.message,
          },
        );
      } else {
        onError({
          code: "client_error",
          message: err instanceof Error ? err.message : "Unknown error",
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void submit();
    }
  }

  return (
    <div className="border-t border-border bg-surface px-4 py-3">
      <div className="mx-auto max-w-3xl">
        <div className="flex items-end gap-2 rounded-lg border border-border bg-background p-2 focus-within:border-primary">
          <Textarea
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ask from the approved library…"
            maxLength={maxLength}
            disabled={disabled || isSubmitting}
            className="min-h-[40px] resize-none border-0 bg-transparent px-2 py-1.5 text-sm shadow-none focus-visible:ring-0"
            rows={1}
            aria-label="Question"
          />
          <Button
            type="button"
            size="sm"
            onClick={() => void submit()}
            disabled={disabled || isSubmitting || value.trim().length === 0}
            className="gap-1.5"
          >
            {isSubmitting ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Send className="h-3.5 w-3.5" />
            )}
            Ask
          </Button>
        </div>
        <p className="mt-1 text-[10px] text-muted-foreground">
          Closed corpus. Answers compose only after citation and policy verification pass.
        </p>
      </div>
    </div>
  );
}
