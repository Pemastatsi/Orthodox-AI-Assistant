import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, PageBody, Section, Stat } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { ShieldCheck, Mic, ScanText, FileSignature, Languages, Users } from "lucide-react";
import { sources } from "@/data/mock";

export const Route = createFileRoute("/_app/attestations")({
  component: Attestations,
});

function Attestations() {
  return (
    <>
      <PageHeader
        title="Attestations"
        description="Chain of custody for every source — extraction method, transcription confidence, translation status, quote integrity, reviewer sign-off."
      />
      <PageBody className="space-y-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat
            label="Signed off"
            value={sources.filter((s) => s.attestation.signedOff).length}
            tone="success"
          />
          <Stat
            label="Unsigned"
            value={sources.filter((s) => !s.attestation.signedOff).length}
            tone="warning"
          />
          <Stat
            label="OCR/Whisper"
            value={sources.filter((s) => s.attestation.extraction !== "Native").length}
          />
          <Stat label="Avg. quote integrity" value="95%" tone="gold" />
        </div>

        <Section title="Sources by attestation chain">
          <div className="space-y-3">
            {sources.map((s) => (
              <div key={s.id} className="rounded-lg border border-border bg-card p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="font-serif text-base font-semibold">{s.title}</div>
                    <div className="text-xs text-muted-foreground">
                      {s.author} · {s.work}
                    </div>
                  </div>
                  <Badge
                    variant="outline"
                    className={
                      s.attestation.signedOff
                        ? "border-success/30 bg-success-soft text-success"
                        : "border-warning/40 bg-warning-soft text-warning-foreground"
                    }
                  >
                    {s.attestation.signedOff ? "Signed off" : "Unsigned"}
                  </Badge>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-3 text-xs md:grid-cols-5">
                  <Field icon={ScanText} label="Extraction" value={s.attestation.extraction} />
                  <Field
                    icon={Mic}
                    label="Transcription"
                    value={
                      s.attestation.transcriptionConfidence
                        ? `${Math.round(s.attestation.transcriptionConfidence * 100)}%`
                        : "—"
                    }
                  />
                  <Field
                    icon={Languages}
                    label="Translation"
                    value={s.attestation.translationStatus}
                  />
                  <Field
                    icon={ShieldCheck}
                    label="Quote integrity"
                    value={`${Math.round(s.attestation.quoteIntegrity * 100)}%`}
                  />
                  <Field
                    icon={Users}
                    label="Parallel witnesses"
                    value={s.attestation.parallelWitnesses.toString()}
                  />
                </div>
                {s.reviewer && (
                  <div className="mt-3 flex items-center gap-1.5 border-t border-border pt-2 text-xs text-muted-foreground">
                    <FileSignature className="h-3 w-3" /> Reviewed by{" "}
                    <span className="font-medium text-foreground">{s.reviewer}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </Section>
      </PageBody>
    </>
  );
}

function Field({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-md border border-border bg-muted/40 px-2.5 py-1.5">
      <div className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground">
        <Icon className="h-3 w-3" /> {label}
      </div>
      <div className="mt-0.5 text-sm font-medium capitalize">{value}</div>
    </div>
  );
}
