import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  Database,
  Download,
  ExternalLink,
  Info,
  KeyRound,
  Moon,
  Palette,
  ServerCog,
  ShieldCheck,
  Sparkles,
  Sun,
  Terminal,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useTheme } from "@/components/theme-provider";
import { useTenant } from "@/components/tenant-provider";
import { useOverview, useSeedDemo } from "@/hooks/use-api";
import { api, clearApiToken, getApiToken, setApiToken } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";

const envVars = [
  ["ERASUREPROOF_ENVIRONMENT", "development", "Runtime label shown in the console."],
  ["ERASUREPROOF_AUTH_MODE", "disabled", "disabled, api_key, or oidc. Production must not use disabled."],
  ["ERASUREPROOF_REQUIRE_REMEDIATION_APPROVAL", "false", "Require a second administrator to approve destructive runs."],
  ["ERASUREPROOF_RATE_LIMIT_PER_MINUTE", "0", "Per-process request limit for /v1 endpoints."],
  ["ERASUREPROOF_METRICS_TOKEN", "—", "Bearer token for Prometheus scraping when set."],
  ["ERASUREPROOF_DEMO_ENABLED", "true", "Expose the non-destructive demo bootstrap endpoint."],
  ["ERASUREPROOF_EXPOSURE_ENABLED", "false", "Enable passive public-source collection."],
  ["ERASUREPROOF_DATABASE_URL", "sqlite:///…", "SQLite or PostgreSQL metadata store."],
  ["ERASUREPROOF_DATA_DIR", "./.erasureproof", "Evidence objects, ledger, and attestations."],
];

export function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const { tenant, tenantId, tenants, setTenantId } = useTenant();
  const { data: overview } = useOverview(tenantId);
  const seed = useSeedDemo();
  const client = useQueryClient();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, retry: false });
  const [token, setToken] = useState(() => getApiToken());

  const saveToken = async () => {
    setApiToken(token);
    await client.invalidateQueries();
    toast.success(token.trim() ? "API access token saved" : "API access token removed");
  };

  const clearToken = async () => {
    clearApiToken();
    setToken("");
    await client.invalidateQueries();
    toast.success("API access token removed");
  };

  const exportAudit = async () => {
    try {
      await api.downloadAudit(tenantId);
      toast.success("Audit export downloaded");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Audit export failed");
    }
  };

  const loadDemo = async () => {
    try {
      const result = await seed.mutateAsync();
      const id = result.tenant_id as string | undefined;
      if (id) setTenantId(id);
      toast.success(
        result.created ? "Demo workspace created" : "Demo workspace already exists — opening it",
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not seed demo");
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Settings"
        title="Workspace & runtime"
        description="Appearance, environment, and the control-plane configuration available to this console."
      />

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader>
            <div className="mb-2 flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Palette className="h-5 w-5" />
              </span>
              <div>
                <CardTitle>Appearance</CardTitle>
                <CardDescription>Theme is stored locally in this browser.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2">
              {[
                { id: "dark" as const, label: "Midnight", description: "High-contrast operations console", icon: Moon },
                { id: "light" as const, label: "Daylight", description: "Bright, audit-friendly reading mode", icon: Sun },
              ].map((option) => {
                const Icon = option.icon;
                const active = theme === option.id;
                return (
                  <button
                    key={option.id}
                    onClick={() => setTheme(option.id)}
                    className={cn(
                      "relative flex items-start gap-3 rounded-2xl border p-4 text-left transition",
                      active
                        ? "border-primary/40 bg-primary/8"
                        : "border-border/70 hover:border-primary/25",
                    )}
                  >
                    <span className={cn(
                      "flex h-9 w-9 items-center justify-center rounded-xl",
                      active ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground",
                    )}>
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className="flex-1">
                      <span className="block text-sm font-semibold">{option.label}</span>
                      <span className="mt-0.5 block text-[11px] leading-5 text-muted-foreground">{option.description}</span>
                    </span>
                    {active ? (
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground">
                        <Check className="h-3 w-3" />
                      </span>
                    ) : null}
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="mb-2 flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <ServerCog className="h-5 w-5" />
              </span>
              <div>
                <CardTitle>Runtime</CardTitle>
                <CardDescription>Live values reported by the API.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-2 text-xs">
            {[
              ["API version", health.data?.version ?? "unreachable"],
              ["Database", health.data?.database ?? "—"],
              ["Environment", overview?.features.environment ?? "—"],
              ["Authentication", overview?.features.auth_mode ?? "—"],
              ["Remediation approval", overview?.features.approval_required ? "required" : "not required"],
              ["Exposure scanner", overview?.features.exposure_enabled ? "enabled" : "disabled"],
              ["Demo bootstrap", overview?.features.demo_enabled ? "enabled" : "disabled"],
              ["Ledger head", overview?.ledger.head.slice(0, 18) ?? "—"],
            ].map(([label, value]) => (
              <div key={label} className="flex items-center justify-between gap-4 rounded-xl border border-border/50 px-3 py-2.5">
                <span className="text-muted-foreground">{label}</span>
                <span className="max-w-48 truncate font-mono text-foreground/80">{value}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="mb-2 flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <KeyRound className="h-5 w-5" />
              </span>
              <div>
                <CardTitle>API access</CardTitle>
                <CardDescription>Bearer token for this browser session.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <input
              type="password"
              autoComplete="off"
              value={token}
              onChange={(event) => setToken(event.target.value)}
              placeholder="Paste bearer token or API key"
              className="h-10 w-full rounded-xl border border-border/80 bg-background/60 px-3 font-mono text-xs outline-none focus:border-primary/50"
            />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => void clearToken()}>
                <Trash2 className="h-3.5 w-3.5" /> Clear
              </Button>
              <Button variant="brand" size="sm" onClick={() => void saveToken()}>
                <KeyRound className="h-3.5 w-3.5" /> Save token
              </Button>
            </div>
            <p className="text-[11px] leading-5 text-muted-foreground">
              Stored only in this browser. Use a short-lived token and clear it on shared devices.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="mb-2 flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Download className="h-5 w-5" />
              </span>
              <div>
                <CardTitle>Operational audit</CardTitle>
                <CardDescription>Export tenant-scoped administrative events.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-xs leading-5 text-muted-foreground">
              CSV export requires an administrator role. It includes request creation,
              approvals, remediation runs, tenant changes, and connector lifecycle events.
            </p>
            <Button variant="outline" size="sm" onClick={() => void exportAudit()}>
              <Download className="h-3.5 w-3.5" /> Download CSV
            </Button>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex-row items-start justify-between">
          <div>
            <CardTitle>Active workspace</CardTitle>
            <CardDescription>Requests, subjects, connectors, and evidence are scoped to this tenant.</CardDescription>
          </div>
          <Badge variant="default">{tenants.length} workspaces</Badge>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4 rounded-2xl border border-border/60 bg-background/30 p-4 sm:flex-row sm:items-center">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand text-white">
              <Database className="h-5 w-5" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold">{tenant?.name ?? "No active workspace"}</p>
              <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">
                {tenant ? `${tenant.id} · ${tenant.jurisdiction} · created ${formatDate(tenant.created_at)}` : "Load the demo or create a workspace through the API."}
              </p>
            </div>
            {!tenant ? (
              <Button variant="brand" onClick={() => void loadDemo()} disabled={seed.isPending}>
                <Sparkles className="h-4 w-4" /> {seed.isPending ? "Preparing…" : "Load demo"}
              </Button>
            ) : (
              <div className="flex flex-wrap gap-2">
                <select
                  value={tenantId}
                  onChange={(event) => setTenantId(event.target.value)}
                  className="h-10 rounded-xl border border-border/80 bg-background/60 px-3 text-xs outline-none focus:border-primary/50"
                >
                  {tenants.map((item) => (
                    <option key={item.id} value={item.id}>{item.name}</option>
                  ))}
                </select>
                <Button variant="outline" onClick={() => void loadDemo()} disabled={seed.isPending}>
                  <Sparkles className="h-4 w-4" /> Ensure demo
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Terminal className="h-5 w-5" />
            </span>
            <div>
              <CardTitle>Environment configuration</CardTitle>
              <CardDescription>Server-side controls. Secrets never belong in this console.</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="px-3 pb-3">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-[10px] uppercase tracking-widest text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Variable</th>
                  <th className="px-3 py-2 font-medium">Default</th>
                  <th className="px-3 py-2 font-medium">Purpose</th>
                </tr>
              </thead>
              <tbody>
                {envVars.map(([name, value, purpose]) => (
                  <tr key={name} className="border-t border-border/50">
                    <td className="px-3 py-3 font-mono text-[10px] text-primary">{name}</td>
                    <td className="px-3 py-3 font-mono text-[10px] text-muted-foreground">{value}</td>
                    <td className="px-3 py-3 text-muted-foreground">{purpose}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardContent className="flex items-start gap-3 p-5">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-400/10 text-emerald-300">
              <ShieldCheck className="h-4 w-4" />
            </span>
            <div>
              <p className="text-sm font-semibold">Safety boundary</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">
                This deployment performs local artifact analysis and passive public-source collection only.
                It does not attempt authentication bypass, exploitation, credential attacks, or private scraping.
              </p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-start gap-3 p-5">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Info className="h-4 w-4" />
            </span>
            <div className="flex-1">
              <p className="text-sm font-semibold">API documentation</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">
                Interactive OpenAPI reference and the full product architecture guide.
              </p>
              <div className="mt-3 flex gap-2">
                <a href="/docs" target="_blank" rel="noreferrer">
                  <Button variant="secondary" size="sm">OpenAPI <ExternalLink className="h-3 w-3" /></Button>
                </a>
                <a href="/app/docs">
                  <Button variant="ghost" size="sm">Product docs</Button>
                </a>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
