import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { PageHeader, PageBody, Section, Stat } from "@/components/page";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  FlaskConical,
  FileDown,
  GitBranch,
  Plus,
  FileText,
  Quote,
  Layers,
  BookMarked,
  Clock,
  Network,
} from "lucide-react";

export const Route = createFileRoute("/_app/research")({
  component: Research,
});

const WORKSPACES = [
  {
    id: "ws-1",
    title: "Cappadocian Trinitarian Grammar",
    owner: "Dr. Bucur",
    claims: 14,
    sources: 22,
    updated: "1h ago",
  },
  {
    id: "ws-2",
    title: "Hesychast Controversy — 1341",
    owner: "Fr. Behr",
    claims: 9,
    sources: 17,
    updated: "3h ago",
  },
  {
    id: "ws-3",
    title: "Eucharistic Ecclesiology — Schmemann",
    owner: "Fr. Michael",
    claims: 7,
    sources: 12,
    updated: "yesterday",
  },
  {
    id: "ws-4",
    title: "Theosis vs. Deification — Modern Debates",
    owner: "Dr. Bucur",
    claims: 21,
    sources: 31,
    updated: "2d ago",
  },
];

const CLAIMS = [
  {
    id: "c-1",
    text: "The essence/energies distinction is metaphysically real, not nominal.",
    status: "supported",
    coverage: 0.92,
  },
  {
    id: "c-2",
    text: "Hesychast bodily techniques are normative for noetic prayer.",
    status: "contested",
    coverage: 0.61,
  },
  {
    id: "c-3",
    text: "Florovsky reads Palamas through neo-patristic synthesis.",
    status: "supported",
    coverage: 0.84,
  },
  {
    id: "c-4",
    text: "Western Scholastic categories distort the patristic grammar.",
    status: "contested",
    coverage: 0.55,
  },
  { id: "c-5", text: "The Tabor light is uncreated.", status: "supported", coverage: 0.97 },
  {
    id: "c-6",
    text: "Akindynos's critique survives modern reassessment.",
    status: "insufficient",
    coverage: 0.22,
  },
];

function Research() {
  const [active, setActive] = useState(WORKSPACES[1]);
  return (
    <>
      <PageHeader
        title="Research Workbench"
        description="A scholarly workspace for clergy reviewers, professors, and content teams. Claims, citations, lineage — all evidence-bound."
        badges={
          <Badge variant="outline" className="ml-2">
            Scholar role
          </Badge>
        }
        actions={
          <>
            <Button size="sm" variant="outline" className="gap-1.5">
              <FileDown className="h-3.5 w-3.5" /> Export bundle
            </Button>
            <Button size="sm" className="gap-1.5">
              <Plus className="h-3.5 w-3.5" /> New workspace
            </Button>
          </>
        }
      />
      <PageBody className="grid gap-6 lg:grid-cols-12">
        <aside className="lg:col-span-3">
          <Section title="Workspaces">
            <ul className="space-y-1">
              {WORKSPACES.map((w) => (
                <li key={w.id}>
                  <button
                    onClick={() => setActive(w)}
                    className={`w-full rounded-md border px-3 py-2 text-left ${
                      w.id === active.id
                        ? "border-primary bg-primary-soft"
                        : "border-border hover:bg-accent/40"
                    }`}
                  >
                    <div className="text-sm font-medium leading-tight">{w.title}</div>
                    <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
                      <span>{w.owner}</span>
                      <span>·</span>
                      <span>{w.claims} claims</span>
                      <span className="ml-auto">{w.updated}</span>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </Section>
        </aside>

        <div className="space-y-4 lg:col-span-9">
          <div className="grid grid-cols-4 gap-3">
            <Stat label="Claims" value={active.claims} />
            <Stat label="Sources" value={active.sources} />
            <Stat label="Citations" value={68} tone="gold" />
            <Stat label="Bundles ready" value={2} tone="success" />
          </div>

          <Tabs defaultValue="claims">
            <TabsList className="bg-muted">
              <TabsTrigger value="board" className="gap-1.5">
                <Layers className="h-3.5 w-3.5" /> Evidence board
              </TabsTrigger>
              <TabsTrigger value="claims" className="gap-1.5">
                <FlaskConical className="h-3.5 w-3.5" /> Claims
              </TabsTrigger>
              <TabsTrigger value="sources" className="gap-1.5">
                <BookMarked className="h-3.5 w-3.5" /> Sources
              </TabsTrigger>
              <TabsTrigger value="notes" className="gap-1.5">
                <FileText className="h-3.5 w-3.5" /> Notes
              </TabsTrigger>
              <TabsTrigger value="bundles" className="gap-1.5">
                <GitBranch className="h-3.5 w-3.5" /> Bundles
              </TabsTrigger>
              <TabsTrigger value="timeline" className="gap-1.5">
                <Clock className="h-3.5 w-3.5" /> Timeline
              </TabsTrigger>
              <TabsTrigger value="dispute" className="gap-1.5">
                <Network className="h-3.5 w-3.5" /> Dispute map
              </TabsTrigger>
            </TabsList>

            <TabsContent value="claims" className="mt-3">
              <Section>
                <ul className="divide-y divide-border">
                  {CLAIMS.map((c) => (
                    <li key={c.id} className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
                      <Quote className="mt-1 h-3.5 w-3.5 text-gold-foreground" />
                      <div className="flex-1">
                        <div className="text-sm">{c.text}</div>
                        <div className="mt-1 flex items-center gap-2">
                          <Badge
                            className={
                              c.status === "supported"
                                ? "bg-success-soft text-success border-success/30"
                                : c.status === "contested"
                                  ? "bg-warning-soft text-warning-foreground border-warning/40"
                                  : "bg-danger-soft text-danger border-danger/40"
                            }
                            variant="outline"
                          >
                            {c.status}
                          </Badge>
                          <span className="text-[11px] text-muted-foreground">
                            {Math.round(c.coverage * 100)}% coverage
                          </span>
                        </div>
                      </div>
                      <Button variant="ghost" size="sm" className="h-7 text-xs">
                        Open
                      </Button>
                    </li>
                  ))}
                </ul>
              </Section>
            </TabsContent>

            <TabsContent value="board" className="mt-3">
              <Section>
                <p className="text-sm text-muted-foreground">
                  Drag-and-drop evidence board (preview): pin chunks, group by theme, link claims to
                  sources.
                </p>
              </Section>
            </TabsContent>
            <TabsContent value="sources" className="mt-3">
              <Section>
                <p className="text-sm text-muted-foreground">
                  Sources list — same shape as the Corpus library, scoped to this workspace.
                </p>
              </Section>
            </TabsContent>
            <TabsContent value="notes" className="mt-3">
              <Section>
                <p className="text-sm text-muted-foreground">
                  Reviewer notes, drafts, and marginalia — versioned and exportable.
                </p>
              </Section>
            </TabsContent>
            <TabsContent value="bundles" className="mt-3">
              <Section>
                <p className="text-sm text-muted-foreground">
                  Argument bundles, reading packets, citation reports — ready to export as DOCX/PDF.
                </p>
              </Section>
            </TabsContent>
            <TabsContent value="timeline" className="mt-3">
              <Section>
                <p className="text-sm text-muted-foreground">
                  Chronological view of evidence by century / period.
                </p>
              </Section>
            </TabsContent>
            <TabsContent value="dispute" className="mt-3">
              <Section>
                <p className="text-sm text-muted-foreground">
                  Force-directed dispute map — positions, opponents, mediating witnesses.
                </p>
              </Section>
            </TabsContent>
          </Tabs>
        </div>
      </PageBody>
    </>
  );
}
