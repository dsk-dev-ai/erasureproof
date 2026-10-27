import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ChevronDown,
  Command,
  ExternalLink,
  KeyRound,
  Menu,
  Moon,
  Sun,
  Wifi,
} from "lucide-react";
import { Logo } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";
import { useTenant } from "@/components/tenant-provider";
import { useTheme } from "@/components/theme-provider";
import { CommandPalette } from "@/components/layout/command-palette";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export function Topbar({ onMenu }: { onMenu: () => void }) {
  const location = useLocation();
  const { theme, toggle } = useTheme();
  const { tenants, tenantId, setTenantId } = useTenant();
  const [tenantOpen, setTenantOpen] = useState(false);
  const health = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 30_000,
    retry: false,
  });

  const crumb =
    location.pathname === "/app"
      ? "Overview"
      : location.pathname.split("/").filter(Boolean).slice(1).join(" / ") || "Overview";

  return (
    <>
      <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border/60 bg-background/70 px-4 backdrop-blur-2xl sm:px-6">
        <button
          onClick={onMenu}
          className="rounded-lg p-2 text-muted-foreground transition hover:bg-accent hover:text-foreground lg:hidden"
          aria-label="Open navigation"
        >
          <Menu className="h-5 w-5" />
        </button>
        <Link to="/app" className="lg:hidden">
          <Logo markOnly />
        </Link>
        <div className="hidden min-w-0 flex-1 items-center gap-2 text-sm text-muted-foreground sm:flex">
          <span className="font-mono text-[11px] uppercase tracking-widest text-primary">Console</span>
          <span className="text-border">/</span>
          <span className="truncate capitalize">{crumb.replaceAll("-", " ")}</span>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <div className="relative hidden sm:block">
            <button
              onClick={() => setTenantOpen((value) => !value)}
              className="flex h-9 items-center gap-2 rounded-xl border border-border/70 bg-card/50 px-3 text-xs font-medium transition hover:border-primary/30 hover:bg-accent"
            >
              <span className="h-2 w-2 rounded-full bg-primary" />
              <span className="max-w-32 truncate">
                {tenants.find((tenant) => tenant.id === tenantId)?.name ?? "All workspaces"}
              </span>
              <ChevronDown className={cn("h-3.5 w-3.5 transition", tenantOpen && "rotate-180")} />
            </button>
            {tenantOpen ? (
              <div className="surface absolute right-0 top-11 z-50 w-60 rounded-xl p-1.5">
                <p className="px-2.5 py-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                  Workspaces
                </p>
                {tenants.map((tenant) => (
                  <button
                    key={tenant.id}
                    onClick={() => {
                      setTenantId(tenant.id);
                      setTenantOpen(false);
                    }}
                    className={cn(
                      "flex w-full flex-col rounded-lg px-2.5 py-2 text-left text-sm transition hover:bg-accent",
                      tenant.id === tenantId && "bg-primary/10 text-primary",
                    )}
                  >
                    <span className="font-medium">{tenant.name}</span>
                    <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                      {tenant.jurisdiction} · {tenant.id}
                    </span>
                  </button>
                ))}
                {!tenants.length ? (
                  <p className="px-2.5 py-4 text-xs text-muted-foreground">
                    No workspace yet. Load the demo from the dashboard.
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>

          <button
            onClick={() => {
              window.dispatchEvent(
                new KeyboardEvent("keydown", { key: "k", metaKey: true }),
              );
            }}
            className="hidden h-9 items-center gap-2 rounded-xl border border-border/70 bg-card/50 px-3 text-xs text-muted-foreground transition hover:border-primary/30 hover:text-foreground md:flex"
          >
            <Command className="h-3.5 w-3.5" />
            <span>Search</span>
            <kbd className="rounded border border-border/70 bg-muted px-1 font-mono text-[9px]">⌘K</kbd>
          </button>

          <Button
            variant="ghost"
            size="icon"
            onClick={() => window.dispatchEvent(new Event("erasureproof:show-token"))}
            aria-label="API access token"
            title="API access token"
          >
            <KeyRound className="h-4 w-4" />
          </Button>

          <span
            title={health.data ? `API ${health.data.version}` : "API unreachable"}
            className={cn(
              "hidden h-9 items-center gap-2 rounded-xl border border-border/70 px-3 text-xs sm:flex",
              health.isError ? "text-destructive" : "text-muted-foreground",
            )}
          >
            <Wifi className={cn("h-3.5 w-3.5", health.isSuccess && "text-success")} />
            {health.isError ? "Offline" : health.data ? `v${health.data.version}` : "Connecting"}
          </span>

          <Button variant="ghost" size="icon" onClick={toggle} aria-label="Toggle theme">
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>

          <a href="/docs" target="_blank" rel="noreferrer">
            <Button variant="outline" size="sm" className="hidden gap-1.5 sm:inline-flex">
              API <ExternalLink className="h-3 w-3" />
            </Button>
          </a>
        </div>
      </header>
      <CommandPalette />
    </>
  );
}
