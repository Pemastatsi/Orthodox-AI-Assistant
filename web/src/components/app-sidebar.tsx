import { Link, useLocation } from "@tanstack/react-router";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarFooter,
  useSidebar,
} from "@/components/ui/sidebar";
import {
  MessagesSquare,
  GraduationCap,
  FlaskConical,
  Workflow,
  Library,
  Quote,
  ShieldCheck,
  Network,
  Scale,
  AlertTriangle,
  History,
  ShieldAlert,
  Cpu,
  Beaker,
  BarChart3,
  Users,
  CreditCard,
  Settings,
  Code2,
  CloudDownload,
  Cross,
} from "lucide-react";

type Item = { to: string; label: string; icon: React.ComponentType<{ className?: string }> };

const groups: { label: string; items: Item[] }[] = [
  {
    label: "Ask & Learn",
    items: [
      { to: "/assistant", label: "Assistant", icon: MessagesSquare },
      { to: "/teach-me", label: "Teach Me", icon: GraduationCap },
      { to: "/research", label: "Research Workbench", icon: FlaskConical },
    ],
  },
  {
    label: "Operations",
    items: [
      { to: "/workflows", label: "Workflows", icon: Workflow },
      { to: "/history", label: "Query History", icon: History },
      { to: "/analytics", label: "Analytics", icon: BarChart3 },
    ],
  },
  {
    label: "Corpus Governance",
    items: [
      { to: "/corpus", label: "Corpus", icon: Library },
      { to: "/citations", label: "Citations", icon: Quote },
      { to: "/attestations", label: "Attestations", icon: ShieldCheck },
      { to: "/lineage", label: "Lineage Graph", icon: Network },
      { to: "/gaps", label: "Gaps & Content", icon: AlertTriangle },
    ],
  },
  {
    label: "Institutional Governance",
    items: [
      { to: "/governance", label: "Governance", icon: Scale },
      { to: "/safety", label: "Safety Gate", icon: ShieldAlert },
    ],
  },
  {
    label: "Configuration",
    items: [
      { to: "/model-routes", label: "Model Routes", icon: Cpu },
      { to: "/prompt-lab", label: "Prompt Lab", icon: Beaker },
    ],
  },
  {
    label: "Tenant Admin",
    items: [
      { to: "/team", label: "Team", icon: Users },
      { to: "/billing", label: "Billing", icon: CreditCard },
      { to: "/settings", label: "Tenant Settings", icon: Settings },
    ],
  },
  {
    label: "Distribution",
    items: [
      { to: "/widget", label: "Widget", icon: Code2 },
      { to: "/offline", label: "Offline Sync", icon: CloudDownload },
    ],
  },
];

export function AppSidebar() {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const location = useLocation();
  const isActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(path + "/");

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="border-b border-sidebar-border">
        <Link
          to="/assistant"
          className="flex items-center gap-2.5 px-2 py-2 transition-opacity hover:opacity-80"
        >
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Cross className="h-4 w-4" strokeWidth={2.5} />
          </div>
          {!collapsed && (
            <div className="flex flex-col leading-tight">
              <span className="font-serif text-base font-semibold">Patristic</span>
              <span className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                Library Assistant
              </span>
            </div>
          )}
        </Link>
      </SidebarHeader>

      <SidebarContent className="gap-0">
        {groups.map((g) => (
          <SidebarGroup key={g.label}>
            {!collapsed && (
              <SidebarGroupLabel className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground/80">
                {g.label}
              </SidebarGroupLabel>
            )}
            <SidebarGroupContent>
              <SidebarMenu>
                {g.items.map((item) => {
                  const active = isActive(item.to);
                  return (
                    <SidebarMenuItem key={item.to}>
                      <SidebarMenuButton
                        asChild
                        isActive={active}
                        tooltip={item.label}
                        className="data-[active=true]:bg-sidebar-accent data-[active=true]:text-sidebar-accent-foreground data-[active=true]:font-medium"
                      >
                        <Link to={item.to}>
                          <item.icon className="h-4 w-4" />
                          <span>{item.label}</span>
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border">
        {!collapsed ? (
          <div className="px-2 py-2 text-[11px] text-muted-foreground">
            Corpus <span className="font-mono text-foreground">v2024.11.3</span>
            <div className="text-muted-foreground/70">approved · attested</div>
          </div>
        ) : (
          <div className="flex justify-center py-2">
            <span className="h-1.5 w-1.5 rounded-full bg-success" />
          </div>
        )}
      </SidebarFooter>
    </Sidebar>
  );
}
