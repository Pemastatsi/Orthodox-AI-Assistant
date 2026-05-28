/**
 * Chat page (`/`) — the chat workbench:
 *   center : transcript + composer
 *   right  : citation panel (lg+ only)
 *
 * Dev-mode auth: when `NEXT_PUBLIC_DEV_PRINCIPAL` is configured
 * (e.g. `tn_test:member:usr_test`), the page sends the dev principal header.
 * Production Clerk JWT wiring lands in a follow-up.
 */
"use client";

import { useCallback, useState } from "react";
import { Sparkles } from "lucide-react";
import { AnswerPanel } from "@/components/chat/AnswerPanel";
import { ChatComposer } from "@/components/chat/ChatComposer";
import { CitationPanel } from "@/components/chat/CitationPanel";
import { ConfidenceBadge } from "@/components/chat/ConfidenceBadge";
import { DisclaimerBanner } from "@/components/chat/DisclaimerBanner";
import { ReframingDisclosure } from "@/components/chat/ReframingDisclosure";
import { StageStatus } from "@/components/chat/StageStatus";
import type { AuthHeaders } from "@/lib/api-client";
import type { ApiError, SensitivityPrimary, VerifiedResponse } from "@/lib/schemas";

interface Turn {
  question: string;
  response: VerifiedResponse;
  sensitivity: SensitivityPrimary;
}

function devAuthFromEnv(): AuthHeaders {
  const raw = process.env.NEXT_PUBLIC_DEV_PRINCIPAL;
  if (!raw) {
    return {
      devPrincipal: { tenantId: "tn_test", role: "member", userId: "usr_test" },
    };
  }
  const [tenantId, role, userId] = raw.split(":");
  return {
    devPrincipal: {
      tenantId: tenantId ?? "tn_test",
      role: role ?? "member",
      userId: userId ?? "usr_test",
    },
  };
}

export default function ChatPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [highlightedCitation, setHighlightedCitation] = useState<string | null>(null);

  const auth = devAuthFromEnv();

  const handleResponse = useCallback((response: VerifiedResponse) => {
    setError(null);
    setPendingQuestion((question) => {
      setTurns((prev) => [
        ...prev,
        { question: question ?? "", response, sensitivity: "normal" },
      ]);
      return null;
    });
    setHighlightedCitation(null);
  }, []);

  const handleError = useCallback((apiError: ApiError) => {
    setError(apiError);
    setPendingQuestion(null);
  }, []);

  const activeTurn = turns[turns.length - 1] ?? null;
  const requiresDisclaimer = activeTurn?.response.handling === "answer_with_disclaimer";

  return (
    <main className="flex h-screen flex-col bg-background">
      <header className="flex items-center justify-between border-b border-border bg-surface px-6 py-3">
        <div>
          <h1 className="font-serif text-lg font-semibold">Orthodox AI Assistant</h1>
          <p className="text-xs text-muted-foreground">
            Closed-corpus theological Q&amp;A. Every answer traceable to approved sources.
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-md border border-success/40 bg-success-soft px-2 py-1 text-xs text-success">
          <Sparkles className="h-3 w-3" /> Verified routes
        </span>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-12">
        {/* Center: transcript + composer */}
        <section className="col-span-12 flex min-h-0 flex-col lg:col-span-8">
          <div className="flex-1 overflow-auto">
            <div className="mx-auto max-w-3xl space-y-4 px-6 py-6">
              {turns.length === 0 && pendingQuestion === null && !error && (
                <div className="rounded-md border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
                  Ask a question to begin. Try: <em>What do the Fathers teach about prayer?</em>
                </div>
              )}

              {turns.map((turn, i) => (
                <div key={i} className="space-y-3">
                  {turn.question && (
                    <div className="rounded-lg border border-border bg-surface p-3 text-sm">
                      <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                        You
                      </span>
                      <p className="mt-0.5">{turn.question}</p>
                    </div>
                  )}
                  {turn.response.reframing.wasReframed && (
                    <ReframingDisclosure reframing={turn.response.reframing} />
                  )}
                  {requiresDisclaimer && i === turns.length - 1 && (
                    <DisclaimerBanner category={turn.sensitivity} />
                  )}
                  <AnswerPanel
                    response={turn.response}
                    onCitationClick={setHighlightedCitation}
                    highlightedCitationId={highlightedCitation}
                  />
                </div>
              ))}

              {pendingQuestion !== null && (
                <div className="space-y-3">
                  <div className="rounded-lg border border-border bg-surface p-3 text-sm">
                    <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                      You
                    </span>
                    <p className="mt-0.5">{pendingQuestion}</p>
                  </div>
                  <StageStatus stages={[]} isComplete={false} />
                </div>
              )}

              {error && (
                <div
                  role="alert"
                  className="rounded-md border border-danger/40 bg-danger-soft p-3 text-sm text-danger"
                >
                  <div className="text-[10px] uppercase tracking-wider">Error</div>
                  <p className="mt-0.5">
                    {error.message}{" "}
                    <span className="font-mono text-xs">({error.code})</span>
                  </p>
                </div>
              )}
            </div>
          </div>

          <ChatComposer
            auth={auth}
            onSubmit={setPendingQuestion}
            onResponse={handleResponse}
            onError={handleError}
            disabled={pendingQuestion !== null}
          />
        </section>

        {/* Right: citation panel */}
        <aside className="hidden border-l border-border bg-surface lg:col-span-4 lg:flex lg:flex-col">
          <div className="border-b border-border px-3 py-2">
            <div className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              Citations
            </div>
            {activeTurn && (
              <div className="mt-1">
                <ConfidenceBadge tier={activeTurn.response.confidenceTier} size="sm" />
              </div>
            )}
          </div>
          <div className="flex-1 overflow-hidden p-3">
            {activeTurn ? (
              <CitationPanel
                citations={activeTurn.response.citations}
                highlightedCitationId={highlightedCitation}
                onCitationClick={setHighlightedCitation}
              />
            ) : (
              <p className="text-center text-xs text-muted-foreground">
                Citations appear here once you ask a question.
              </p>
            )}
          </div>
        </aside>
      </div>
    </main>
  );
}
