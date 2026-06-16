import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { PageHeader, PageBody, Section, Stat } from "@/components/page";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  GraduationCap,
  BookOpen,
  Bookmark,
  Check,
  Search,
  Plus,
  Notebook,
  Library,
} from "lucide-react";
import { sources } from "@/data/mock";

export const Route = createFileRoute("/_app/teach-me")({
  component: TeachMe,
});

const PATHS = [
  {
    topic: "The Jesus Prayer",
    description: "From the Philokalia to the Hesychast tradition.",
    levels: [
      { name: "Introductory", lessons: 4, done: 4 },
      { name: "Intermediate", lessons: 6, done: 3 },
      { name: "Advanced", lessons: 5, done: 0 },
    ],
  },
  {
    topic: "Theosis",
    description: "Deification in the Greek Fathers.",
    levels: [
      { name: "Introductory", lessons: 3, done: 3 },
      { name: "Intermediate", lessons: 5, done: 2 },
      { name: "Advanced", lessons: 4, done: 0 },
    ],
  },
  {
    topic: "Confession",
    description: "Sacramental theology and pastoral practice.",
    levels: [
      { name: "Introductory", lessons: 3, done: 1 },
      { name: "Intermediate", lessons: 4, done: 0 },
      { name: "Advanced", lessons: 3, done: 0 },
    ],
  },
];

function TeachMe() {
  const [topic, setTopic] = useState("The Jesus Prayer");
  const path = PATHS.find((p) => p.topic === topic) ?? PATHS[0];
  const total = path.levels.reduce((s, l) => s + l.lessons, 0);
  const done = path.levels.reduce((s, l) => s + l.done, 0);
  return (
    <>
      <PageHeader
        title="Teach Me"
        description="Member-facing learning paths. Source-grounded, citation-backed, progress-tracked."
        actions={
          <Button size="sm" className="gap-1.5">
            <Plus className="h-3.5 w-3.5" /> New path
          </Button>
        }
      />
      <PageBody className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1 space-y-4">
          <Section title="Choose a topic">
            <div className="relative mb-3">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                className="pl-8 h-9 text-sm"
                placeholder="e.g. Philokalia, humility, theosis…"
              />
            </div>
            <ul className="space-y-1.5">
              {PATHS.map((p) => (
                <li key={p.topic}>
                  <button
                    onClick={() => setTopic(p.topic)}
                    className={`w-full rounded-md border px-3 py-2 text-left transition ${
                      p.topic === topic
                        ? "border-primary bg-primary-soft"
                        : "border-border hover:bg-accent/40"
                    }`}
                  >
                    <div className="flex items-center justify-between text-sm font-medium">
                      <span>{p.topic}</span>
                      <Badge variant="outline" className="text-[10px]">
                        {p.levels.reduce((s, l) => s + l.lessons, 0)} lessons
                      </Badge>
                    </div>
                    <div className="text-xs text-muted-foreground">{p.description}</div>
                  </button>
                </li>
              ))}
            </ul>
          </Section>
          <Section title="Reading queue">
            <ul className="space-y-2 text-sm">
              {sources.slice(0, 4).map((s) => (
                <li key={s.id} className="flex items-start gap-2">
                  <Bookmark className="mt-0.5 h-3.5 w-3.5 text-gold-foreground" />
                  <div>
                    <div className="font-medium leading-tight">{s.title}</div>
                    <div className="text-xs text-muted-foreground">{s.author}</div>
                  </div>
                </li>
              ))}
            </ul>
          </Section>
        </div>

        <div className="space-y-4 lg:col-span-2">
          <div className="grid grid-cols-3 gap-3">
            <Stat label="Lessons completed" value={done} hint={`${total} total`} tone="success" />
            <Stat label="Citations read" value={47} />
            <Stat label="Notes saved" value={12} tone="gold" />
          </div>

          <Section title={path.topic} description={path.description}>
            <div className="space-y-5">
              {path.levels.map((lv, idx) => (
                <div key={lv.name}>
                  <div className="mb-1.5 flex items-baseline justify-between">
                    <h4 className="font-serif text-sm font-semibold">
                      {idx + 1}. {lv.name}
                    </h4>
                    <span className="text-xs text-muted-foreground">
                      {lv.done} / {lv.lessons}
                    </span>
                  </div>
                  <Progress value={(lv.done / lv.lessons) * 100} className="h-1.5" />
                </div>
              ))}
            </div>
          </Section>

          <Section
            title="Lesson 4 — The Prayer of the Heart"
            actions={<Badge variant="outline">In progress</Badge>}
          >
            <p className="text-sm leading-relaxed">
              The Jesus Prayer descends from the lips to the heart through repetition and
              watchfulness (νῆψις). The Philokalia teaches it is to be united with the breath, but
              never as a technique pursued apart from a spiritual father.
              <span className="citation-marker mx-1 rounded bg-gold-soft px-1 text-[10px]">
                [1]
              </span>
              St. Gregory Palamas defends this practice as participation in the uncreated light.
              <span className="citation-marker mx-1 rounded bg-gold-soft px-1 text-[10px]">
                [2]
              </span>
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button size="sm" variant="outline" className="gap-1.5">
                <Notebook className="h-3.5 w-3.5" /> Save note
              </Button>
              <Button size="sm" variant="outline" className="gap-1.5">
                <Library className="h-3.5 w-3.5" /> View sources
              </Button>
              <Button size="sm" className="gap-1.5">
                <Check className="h-3.5 w-3.5" /> Mark complete
              </Button>
            </div>
          </Section>
        </div>
      </PageBody>
    </>
  );
}
