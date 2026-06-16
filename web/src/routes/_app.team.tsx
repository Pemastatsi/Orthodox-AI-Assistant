import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, PageBody, Section } from "@/components/page";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { members } from "@/data/mock";
import { UserPlus } from "lucide-react";

export const Route = createFileRoute("/_app/team")({ component: Team });

function Team() {
  return (
    <>
      <PageHeader
        title="Team"
        description="Members, roles, and invitations. Role changes are audited."
        actions={
          <Button size="sm" className="gap-1.5">
            <UserPlus className="h-3.5 w-3.5" /> Invite member
          </Button>
        }
      />
      <PageBody>
        <Section>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[10px] uppercase tracking-wider text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Member</th>
                <th className="py-2 pr-3 font-medium">Role</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 pr-3 font-medium">Joined</th>
                <th className="py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {members.map((m) => (
                <tr key={m.id} className="hover:bg-accent/30">
                  <td className="py-2.5 pr-3">
                    <div className="flex items-center gap-2">
                      <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-[10px] font-semibold text-primary">
                        {m.name
                          .split(" ")
                          .map((n) => n[0])
                          .slice(0, 2)
                          .join("")}
                      </div>
                      <div>
                        <div className="font-medium leading-tight">{m.name}</div>
                        <div className="text-xs text-muted-foreground">{m.email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="py-2.5 pr-3">
                    <Badge variant="outline" className="capitalize">
                      {m.role}
                    </Badge>
                  </td>
                  <td className="py-2.5 pr-3">
                    <Badge
                      variant="outline"
                      className={
                        m.active
                          ? "border-success/30 bg-success-soft text-success"
                          : "border-border bg-muted text-muted-foreground"
                      }
                    >
                      {m.active ? "active" : "inactive"}
                    </Badge>
                  </td>
                  <td className="py-2.5 pr-3 font-mono text-xs text-muted-foreground">
                    {m.joined}
                  </td>
                  <td className="py-2.5">
                    <Button variant="ghost" size="sm" className="h-7 text-xs">
                      Manage
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      </PageBody>
    </>
  );
}
