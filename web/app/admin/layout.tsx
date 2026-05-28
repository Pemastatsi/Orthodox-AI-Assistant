/**
 * Admin layout — shared chrome for /admin/* pages. Renders the persistent
 * left navigation between the four read surfaces (queries, flagged, audit,
 * corpus) and the tenant switcher in the header.
 *
 * Auth: server-side dev principal is read by each page individually (no
 * cookie session yet); the layout's TenantSwitcher mirrors it for visibility.
 */
import Link from "next/link";
import type { Route } from "next";
import { TenantSwitcher } from "@/components/admin/TenantSwitcher";
import { serverDevPrincipal } from "@/lib/admin-api";

const NAV: { href: Route; label: string }[] = [
  { href: "/admin/queries", label: "Query log" },
  { href: "/admin/flagged", label: "Flagged queries" },
  { href: "/admin/audit", label: "Audit" },
  { href: "/admin/corpus", label: "Corpus approval" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const principal = serverDevPrincipal();
  return (
    <main className="flex h-screen flex-col bg-background">
      <header className="flex items-center justify-between border-b border-border bg-surface px-6 py-3">
        <div>
          <h1 className="font-serif text-lg font-semibold">
            Orthodox AI Assistant — Admin
          </h1>
          <p className="text-xs text-muted-foreground">
            Per-tenant operational surfaces. Sensitive content respects role-scope redaction.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="text-xs text-muted-foreground underline-offset-4 hover:underline"
          >
            ← Back to chat
          </Link>
          <TenantSwitcher tenantId={principal.tenantId} role={principal.role} />
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <aside className="w-56 shrink-0 border-r border-border bg-surface-muted py-4">
          <nav aria-label="Admin sections">
            <ul>
              {NAV.map((item) => (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className="block px-4 py-2 text-sm text-foreground hover:bg-accent"
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </aside>
        <section className="min-w-0 flex-1 overflow-auto p-6">{children}</section>
      </div>
    </main>
  );
}
