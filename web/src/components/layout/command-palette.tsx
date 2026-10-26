import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Command, Search, Sparkles } from "lucide-react";
import { navItems } from "@/components/layout/nav-config";
import { useSeedDemo } from "@/hooks/use-api";
import { useTenant } from "@/components/tenant-provider";
import { toast } from "sonner";

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const navigate = useNavigate();
  const seed = useSeedDemo();
  const { tenantId } = useTenant();

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => !value);
      }
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const items = useMemo(
    () =>
      navItems.filter((item) =>
        item.label.toLowerCase().includes(query.toLowerCase()),
      ),
    [query],
  );

  const run = (href: string) => {
    setOpen(false);
    setQuery("");
    navigate(href);
  };

  const loadDemo = async () => {
    setOpen(false);
    try {
      const result = await seed.mutateAsync();
      const id = result.tenant_id as string | undefined;
      if (id) {
        window.localStorage.setItem("erasureproof.tenant", id);
        window.location.assign(`/app?tenant=${id}`);
      }
      toast.success("Demo workspace is ready");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not seed demo");
    }
  };

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-[120] flex items-start justify-center px-4 pt-[12vh]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <button
            className="absolute inset-0 bg-background/75 backdrop-blur-md"
            onClick={() => setOpen(false)}
            aria-label="Close command palette"
          />
          <motion.div
            initial={{ opacity: 0, y: 18, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.99 }}
            className="surface relative z-10 w-full max-w-xl overflow-hidden rounded-2xl"
          >
            <div className="flex items-center gap-3 border-b border-border/70 px-4">
              <Search className="h-4 w-4 text-muted-foreground" />
              <input
                autoFocus
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Jump to a page or action…"
                className="h-14 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              />
              <kbd className="rounded-md border border-border/70 bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                ESC
              </kbd>
            </div>
            <div className="max-h-[340px] overflow-y-auto p-2">
              {items.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.href}
                    onClick={() => run(item.href)}
                    className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm text-muted-foreground transition hover:bg-accent hover:text-foreground"
                  >
                    <Icon className="h-4 w-4" />
                    <span className="flex-1">{item.label}</span>
                    <ArrowRight className="h-3.5 w-3.5 opacity-40" />
                  </button>
                );
              })}
              {!query ? (
                <button
                  onClick={() => void loadDemo()}
                  className="mt-1 flex w-full items-center gap-3 rounded-xl border border-primary/20 bg-primary/5 px-3 py-2.5 text-left text-sm text-primary transition hover:bg-primary/10"
                >
                  <Sparkles className="h-4 w-4" />
                  <span className="flex-1">Load demo workspace</span>
                  <span className="text-[10px] uppercase tracking-widest opacity-70">
                    {tenantId ? "refresh" : "start"}
                  </span>
                </button>
              ) : null}
              {!items.length && query ? (
                <p className="px-3 py-8 text-center text-sm text-muted-foreground">
                  No commands match “{query}”
                </p>
              ) : null}
            </div>
            <div className="flex items-center justify-between border-t border-border/70 px-4 py-2.5 text-[10px] uppercase tracking-widest text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <Command className="h-3 w-3" /> K to open
              </span>
              <span>Enter to navigate</span>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
