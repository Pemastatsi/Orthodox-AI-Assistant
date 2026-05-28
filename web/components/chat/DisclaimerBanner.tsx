/**
 * `<DisclaimerBanner>` — rendered above the answer when
 * `response.handling === "answer_with_disclaimer"`. The exact phrasing is tenant-
 * configurable via `templateId` (Phase 1 currently ships the canonical default;
 * the resolver wiring lands with the tenant config endpoint).
 */
import { AlertTriangle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import type { SensitivityPrimary } from "@/lib/schemas";

const categoryCopy: Partial<Record<SensitivityPrimary, { title: string; body: string }>> = {
  medical: {
    title: "Medical context",
    body: "This is not medical advice. Please consult a qualified clinician for diagnosis or treatment.",
  },
  comparative_religion: {
    title: "Comparative-religion context",
    body: "This answer compares Orthodox teaching with other traditions; emphasis remains on the approved Orthodox sources.",
  },
  canonical_dispute: {
    title: "Canonical-dispute context",
    body: "Sources in the approved corpus differ on this question; the answer surfaces the contested points.",
  },
};

const defaultCopy = {
  title: "Sensitive context",
  body: "This question touches on a sensitive area; please read the citations alongside the answer.",
};

export interface DisclaimerBannerProps {
  category: SensitivityPrimary;
  templateId?: string;
}

export function DisclaimerBanner({ category, templateId }: DisclaimerBannerProps) {
  // templateId is reserved for tenant-overridable text (wired in T-007/T-008);
  // until that lands, fall back to the per-category default copy below.
  void templateId;
  const copy = categoryCopy[category] ?? defaultCopy;
  return (
    <Alert className="border-warning/40 bg-warning-soft/40 text-warning-foreground">
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle>{copy.title}</AlertTitle>
      <AlertDescription>{copy.body}</AlertDescription>
    </Alert>
  );
}
