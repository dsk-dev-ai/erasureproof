import { useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Github, PanelsTopLeft } from "lucide-react";
import { Logo } from "@/components/brand/logo";
import { navItems } from "@/components/layout/nav-config";
import { cn } from "@/lib/utils";

export function Sidebar({
  mobileOpen,
  onMobileClose,
}: {
  mobileOpen: boolean;
  onMobileClose: () => void;
}) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <>
      <button
        aria-label="Close navigation"
        onClick={onMobileClose}
        className={cn(
          "fixed inset-0 z-40 bg-background/70 backdrop-blur-sm transition-opacity lg:hidden",
          mobileOpen ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      />
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-border/60 bg-card/75 backdrop-blur-2xl transition-all duration-300",
          collapsed ? "lg:w-[76px]" : "lg:w-64",
          mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
        )}
      >
        <div
          className={cn(
            "flex h-16 items-center border-b border-border/60",
            collapsed ? "justify-center px-2" : "justify-between px-4",
          )}
        >
          <Link to="/" className="flex items-center">
            <Logo markOnly={collapsed} />
          </Link>
          {!collapsed ? (
            <button
              onClick={() => setCollapsed(true)}
              className="hidden rounded-lg p-1.5 text-muted-foreground transition hover:bg-accent hover:text-foreground lg:block"
              aria-label="Collapse sidebar"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          ) : null}
        </div>

        <nav className="no-scrollbar flex-1 space-y-1 overflow-y-auto p-3">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.href}
                to={item.href}
                end={item.end}
                onClick={onMobileClose}
                title={collapsed ? item.label : undefined}
                className={({ isActive }) =>
                  cn(
                    "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                    isActive
                      ? "text-primary"
                      : "text-muted-foreground hover:bg-accent/70 hover:text-foreground",
                    collapsed && "justify-center",
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive ? (
                      <motion.span
                        layoutId="sidebar-active"
                        className="absolute inset-0 -z-10 rounded-xl border border-primary/20 bg-primary/10"
                        transition={{ type: "spring", stiffness: 380, damping: 32 }}
                      />
                    ) : null}
                    {isActive ? (
                      <motion.span
                        layoutId="sidebar-indicator"
                        className="absolute left-0 h-5 w-1 rounded-r-full bg-brand"
                        transition={{ type: "spring", stiffness: 380, damping: 32 }}
                      />
                    ) : null}
                    <Icon className="h-[18px] w-[18px] shrink-0" />
                    {!collapsed ? <span>{item.label}</span> : null}
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>

        <div className="border-t border-border/60 p-3">
          {collapsed ? (
            <button
              onClick={() => setCollapsed(false)}
              className="mx-auto block rounded-lg p-2 text-muted-foreground transition hover:bg-accent hover:text-foreground"
              aria-label="Expand sidebar"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          ) : (
            <div className="space-y-2">
              <div className="flex items-center justify-between rounded-xl border border-border/60 bg-gradient-to-br from-primary/10 to-transparent px-3 py-2.5">
                <span className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="h-2 w-2 animate-pulse rounded-full bg-success" />
                  Self-hostable
                </span>
                <Link
                  to="/app/docs"
                  className="text-[10px] font-semibold uppercase tracking-widest text-primary"
                >
                  v0.3
                </Link>
              </div>
              <div className="flex items-center justify-between px-1">
                <a
                  href="https://github.com/dsk-dev-ai/erasureproof"
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1.5 text-[11px] text-muted-foreground transition hover:text-foreground"
                >
                  <Github className="h-3.5 w-3.5" /> Source
                </a>
                <a
                  href="/docs"
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1.5 text-[11px] text-muted-foreground transition hover:text-foreground"
                >
                  <PanelsTopLeft className="h-3.5 w-3.5" /> API
                </a>
              </div>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
