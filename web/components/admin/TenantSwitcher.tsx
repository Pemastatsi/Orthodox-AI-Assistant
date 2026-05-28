/**
 * `<TenantSwitcher>` — placeholder. Full multi-tenant switching requires the
 * Clerk session + the tenant config endpoint, both deferred to a follow-up.
 * For now, this just surfaces the current dev tenant.
 */
export interface TenantSwitcherProps {
  tenantId: string;
  role: string;
}

export function TenantSwitcher({ tenantId, role }: TenantSwitcherProps) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-border bg-surface-muted px-2 py-1 text-xs">
      <span className="text-muted-foreground">Tenant</span>
      <span className="font-mono">{tenantId}</span>
      <span className="text-muted-foreground">·</span>
      <span className="capitalize">{role}</span>
    </div>
  );
}
