/**
 * `<DisputeCard>` — the Logos / VulgateAI differentiator per T-006 task card
 * §"Scholarly Dispute UX". Renders competing patristic positions in
 * **side-by-side columns** (md+ widths) or a labeled vertical stack at mobile
 * widths. Each column carries its own short composed thesis, its own
 * citations (scoped to the column — never aggregated), and its own confidence
 * badge derived from that column's sub-packet.
 *
 * The composed columns must NEVER imply consensus where the evidence shows
 * dispute. This component's contract enforces that visually:
 *   - column boundaries are always visible at every breakpoint;
 *   - the position label (name) is always visible above the thesis;
 *   - the closing banner reinforces that the area is contested and that
 *     both positions remain within Orthodox theological discourse.
 *
 * Backend wiring note: `positions` are accepted as an optional field on
 * `VerifiedResponse`. Until per-column A5 composition lands on the backend
 * (follow-up to T-006), this component renders only when the page supplies
 * `positions` directly.
 */
import { AlertTriangle } from "lucide-react";
import { ConfidenceBadge } from "./ConfidenceBadge";
import type { Citation, Position, VerifiedResponse } from "@/lib/schemas";

export interface DisputeCardProps {
  response: VerifiedResponse;
  positions: Position[];
  onCitationClick?: (citationId: string) => void;
  highlightedCitationId?: string | null;
}

function citationsForPosition(
  position: Position,
  all: Citation[],
): Citation[] {
  const set = new Set(position.citationIds);
  return all.filter((c) => set.has(c.citationId));
}

export function DisputeCard({
  response,
  positions,
  onCitationClick,
  highlightedCitationId = null,
}: DisputeCardProps) {
  return (
    <article
      aria-label="Scholarly dispute — competing positions"
      className="rounded-lg border border-border bg-card"
    >
      <div className="space-y-3 p-4">
        {response.answer && (
          <p className="text-[15px] leading-relaxed text-foreground">
            {response.answer}
          </p>
        )}

        <div
          role="group"
          aria-label="Competing positions"
          className="grid gap-3 md:grid-cols-2"
        >
          {positions.map((position, index) => {
            const positionCitations = citationsForPosition(position, response.citations);
            return (
              <section
                key={position.name}
                aria-label={`Position ${String.fromCharCode(65 + index)}: ${position.name}`}
                className="flex flex-col gap-2 rounded-md border border-border bg-surface-muted p-3"
              >
                <header className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <span
                      aria-hidden="true"
                      className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground"
                    >
                      {String.fromCharCode(65 + index)}
                    </span>
                    <h4 className="font-serif text-sm font-semibold">
                      {position.name}
                    </h4>
                  </div>
                  <ConfidenceBadge tier={position.confidenceTier} size="sm" />
                </header>
                <p className="text-sm text-foreground">{position.thesis}</p>
                {positionCitations.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {positionCitations.map((c) => {
                      const isHighlighted = c.citationId === highlightedCitationId;
                      return (
                        <button
                          key={c.citationId}
                          type="button"
                          aria-label={`Citation: ${c.father ?? c.title}`}
                          aria-current={isHighlighted ? "true" : undefined}
                          onClick={() => onCitationClick?.(c.citationId)}
                          className={
                            "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] transition-colors " +
                            (isHighlighted
                              ? "border-gold ring-2 ring-gold/40 bg-gold-soft text-gold-foreground"
                              : "border-gold/30 bg-gold-soft hover:bg-gold/30 text-gold-foreground")
                          }
                        >
                          {c.father ?? c.title}
                        </button>
                      );
                    })}
                  </div>
                )}
              </section>
            );
          })}
        </div>

        <div className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning-soft/40 px-3 py-2 text-xs text-warning-foreground">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            Contested area — both positions remain within Orthodox theological
            discourse. The library does not pick a winner.
          </span>
        </div>
      </div>
    </article>
  );
}
