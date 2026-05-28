/**
 * `<AnswerPanel>` — renders a `VerifiedResponse`. The visual surface differs
 * by `response.handling`:
 *
 *   - "answer" / "answer_with_disclaimer" → normal verified answer with
 *     inline citation markers `[n]` that link back to `<CitationPanel>`.
 *   - "reframe_to_teaching" → reframing disclosure + answer (the actual
 *     `<ReframingDisclosure>` is rendered as a sibling by the page; this
 *     panel handles the answer body).
 *   - "block_with_redirect" → danger-toned card, no citations rendered,
 *     full canonical bounded-fallback text shown verbatim.
 *   - "insufficient_evidence" → danger-toned card with "insufficient evidence"
 *     label and the canonical bounded-fallback text.
 *
 * For "answer_with_disclaimer" the page is responsible for rendering
 * `<DisclaimerBanner>` above this component (per the contract). The
 * `<AnswerPanel>` itself does not own the banner.
 */
import { AlertTriangle, Ban, CircleDashed, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { ConfidenceBadge } from "./ConfidenceBadge";
import type { VerifiedResponse } from "@/lib/schemas";

export interface AnswerPanelProps {
  response: VerifiedResponse;
  onCitationClick?: (citationId: string) => void;
  highlightedCitationId?: string | null;
}

export function AnswerPanel({
  response,
  onCitationClick,
  highlightedCitationId = null,
}: AnswerPanelProps) {
  switch (response.handling) {
    case "block_with_redirect":
      return <BlockedCard response={response} />;
    case "insufficient_evidence":
      return <InsufficientCard response={response} />;
    case "answer":
    case "answer_with_disclaimer":
    case "reframe_to_teaching":
    default:
      return (
        <VerifiedCard
          response={response}
          onCitationClick={onCitationClick}
          highlightedCitationId={highlightedCitationId}
        />
      );
  }
}

/** Splits an answer body into text spans and `[n]` citation markers. */
function renderAnswerBody(
  body: string,
  citations: VerifiedResponse["citations"],
  onCitationClick?: (citationId: string) => void,
  highlightedCitationId: string | null = null,
): React.ReactNode {
  const parts = body.split(/(\[\d+\])/g);
  return parts.map((part, i) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (!match) return <span key={i}>{part}</span>;
    const n = parseInt(match[1], 10);
    const citation = citations[n - 1];
    if (!citation) return <span key={i}>{part}</span>;
    const isHighlighted = citation.citationId === highlightedCitationId;
    return (
      <button
        key={i}
        type="button"
        aria-label={`Citation ${n}`}
        onClick={() => onCitationClick?.(citation.citationId)}
        className={cn(
          "mx-0.5 inline-flex h-4 min-w-[18px] items-center justify-center rounded px-1 font-mono text-[10px] transition-colors",
          "bg-gold-soft text-gold-foreground hover:bg-gold/30",
          isHighlighted && "ring-2 ring-gold",
        )}
      >
        [{n}]
      </button>
    );
  });
}

function VerifiedCard({
  response,
  onCitationClick,
  highlightedCitationId,
}: {
  response: VerifiedResponse;
  onCitationClick?: (citationId: string) => void;
  highlightedCitationId: string | null;
}) {
  return (
    <article
      aria-label="Verified answer"
      className="rounded-lg border border-border bg-card"
    >
      <div className="space-y-3 p-4">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="inline-flex items-center gap-1 rounded-md border border-primary/30 bg-primary-soft px-1.5 py-0.5 text-[10px] font-medium capitalize text-primary">
            <ShieldCheck className="h-2.5 w-2.5" /> Verified
          </span>
          <ConfidenceBadge tier={response.confidenceTier} size="sm" />
          <span className="inline-flex items-center rounded-md border border-border bg-muted px-1.5 py-0.5 text-[10px] font-medium capitalize text-muted-foreground">
            {response.handling.replace(/_/g, " ")}
          </span>
          {response.servedFromCache && (
            <span className="inline-flex items-center rounded-md border border-gold/30 bg-gold-soft px-1.5 py-0.5 text-[10px] font-medium capitalize text-gold-foreground">
              served from cache
            </span>
          )}
        </div>
        <p className="text-[15px] leading-relaxed text-foreground">
          {renderAnswerBody(
            response.answer,
            response.citations,
            onCitationClick,
            highlightedCitationId,
          )}
        </p>
      </div>
    </article>
  );
}

function BlockedCard({ response }: { response: VerifiedResponse }) {
  return (
    <article
      aria-label="Blocked at safety gate"
      className="rounded-lg border border-danger/40 bg-card"
    >
      <div className="flex items-start gap-2 p-4">
        <Ban className="mt-0.5 h-5 w-5 shrink-0 text-danger" />
        <div className="flex-1">
          <div className="mb-2 inline-flex items-center gap-1 rounded-md border border-danger/40 bg-danger-soft px-1.5 py-0.5 text-[10px] font-medium capitalize text-danger">
            <Ban className="h-2.5 w-2.5" /> Blocked
          </div>
          <p className="text-[15px] leading-relaxed text-foreground">{response.answer}</p>
        </div>
      </div>
    </article>
  );
}

function InsufficientCard({ response }: { response: VerifiedResponse }) {
  return (
    <article
      aria-label="Insufficient evidence"
      className="rounded-lg border border-danger/40 bg-card"
    >
      <div className="flex items-start gap-2 p-4">
        <CircleDashed className="mt-0.5 h-5 w-5 shrink-0 text-danger" />
        <div className="flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-1.5">
            <span className="inline-flex items-center gap-1 rounded-md border border-danger/40 bg-danger-soft px-1.5 py-0.5 text-[10px] font-medium capitalize text-danger">
              <AlertTriangle className="h-2.5 w-2.5" /> Insufficient evidence
            </span>
            <ConfidenceBadge tier={response.confidenceTier} size="sm" />
          </div>
          <p className="text-[15px] leading-relaxed text-foreground">{response.answer}</p>
        </div>
      </div>
    </article>
  );
}
