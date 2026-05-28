/**
 * `<ConfidenceBadge>` — visual badge for confidence tier per
 * `frontend-components.md`. Color is the redundant cue, not the only one
 * (accessibility requirement). Tier label is always rendered as text.
 */
import { cn } from "@/lib/utils";
import type { ConfidenceTier } from "@/lib/schemas";

const tierStyles: Record<ConfidenceTier, { dot: string; chip: string; label: string }> = {
  GREEN: {
    dot: "bg-success",
    chip: "border-success/40 bg-success-soft text-success",
    label: "High confidence",
  },
  YELLOW: {
    dot: "bg-info",
    chip: "border-info/40 bg-info-soft text-info",
    label: "Moderate confidence",
  },
  RED: {
    dot: "bg-danger",
    chip: "border-danger/40 bg-danger-soft text-danger",
    label: "Low confidence",
  },
};

export interface ConfidenceBadgeProps {
  tier: ConfidenceTier;
  size?: "sm" | "md";
}

export function ConfidenceBadge({ tier, size = "md" }: ConfidenceBadgeProps) {
  const style = tierStyles[tier];
  const padding = size === "sm" ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-1 text-xs";
  return (
    <span
      role="status"
      aria-label={`${style.label} (${tier})`}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border font-medium",
        style.chip,
        padding,
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", style.dot)} aria-hidden="true" />
      {style.label}
    </span>
  );
}
