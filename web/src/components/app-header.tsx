import { SidebarTrigger } from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import {
  Building2,
  ChevronDown,
  Globe,
  Languages,
  Moon,
  Sun,
  ShieldCheck,
  CircleDot,
  GitBranch,
} from "lucide-react";
import { useTheme } from "@/lib/theme";
import { tenants } from "@/data/mock";
import { useState } from "react";

export function AppHeader() {
  const { theme, toggle } = useTheme();
  const [tenant, setTenant] = useState(tenants[0]);

  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-2 border-b border-border bg-background/80 px-3 backdrop-blur-sm">
      <SidebarTrigger className="text-muted-foreground" />
      <Separator orientation="vertical" className="mx-1 h-5" />

      {/* Tenant switcher */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="h-8 gap-2 px-2 font-medium">
            <Building2 className="h-3.5 w-3.5 text-primary" />
            <span className="hidden sm:inline">{tenant.name}</span>
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-72">
          <DropdownMenuLabel className="text-xs">Switch tenant</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {tenants.map((t) => (
            <DropdownMenuItem
              key={t.id}
              onClick={() => setTenant(t)}
              className="flex flex-col items-start gap-0.5"
            >
              <div className="flex w-full items-center justify-between">
                <span className="font-medium">{t.name}</span>
                <Badge variant="outline" className="ml-2 text-[10px] capitalize">
                  {t.type}
                </Badge>
              </div>
              <span className="text-xs text-muted-foreground">
                {t.region} · corpus {t.corpusVersion}
              </span>
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Compact context chips */}
      <div className="ml-1 hidden items-center gap-1.5 lg:flex">
        <Chip icon={ShieldCheck} label="Reviewer" tone="primary" />
        <Chip icon={Globe} label={tenant.region} />
        <Chip icon={GitBranch} label={tenant.corpusVersion} mono />
        <Chip icon={CircleDot} label={tenant.policyScope} tone="gold" />
      </div>

      <div className="ml-auto flex items-center gap-1.5">
        {/* Language */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 gap-1.5 px-2 text-xs text-muted-foreground"
            >
              <Languages className="h-3.5 w-3.5" />
              EN
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {["English", "Ελληνικά", "Русский", "Română", "العربية", "Српски"].map((l) => (
              <DropdownMenuItem key={l}>{l}</DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Env badge */}
        <Badge
          variant="outline"
          className="hidden h-7 gap-1.5 border-success/40 bg-success-soft text-[10px] font-medium text-success md:flex"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-success" />
          Production
        </Badge>

        {/* Theme */}
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={toggle}
          aria-label="Toggle theme"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>

        {/* User */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="h-8 gap-2 px-1.5">
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                JB
              </div>
              <span className="hidden text-xs md:inline">Fr. John Behr</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel className="flex flex-col">
              <span>Fr. John Behr</span>
              <span className="text-xs font-normal text-muted-foreground">Admin · SVOTS</span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem>Profile</DropdownMenuItem>
            <DropdownMenuItem>Audit log</DropdownMenuItem>
            <DropdownMenuItem>API keys</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem>Sign out</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}

function Chip({
  icon: Icon,
  label,
  tone,
  mono,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  tone?: "primary" | "gold" | "default";
  mono?: boolean;
}) {
  const toneClass =
    tone === "primary"
      ? "border-primary/30 bg-primary-soft text-primary"
      : tone === "gold"
        ? "border-gold/30 bg-gold-soft text-gold-foreground"
        : "border-border bg-muted text-muted-foreground";
  return (
    <span
      className={`inline-flex h-7 items-center gap-1.5 rounded-md border px-2 text-[11px] ${toneClass} ${
        mono ? "font-mono" : ""
      }`}
    >
      <Icon className="h-3 w-3" />
      {label}
    </span>
  );
}
