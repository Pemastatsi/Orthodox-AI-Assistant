import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { PageHeader, PageBody, Section, Stat } from "@/components/page";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Upload,
  Search,
  Library,
  Youtube,
  FileAudio,
  FileText,
  FileType,
  Inbox,
  History,
  Eye,
} from "lucide-react";
import { sources, chunks } from "@/data/mock";
import type { Source, ApprovalState } from "@/data/types";

export const Route = createFileRoute("/_app/corpus")({
  component: Corpus,
});

const APPROVAL_TONE: Record<ApprovalState, string> = {
  candidate: "border-warning/40 bg-warning-soft text-warning-foreground",
  approved: "border-success/30 bg-success-soft text-success",
  rejected: "border-danger/40 bg-danger-soft text-danger",
  suppressed: "border-border bg-muted text-muted-foreground",
  admin_only: "border-primary/30 bg-primary-soft text-primary",
  scholarly_only: "border-gold/30 bg-gold-soft text-gold-foreground",
};

const TYPE_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  PDF: FileType,
  Audio: FileAudio,
  YouTube: Youtube,
  TXT: FileText,
  Markdown: FileText,
  DOCX: FileText,
};

function Corpus() {
  const [filter, setFilter] = useState("");
  const filtered = sources.filter(
    (s) =>
      s.title.toLowerCase().includes(filter.toLowerCase()) ||
      s.author.toLowerCase().includes(filter.toLowerCase()),
  );
  const candidates = chunks.filter((c) => c.approval === "candidate");

  return (
    <>
      <PageHeader
        title="Corpus"
        description="The approved tenant library — sources, chunks, attestation, version history, and visibility governance."
        badges={
          <Badge variant="outline" className="ml-2 font-mono">
            v2024.11.3
          </Badge>
        }
        actions={
          <>
            <Button size="sm" variant="outline" className="gap-1.5">
              <History className="h-3.5 w-3.5" /> Version history
            </Button>
            <Button size="sm" className="gap-1.5">
              <Upload className="h-3.5 w-3.5" /> Upload sources
            </Button>
          </>
        }
      />
      <PageBody className="space-y-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <Stat label="Sources" value={sources.length} />
          <Stat label="Chunks" value={chunks.length * 60} hint="approved" />
          <Stat label="Candidates" value={candidates.length} tone="warning" />
          <Stat label="Suppressed" value={3} />
          <Stat label="Languages" value={6} tone="gold" />
        </div>

        <Tabs defaultValue="library">
          <TabsList className="bg-muted">
            <TabsTrigger value="library" className="gap-1.5">
              <Library className="h-3.5 w-3.5" /> Library
            </TabsTrigger>
            <TabsTrigger value="queue" className="gap-1.5">
              <Inbox className="h-3.5 w-3.5" /> Approval queue ({candidates.length})
            </TabsTrigger>
            <TabsTrigger value="ingest" className="gap-1.5">
              <Upload className="h-3.5 w-3.5" /> Ingestion
            </TabsTrigger>
            <TabsTrigger value="youtube" className="gap-1.5">
              <Youtube className="h-3.5 w-3.5" /> YouTube monitor
            </TabsTrigger>
          </TabsList>

          <TabsContent value="library" className="mt-3">
            <Section
              title="Sources"
              actions={
                <div className="relative w-64">
                  <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                  <Input
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                    placeholder="Search title or author…"
                    className="h-8 pl-8 text-sm"
                  />
                </div>
              }
            >
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-[10px] uppercase tracking-wider text-muted-foreground">
                      <th className="py-2 pr-3 font-medium">Source</th>
                      <th className="py-2 pr-3 font-medium">Author</th>
                      <th className="py-2 pr-3 font-medium">Type</th>
                      <th className="py-2 pr-3 font-medium">Lang</th>
                      <th className="py-2 pr-3 font-medium">Approval</th>
                      <th className="py-2 pr-3 font-medium">Visibility</th>
                      <th className="py-2 pr-3 font-medium">Quote integrity</th>
                      <th className="py-2 pr-3 font-medium">Hash</th>
                      <th className="py-2 font-medium"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {filtered.map((s) => (
                      <SourceRow key={s.id} s={s} />
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
          </TabsContent>

          <TabsContent value="queue" className="mt-3">
            <Section
              title="Chunk approval queue"
              description="Awaiting reviewer sign-off before they may serve as evidence."
            >
              {candidates.length === 0 ? (
                <p className="text-sm text-muted-foreground">No chunks pending.</p>
              ) : (
                <ul className="space-y-3">
                  {candidates.map((c) => (
                    <li
                      key={c.id}
                      className="rounded-md border border-warning/40 bg-warning-soft/40 p-3"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-xs text-muted-foreground">
                            {c.timestamp ?? `p. ${c.page}`} · {c.categories.join(", ")}
                          </div>
                          <p className="mt-0.5 font-serif text-sm italic">"{c.text}"</p>
                          <div className="mt-1 font-mono text-[10px] text-muted-foreground">
                            {c.hash}
                          </div>
                        </div>
                        <div className="flex shrink-0 gap-1.5">
                          <Button size="sm" variant="outline">
                            Reject
                          </Button>
                          <Button size="sm" variant="outline">
                            Suppress
                          </Button>
                          <Button size="sm">Approve</Button>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          </TabsContent>

          <TabsContent value="ingest" className="mt-3">
            <Section title="Ingestion queue">
              <div className="space-y-2 text-sm">
                {[
                  { f: "philokalia-vol-3.pdf", state: "Embedding (chunk 218 / 412)", pct: 53 },
                  { f: "lecture-13-trinity.mp3", state: "Whisper transcribing", pct: 78 },
                  { f: "diocese-encyclical-2025.docx", state: "Awaiting metadata", pct: 0 },
                ].map((i) => (
                  <div key={i.f} className="rounded-md border border-border bg-card p-3">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{i.f}</span>
                      <span className="text-xs text-muted-foreground">{i.state}</span>
                    </div>
                    <div className="mt-1 h-1 overflow-hidden rounded-full bg-muted">
                      <div className="h-full bg-primary" style={{ width: `${i.pct}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          </TabsContent>

          <TabsContent value="youtube" className="mt-3">
            <Section
              title="YouTube auto-ingestion"
              description="Monitored channels and recent imports."
            >
              <ul className="divide-y divide-border text-sm">
                {[
                  {
                    channel: "Holy Trinity Jordanville",
                    videos: 142,
                    lastSync: "2025-04-26 02:00",
                    status: "ok",
                  },
                  {
                    channel: "St. Vladimir's Seminary",
                    videos: 89,
                    lastSync: "2025-04-26 02:00",
                    status: "ok",
                  },
                  {
                    channel: "Antiochian Archdiocese",
                    videos: 67,
                    lastSync: "2025-04-25 22:14",
                    status: "rate-limited",
                  },
                ].map((c) => (
                  <li key={c.channel} className="flex items-center justify-between py-2.5">
                    <div>
                      <div className="font-medium">{c.channel}</div>
                      <div className="text-xs text-muted-foreground">
                        {c.videos} videos · last sync {c.lastSync}
                      </div>
                    </div>
                    <Badge
                      variant="outline"
                      className={
                        c.status === "ok"
                          ? "border-success/30 bg-success-soft text-success"
                          : "border-warning/40 bg-warning-soft text-warning-foreground"
                      }
                    >
                      {c.status}
                    </Badge>
                  </li>
                ))}
              </ul>
            </Section>
          </TabsContent>
        </Tabs>
      </PageBody>
    </>
  );
}

function SourceRow({ s }: { s: Source }) {
  const Icon = TYPE_ICON[s.type] ?? FileText;
  return (
    <tr className="hover:bg-accent/30">
      <td className="py-2.5 pr-3">
        <div className="flex items-center gap-2">
          <Icon className="h-3.5 w-3.5 text-muted-foreground" />
          <div>
            <div className="font-medium leading-tight">{s.title}</div>
            <div className="text-[11px] text-muted-foreground italic">{s.work}</div>
          </div>
        </div>
      </td>
      <td className="py-2.5 pr-3 text-xs">
        <div>{s.author}</div>
        {s.authorRole && <div className="text-muted-foreground">{s.authorRole}</div>}
      </td>
      <td className="py-2.5 pr-3 text-xs">{s.type}</td>
      <td className="py-2.5 pr-3 font-mono text-xs uppercase text-muted-foreground">
        {s.language}
      </td>
      <td className="py-2.5 pr-3">
        <span
          className={`inline-flex rounded-md border px-1.5 py-0.5 text-[10px] font-medium capitalize ${APPROVAL_TONE[s.approval]}`}
        >
          {s.approval.replace(/_/g, " ")}
        </span>
      </td>
      <td className="py-2.5 pr-3 text-xs capitalize">{s.visibility}</td>
      <td className="py-2.5 pr-3 tabular text-xs">
        {Math.round(s.attestation.quoteIntegrity * 100)}%
      </td>
      <td className="py-2.5 pr-3 font-mono text-[10px] text-muted-foreground">
        {s.hash.slice(0, 18)}…
      </td>
      <td className="py-2.5">
        <Button variant="ghost" size="sm" className="h-7 gap-1.5 text-xs">
          <Eye className="h-3 w-3" /> View
        </Button>
      </td>
    </tr>
  );
}
