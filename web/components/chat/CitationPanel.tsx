/**
 * `<CitationPanel>` — citation list scoped to a `VerifiedResponse`. Each row
 * exposes the source title, the patristic father (if known), work, page or
 * timestamp, and the quote excerpt. Clicking a row scrolls into view and emits
 * `onCitationClick`.
 *
 * `evidencePacket` (suppressed-chunk metadata, A4 confidence breakdown) is
 * intentionally hidden in member view per closed-corpus governance — the
 * `evidencePacket` prop is accepted but not rendered when the caller is a
 * member. The full evidence packet view lands in B.4 admin surfaces.
 */
"use client";

import { Quote } from "lucide-react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { Citation } from "@/lib/schemas";

export interface EvidencePacket {
  /** Reserved for the B.4 admin view; not rendered in member view. */
  admittedChunkIds: string[];
  suppressedChunkIds: string[];
  confidenceTier: "GREEN" | "YELLOW" | "RED";
}

export interface CitationPanelProps {
  citations: Citation[];
  evidencePacket?: EvidencePacket;
  highlightedCitationId: string | null;
  onCitationClick?: (citationId: string) => void;
}

export function CitationPanel({
  citations,
  highlightedCitationId,
  onCitationClick,
}: CitationPanelProps) {
  if (citations.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
        No citations — answer was not composed.
      </div>
    );
  }

  return (
    <ScrollArea className="h-full">
      <ol className="space-y-2.5">
        {citations.map((c, idx) => {
          const marker = idx + 1;
          const isHighlighted = c.citationId === highlightedCitationId;
          return (
            <li key={c.citationId}>
              <button
                type="button"
                aria-current={isHighlighted ? "true" : undefined}
                aria-label={`Citation ${marker}: ${c.title}`}
                onClick={() => onCitationClick?.(c.citationId)}
                className={cn(
                  "block w-full rounded-md border bg-card p-3 text-left transition-colors hover:bg-accent/40",
                  isHighlighted
                    ? "border-gold ring-2 ring-gold/40"
                    : "border-border",
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <span
                      aria-hidden="true"
                      className="rounded bg-gold-soft px-1.5 py-0.5 font-mono text-xs text-gold-foreground"
                    >
                      [{marker}]
                    </span>
                    <span className="font-serif text-sm font-semibold leading-tight">
                      {c.title}
                    </span>
                  </div>
                </div>
                <div className="mt-0.5 text-[11px] text-muted-foreground">
                  {c.father && <span>{c.father}</span>}
                  {c.father && c.work && <span> · </span>}
                  {c.work && <span>{c.work}</span>}
                  {c.page && <span> · p. {c.page}</span>}
                  {!c.page && c.timestamp && <span> · {c.timestamp}</span>}
                </div>
                {c.quote && (
                  <blockquote className="mt-2 border-l-2 border-gold pl-2 font-serif text-sm italic text-foreground/90">
                    <Quote className="mr-1 inline h-3 w-3 text-gold-foreground" />
                    {c.quote}
                  </blockquote>
                )}
              </button>
            </li>
          );
        })}
      </ol>
    </ScrollArea>
  );
}
