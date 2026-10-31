import { useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowRight,
  ArrowUpRight,
  Boxes,
  Check,
  ChevronRight,
  CircleDot,
  Database,
  FileCheck2,
  Fingerprint,
  GitBranch,
  KeyRound,
  Layers3,
  LockKeyhole,
  Menu,
  Moon,
  Network,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Sun,
  TerminalSquare,
  Workflow,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Logo } from "@/components/brand/logo";
import { SandboxDialog } from "@/components/auth/sandbox-dialog";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/components/theme-provider";
import { useCreateSandbox, useSeedDemo } from "@/hooks/use-api";
import { setApiToken } from "@/lib/api";
import type { Sandbox } from "@/lib/types";
import { EASE, Reveal, Stagger, StaggerItem } from "@/components/motion/motion";
import { cn } from "@/lib/utils";

const navLinks = [
  { href: "#product", label: "Product" },
  { href: "#workflow", label: "How it works" },
  { href: "#developers", label: "API" },
  { href: "#evidence", label: "Evidence" },
  { href: "#security", label: "Security" },
];

const features = [
  {
    icon: Fingerprint,
    title: "Identity resurrection",
    description:
      "Rebuild every historic email, phone, hash, and username from audit history, then trace each alias across every surface.",
    className: "md:col-span-2",
  },
  {
    icon: Workflow,
    title: "Dependency-aware remediation",
    description:
      "A verified DAG disables data flows and blocks restores before deleting downstream copies in the correct order.",
  },
  {
    icon: Database,
    title: "Evidence you can defend",
    description:
      "Files are fingerprinted, linked to findings, and bound to an append-only hash-chained ledger.",
  },
  {
    icon: ScanSearch,
    title: "Exposure intelligence",
    description:
      "Authorized, passive scanning for public identifiers with strict safety guardrails and report evidence.",
  },
  {
    icon: Layers3,
    title: "Policy as a control plane",
    description:
      "Per-jurisdiction rules decide what must be deleted, redacted, anonymized, retained, or tombstoned.",
    className: "md:col-span-2",
  },
];

const workflow = [
  {
    number: "01",
    title: "Authorize",
    body: "Classify the request. Access, correction, export, and opt-out never become deletion cases.",
    icon: FileCheck2,
  },
  {
    number: "02",
    title: "Discover",
    body: "Resolve current and historic identifiers, inspect evidence, and reconstruct the true state at audit time.",
    icon: Network,
  },
  {
    number: "03",
    title: "Prove",
    body: "Execute the ordered remediation plan, verify every resource, and issue a signed attestation.",
    icon: ShieldCheck,
  },
];

function HeroConsole() {
  const rows = [
    { label: "Primary database", state: "Deleted", tone: "success" },
    { label: "Analytics warehouse", state: "PII exposed", tone: "danger" },
    { label: "Support attachment", state: "Deleted", tone: "success" },
    { label: "Nightly export", state: "Active flow", tone: "warning" },
    { label: "Backup snapshot", state: "Restore risk", tone: "warning" },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 28, rotateX: 4 }}
      animate={{ opacity: 1, y: 0, rotateX: 0 }}
      transition={{ duration: 0.9, delay: 0.25, ease: EASE }}
      className="relative mx-auto w-full max-w-[600px] [perspective:1200px]"
    >
      <div className="absolute -inset-8 -z-10 rounded-[40px] bg-primary/15 blur-3xl" />
      <div className="surface glow relative overflow-hidden rounded-[26px] p-3 sm:p-4">
        <div className="mb-3 flex items-center justify-between px-1">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-rose-400/80" />
            <span className="h-2.5 w-2.5 rounded-full bg-amber-400/80" />
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/80" />
          </div>
          <span className="font-mono text-[10px] text-muted-foreground">
            audit / req_01J8A2
          </span>
        </div>

        <div className="rounded-2xl border border-border/70 bg-background/55 p-4 sm:p-5">
          <div className="mb-5 flex items-start justify-between gap-3">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Deletion audit
              </p>
              <p className="mt-1 font-display text-lg font-semibold">Alice Mercer</p>
              <p className="font-mono text-[10px] text-muted-foreground">usr_8f21c · EU / GDPR</p>
            </div>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-rose-400/25 bg-rose-400/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-rose-300">
              <X className="h-3 w-3" /> Incomplete
            </span>
          </div>

          <div className="mb-4 grid grid-cols-3 gap-2">
            {[
              ["Findings", "2"],
              ["Remediations", "4"],
              ["Checks", "7/7"],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border border-border/60 bg-card/60 p-2.5">
                <p className="text-[9px] uppercase tracking-widest text-muted-foreground">{label}</p>
                <p className="mt-1 font-display text-base font-semibold">{value}</p>
              </div>
            ))}
          </div>

          <div className="space-y-1.5">
            {rows.map((row, index) => (
              <motion.div
                key={row.label}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.5 + index * 0.08 }}
                className="flex items-center gap-2.5 rounded-lg border border-border/50 bg-card/45 px-2.5 py-2"
              >
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    row.tone === "success"
                      ? "bg-emerald-400"
                      : row.tone === "danger"
                        ? "bg-rose-400"
                        : "bg-amber-400",
                  )}
                />
                <span className="flex-1 text-[11px] text-foreground/85">{row.label}</span>
                <span
                  className={cn(
                    "text-[9px] font-semibold uppercase tracking-wider",
                    row.tone === "success"
                      ? "text-emerald-300"
                      : row.tone === "danger"
                        ? "text-rose-300"
                        : "text-amber-300",
                  )}
                >
                  {row.state}
                </span>
              </motion.div>
            ))}
          </div>

          <div className="mt-4 flex items-center gap-2 rounded-xl border border-primary/20 bg-primary/5 p-2.5">
            <LockKeyhole className="h-3.5 w-3.5 text-primary" />
            <div className="min-w-0 flex-1">
              <p className="text-[9px] uppercase tracking-widest text-muted-foreground">Ledger head</p>
              <p className="truncate font-mono text-[10px] text-primary">a91f…7c2e</p>
            </div>
            <span className="flex items-center gap-1 text-[9px] font-semibold uppercase tracking-wider text-success">
              <Check className="h-3 w-3" /> Verified
            </span>
          </div>
        </div>
      </div>

      <motion.div
        initial={{ opacity: 0, x: 20, y: 10 }}
        animate={{ opacity: 1, x: 0, y: 0 }}
        transition={{ delay: 0.95, duration: 0.6, ease: EASE }}
        className="glass absolute -bottom-7 -left-4 hidden items-center gap-2.5 rounded-2xl px-3.5 py-2.5 sm:flex"
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-400/10 text-emerald-300">
          <GitBranch className="h-4 w-4" />
        </span>
        <div>
          <p className="text-[10px] font-semibold">Plan validated</p>
          <p className="font-mono text-[9px] text-muted-foreground">0 cycles · 12 edges</p>
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, x: -20, y: -10 }}
        animate={{ opacity: 1, x: 0, y: 0 }}
        transition={{ delay: 1.1, duration: 0.6, ease: EASE }}
        className="glass absolute -right-5 top-24 hidden items-center gap-2.5 rounded-2xl px-3.5 py-2.5 sm:flex"
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <CircleDot className="h-4 w-4" />
        </span>
        <div>
          <p className="text-[10px] font-semibold">Live sync detected</p>
          <p className="font-mono text-[9px] text-muted-foreground">disable before delete</p>
        </div>
      </motion.div>
    </motion.div>
  );
}

export function LandingPage() {
  const { theme, toggle } = useTheme();
  const seed = useSeedDemo();
  const sandboxMutation = useCreateSandbox();
  const [menuOpen, setMenuOpen] = useState(false);
  const [sandbox, setSandbox] = useState<Sandbox | null>(null);
  const [sandboxOpen, setSandboxOpen] = useState(false);
  const busy = seed.isPending || sandboxMutation.isPending;

  const openDemo = async () => {
    try {
      const result = await sandboxMutation.mutateAsync({
        workspace_name: "Developer sandbox",
      });
      setApiToken(result.api_key);
      window.localStorage.setItem("erasureproof.tenant", result.tenant_id);
      setSandbox(result);
      setSandboxOpen(true);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not open the demo workspace";
      if (!message.toLowerCase().includes("disabled")) {
        toast.error(message);
        return;
      }
      try {
        const result = await seed.mutateAsync();
        const tenantId = result.tenant_id as string | undefined;
        if (tenantId) window.localStorage.setItem("erasureproof.tenant", tenantId);
        window.location.assign(`${import.meta.env.BASE_URL}app`);
      } catch (fallbackError) {
        toast.error(
          fallbackError instanceof Error ? fallbackError.message : "Could not open the demo workspace",
        );
      }
    }
  };

  const closeSandbox = () => {
    setSandboxOpen(false);
    window.location.assign(`${import.meta.env.BASE_URL}app`);
  };

  return (
    <div className="relative overflow-x-clip">
      <header className="sticky top-0 z-50 border-b border-border/50 bg-background/65 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link to="/" aria-label="ErasureProof home">
            <Logo />
          </Link>
          <nav className="hidden items-center gap-7 md:flex">
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="text-sm text-muted-foreground transition hover:text-foreground"
              >
                {link.label}
              </a>
            ))}
            <Link
              to="/app/docs"
              className="text-sm text-muted-foreground transition hover:text-foreground"
            >
              Docs
            </Link>
          </nav>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" onClick={toggle} aria-label="Toggle theme">
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <Link to="/app" className="hidden sm:block">
              <Button variant="secondary" size="sm">
                Open console <ArrowUpRight className="h-3.5 w-3.5" />
              </Button>
            </Link>
            <Button variant="brand" size="sm" onClick={() => void openDemo()} disabled={busy}>
              <Sparkles className="h-3.5 w-3.5" />
              {busy ? "Preparing…" : "Start sandbox"}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              onClick={() => setMenuOpen((value) => !value)}
              aria-label="Toggle navigation"
              aria-expanded={menuOpen}
            >
              {menuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            </Button>
          </div>
        </div>
        {menuOpen ? (
          <motion.nav
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className="border-t border-border/50 bg-background/95 px-4 py-3 backdrop-blur-xl md:hidden"
          >
            <div className="mx-auto flex max-w-7xl flex-col">
              {navLinks.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  onClick={() => setMenuOpen(false)}
                  className="rounded-lg px-3 py-2.5 text-sm text-muted-foreground transition hover:bg-accent hover:text-foreground"
                >
                  {link.label}
                </a>
              ))}
              <Link
                to="/app/docs"
                onClick={() => setMenuOpen(false)}
                className="rounded-lg px-3 py-2.5 text-sm text-muted-foreground transition hover:bg-accent hover:text-foreground"
              >
                Docs
              </Link>
              <Link
                to="/app"
                onClick={() => setMenuOpen(false)}
                className="mt-1 rounded-lg px-3 py-2.5 text-sm font-semibold text-primary transition hover:bg-accent"
              >
                Open console
              </Link>
            </div>
          </motion.nav>
        ) : null}
      </header>

      <main>
        <section className="relative isolate">
          <div className="absolute inset-0 -z-10 bg-grid [mask-image:radial-gradient(ellipse_70%_60%_at_50%_20%,black,transparent)]" />
          <div className="absolute left-1/2 top-0 -z-10 h-[560px] w-[820px] -translate-x-1/2 rounded-full bg-primary/10 blur-[120px]" />
          <div className="mx-auto grid max-w-7xl items-center gap-14 px-4 pb-20 pt-16 sm:px-6 md:pt-24 lg:grid-cols-[1.05fr_0.95fr] lg:gap-10 lg:px-8 lg:pb-28 lg:pt-28">
            <div>
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, ease: EASE }}
                className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/25 bg-primary/8 px-3 py-1.5 text-[11px] font-semibold text-primary"
              >
                <span className="relative flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-60" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-primary" />
                </span>
                ErasureProof v1.1 · deletion audit control plane
              </motion.div>
              <motion.h1
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, delay: 0.08, ease: EASE }}
                className="text-balance font-display text-[2.7rem] font-bold leading-[1.02] tracking-[-0.04em] sm:text-6xl lg:text-[4.1rem]"
              >
                Deletion is a promise.
                <br />
                <span className="text-gradient">Prove it.</span>
              </motion.h1>
              <motion.p
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, delay: 0.16, ease: EASE }}
                className="mt-6 max-w-xl text-base leading-7 text-muted-foreground sm:text-lg"
              >
                ErasureProof reconstructs every copy of a person&apos;s data, finds the backups
                and data flows that recreate it, and produces a policy-safe, verifiable deletion
                plan. No trust in &ldquo;complete.&rdquo;
              </motion.p>
              <motion.div
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, delay: 0.24, ease: EASE }}
                className="mt-8 flex flex-wrap items-center gap-3"
              >
                <Button variant="brand" size="lg" onClick={() => void openDemo()} disabled={busy}>
                  {busy ? "Building workspace…" : "Run a live deletion audit"}
                  <ArrowRight className="h-4 w-4" />
                </Button>
                <Link to="/app/docs">
                  <Button variant="outline" size="lg">
                    <TerminalSquare className="h-4 w-4" /> Read the architecture
                  </Button>
                </Link>
              </motion.div>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.45 }}
                className="mt-9 flex flex-wrap items-center gap-x-6 gap-y-2 text-[11px] text-muted-foreground"
              >
                <span className="flex items-center gap-1.5">
                  <Check className="h-3.5 w-3.5 text-success" /> Deterministic plans
                </span>
                <span className="flex items-center gap-1.5">
                  <Check className="h-3.5 w-3.5 text-success" /> Hash-chained ledger
                </span>
                <span className="flex items-center gap-1.5">
                  <Check className="h-3.5 w-3.5 text-success" /> Self-hostable
                </span>
              </motion.div>
            </div>
            <HeroConsole />
          </div>

          <div className="mx-auto max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
            <Reveal className="flex flex-col items-center gap-5 border-y border-border/50 py-6 sm:flex-row sm:justify-between">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">
                Built for the regulations that matter
              </p>
              <div className="flex flex-wrap items-center justify-center gap-x-7 gap-y-3 font-display text-sm font-semibold text-muted-foreground/80">
                <span>GDPR</span>
                <span className="h-4 w-px bg-border" />
                <span>CCPA / CPRA</span>
                <span className="h-4 w-px bg-border" />
                <span>DPDP</span>
                <span className="h-4 w-px bg-border" />
                <span>LGPD</span>
                <span className="h-4 w-px bg-border" />
                <span>PIPEDA</span>
              </div>
            </Reveal>
          </div>
        </section>

        <section id="product" className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8 lg:py-28">
          <Reveal className="max-w-2xl">
            <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-primary">
              The gap in every deletion workflow
            </p>
            <h2 className="text-balance font-display text-3xl font-bold tracking-tight sm:text-4xl">
              &ldquo;Complete&rdquo; is a status. <span className="text-muted-foreground">Not a fact.</span>
            </h2>
            <p className="mt-4 text-muted-foreground">
              Replicas drift. Support tickets keep attachments. Exports keep running. Backups
              restore. A workflow can mark a ticket done while the person&apos;s data still exists
              in six places.
            </p>
          </Reveal>

          <div className="mt-10 grid gap-4 lg:grid-cols-2">
            <Reveal className="rounded-3xl border border-rose-400/15 bg-rose-400/[0.035] p-6 sm:p-8">
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-rose-400/10 text-rose-300">
                  <X className="h-5 w-5" />
                </span>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-rose-300/80">Reported</p>
                  <p className="font-display text-lg font-semibold">Workflow says complete</p>
                </div>
              </div>
              <div className="mt-6 space-y-2 font-mono text-[11px]">
                {[
                  ["primary.users", "row deleted"],
                  ["analytics.events", "still present"],
                  ["support.attachments", "still present"],
                  ["exports/nightly", "active copy job"],
                  ["backup/s3-eu", "restore can recreate"],
                ].map(([resource, state]) => (
                  <div key={resource} className="flex items-center gap-3 rounded-xl border border-border/50 px-3 py-2">
                    <span className="flex-1 text-muted-foreground">{resource}</span>
                    <span className="text-rose-300">{state}</span>
                  </div>
                ))}
              </div>
            </Reveal>

            <Reveal delay={0.08} className="rounded-3xl border border-emerald-400/15 bg-emerald-400/[0.035] p-6 sm:p-8">
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-emerald-400/10 text-emerald-300">
                  <ShieldCheck className="h-5 w-5" />
                </span>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-emerald-300/80">Proven</p>
                  <p className="font-display text-lg font-semibold">ErasureProof reconstructs the truth</p>
                </div>
              </div>
              <div className="mt-6 space-y-2 font-mono text-[11px]">
                {[
                  ["primary.users", "verified absent"],
                  ["analytics.events", "anonymized"],
                  ["support.attachments", "redacted + retained"],
                  ["exports/nightly", "flow disabled"],
                  ["backup/s3-eu", "restore blocked"],
                ].map(([resource, state]) => (
                  <div key={resource} className="flex items-center gap-3 rounded-xl border border-border/50 px-3 py-2">
                    <span className="flex-1 text-muted-foreground">{resource}</span>
                    <span className="text-emerald-300">{state}</span>
                  </div>
                ))}
              </div>
            </Reveal>
          </div>
        </section>

        <section className="border-y border-border/50 bg-card/20">
          <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8 lg:py-28">
            <Reveal className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
              <div className="max-w-xl">
                <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-primary">
                  One control plane
                </p>
                <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">
                  Everything between a request and proof.
                </h2>
              </div>
              <p className="max-w-sm text-sm leading-6 text-muted-foreground">
                A complete audit surface for privacy engineering teams, not another ticket tracker.
              </p>
            </Reveal>

            <Stagger className="mt-10 grid gap-4 md:grid-cols-3">
              {features.map((feature) => {
                const Icon = feature.icon;
                return (
                  <StaggerItem key={feature.title}>
                    <div
                      className={cn(
                        "group relative h-full overflow-hidden rounded-3xl border border-border/70 bg-card/55 p-6 transition-colors hover:border-primary/30",
                        feature.className,
                      )}
                    >
                      <div className="mb-8 flex h-11 w-11 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10 text-primary transition-transform duration-300 group-hover:scale-105">
                        <Icon className="h-5 w-5" />
                      </div>
                      <h3 className="font-display text-base font-semibold">{feature.title}</h3>
                      <p className="mt-2 text-sm leading-6 text-muted-foreground">{feature.description}</p>
                      <div className="pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full bg-primary/8 blur-2xl transition group-hover:bg-primary/14" />
                    </div>
                  </StaggerItem>
                );
              })}
            </Stagger>
          </div>
        </section>

        <section id="workflow" className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8 lg:py-28">
          <Reveal className="mx-auto max-w-2xl text-center">
            <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-primary">How it works</p>
            <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">
              Authorize. Discover. Prove.
            </h2>
            <p className="mt-4 text-muted-foreground">
              Every answer is grounded in participant-visible evidence and the state at audit time —
              not a workflow status.
            </p>
          </Reveal>

          <Stagger className="relative mt-14 grid gap-4 md:grid-cols-3">
            <div className="absolute left-0 right-0 top-[52px] hidden h-px bg-gradient-to-r from-transparent via-primary/30 to-transparent md:block" />
            {workflow.map((step) => {
              const Icon = step.icon;
              return (
                <StaggerItem key={step.number}>
                  <div className="relative h-full rounded-3xl border border-border/70 bg-card/45 p-6">
                    <div className="mb-8 flex items-center justify-between">
                      <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand text-white shadow-lg shadow-primary/20">
                        <Icon className="h-5 w-5" />
                      </span>
                      <span className="font-mono text-xs text-muted-foreground/60">{step.number}</span>
                    </div>
                    <h3 className="font-display text-lg font-semibold">{step.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">{step.body}</p>
                  </div>
                </StaggerItem>
              );
            })}
          </Stagger>
        </section>

        <section id="developers" className="border-y border-border/50 bg-card/20">
          <div className="mx-auto grid max-w-7xl items-center gap-10 px-4 py-20 sm:px-6 lg:grid-cols-[0.95fr_1.05fr] lg:px-8 lg:py-24">
            <Reveal>
              <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-primary">
                Built for developers
              </p>
              <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">
                One API from request to signed proof.
              </h2>
              <p className="mt-4 max-w-lg leading-7 text-muted-foreground">
                Create a free isolated sandbox in seconds. Submit deletion requests, run the
                dependency-ordered audit, inspect findings, and retrieve a signed attestation —
                all through a tenant-scoped REST API.
              </p>
              <div className="mt-6 flex flex-wrap gap-3">
                <Button variant="brand" onClick={() => void openDemo()} disabled={busy}>
                  <KeyRound className="h-4 w-4" /> Create sandbox API key
                </Button>
                <a href="/docs" target="_blank" rel="noreferrer">
                  <Button variant="outline">
                    OpenAPI reference <ArrowUpRight className="h-3.5 w-3.5" />
                  </Button>
                </a>
              </div>
              <div className="mt-7 grid gap-2 sm:grid-cols-3">
                {[
                  ["Hashed keys", "Shown once, revocable, expiring"],
                  ["Tenant isolation", "Server-side scoping on every route"],
                  ["Audit trail", "Every key and remediation event"],
                ].map(([title, body]) => (
                  <div key={title} className="rounded-xl border border-border/60 bg-background/40 p-3">
                    <p className="text-[11px] font-semibold">{title}</p>
                    <p className="mt-1 text-[10px] leading-4 text-muted-foreground">{body}</p>
                  </div>
                ))}
              </div>
            </Reveal>

            <Reveal delay={0.08}>
              <div className="overflow-hidden rounded-3xl border border-border/70 bg-[#071017] shadow-2xl">
                <div className="flex items-center justify-between border-b border-white/5 px-4 py-3 text-[10px] uppercase tracking-widest text-slate-500">
                  <span>quickstart.sh</span>
                  <span className="flex items-center gap-1.5 text-emerald-400">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> REST + JSON
                  </span>
                </div>
                <pre className="overflow-x-auto p-4 font-mono text-[10px] leading-5 text-slate-300">{`# 1. Create a sandbox key
curl -X POST "$BASE_URL/v1/onboarding/sandbox" \
  -H 'content-type: application/json' \
  -d '{"workspace_name":"Acme privacy"}'

# 2. Run the seeded deletion audit
curl -X POST "$BASE_URL/v1/requests/$REQUEST_ID/run?remediate=false" \
  -H "Authorization: Bearer $ERASUREPROOF_API_KEY"

# 3. Retrieve the signed attestation
curl "$BASE_URL/v1/requests/$REQUEST_ID/attestation" \
  -H "Authorization: Bearer $ERASUREPROOF_API_KEY"`}</pre>
                <div className="border-t border-white/5 px-4 py-3 font-mono text-[10px] text-slate-500">
                  OpenAPI: /docs · Console: /console · SDK: sdk/python
                </div>
              </div>
            </Reveal>
          </div>
        </section>

        <section id="evidence" className="mx-auto max-w-7xl px-4 pb-20 sm:px-6 lg:px-8 lg:pb-28">
          <div className="grid items-center gap-10 rounded-[32px] border border-border/70 bg-card/40 p-6 sm:p-10 lg:grid-cols-2 lg:p-14">
            <Reveal>
              <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-primary">
                Evidence, not assertions
              </p>
              <h2 className="text-balance font-display text-3xl font-bold tracking-tight sm:text-4xl">
                An audit trail that cannot quietly change.
              </h2>
              <p className="mt-4 max-w-lg leading-7 text-muted-foreground">
                Every finding cites a fingerprintable artifact. Every run appends to a ledger where
                each entry commits to the previous hash. Verification is a command, not a vibe.
              </p>
              <ul className="mt-6 space-y-3 text-sm">
                {[
                  "SHA-256 evidence fingerprints and integrity checks",
                  "Append-only ledger with signed attestations",
                  "Deterministic plan ordering and cycle detection",
                  "Policy matrix per jurisdiction and category",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-2.5">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <Check className="h-3 w-3" />
                    </span>
                    <span className="text-muted-foreground">{item}</span>
                  </li>
                ))}
              </ul>
            </Reveal>

            <Reveal delay={0.1}>
              <div className="relative overflow-hidden rounded-3xl border border-border/70 bg-[#071017] p-5 font-mono text-[11px] shadow-2xl">
                <div className="mb-4 flex items-center justify-between text-[10px] uppercase tracking-widest text-slate-500">
                  <span>ledger.jsonl</span>
                  <span className="flex items-center gap-1.5 text-emerald-400">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" /> valid
                  </span>
                </div>
                <div className="space-y-3 text-slate-400">
                  {[
                    { seq: "0441", event: "request.created", hash: "4f8a…c21d" },
                    { seq: "0442", event: "finding.reported", hash: "9b02…71ee" },
                    { seq: "0443", event: "flow.disabled", hash: "d3c7…8a40" },
                    { seq: "0444", event: "record.deleted", hash: "0e19…b6f2" },
                    { seq: "0445", event: "attestation.issued", hash: "a91f…7c2e" },
                  ].map((entry) => (
                    <div key={entry.seq} className="flex items-center gap-3 border-b border-white/5 pb-3 last:border-0 last:pb-0">
                      <span className="text-slate-600">{entry.seq}</span>
                      <span className="flex-1 text-slate-300">{entry.event}</span>
                      <span className="text-teal-400">{entry.hash}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-4 flex items-center gap-2 rounded-xl border border-emerald-400/15 bg-emerald-400/5 px-3 py-2.5 text-emerald-400">
                  <LockKeyhole className="h-3.5 w-3.5" />
                  chain verified · 445 entries · head a91f…7c2e
                </div>
              </div>
            </Reveal>
          </div>
        </section>

        <section id="security" className="border-y border-border/50">
          <div className="mx-auto grid max-w-7xl gap-10 px-4 py-20 sm:px-6 lg:grid-cols-[0.9fr_1.1fr] lg:px-8 lg:py-24">
            <Reveal>
              <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-primary">Trust boundaries</p>
              <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">
                Built to be operated, not trusted blindly.
              </h2>
              <p className="mt-4 leading-7 text-muted-foreground">
                Destructive actions are gated. Exposure scanning is disabled by default and requires
                explicit operator authorization. Every state change is attributable.
              </p>
            </Reveal>
            <Stagger className="grid gap-3 sm:grid-cols-2">
              {[
                { icon: KeyRound, title: "Authorized actions", body: "Remediation and exposure require explicit enablement." },
                { icon: LockKeyhole, title: "Safe by default", body: "Passive collection only; no credential or exploit paths." },
                { icon: Boxes, title: "Self-hosted", body: "SQLite metadata, local artifacts, Docker-first deployment." },
                { icon: GitBranch, title: "Reproducible", body: "Deterministic plans and stable serialization for audits." },
              ].map((item) => {
                const Icon = item.icon;
                return (
                  <StaggerItem key={item.title}>
                    <div className="h-full rounded-2xl border border-border/70 bg-card/45 p-5">
                      <Icon className="mb-4 h-5 w-5 text-primary" />
                      <p className="font-display text-sm font-semibold">{item.title}</p>
                      <p className="mt-1.5 text-xs leading-5 text-muted-foreground">{item.body}</p>
                    </div>
                  </StaggerItem>
                );
              })}
            </Stagger>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8 lg:py-24">
          <Reveal className="relative overflow-hidden rounded-[36px] border border-primary/20 bg-gradient-to-br from-primary/12 via-card to-violet-500/10 px-6 py-14 text-center sm:px-12 sm:py-20">
            <div className="absolute inset-0 bg-dots opacity-40" />
            <div className="relative">
              <span className="inline-flex items-center gap-2 rounded-full border border-primary/25 bg-background/50 px-3 py-1.5 text-[11px] font-semibold text-primary">
                <Sparkles className="h-3.5 w-3.5" /> 2-minute demo
              </span>
              <h2 className="mx-auto mt-5 max-w-2xl text-balance font-display text-3xl font-bold tracking-tight sm:text-5xl">
                Stop reporting erasure. Start proving it.
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-muted-foreground">
                Seed a realistic workspace with a complete erasure, an incomplete audit,
                a non-deletion request, and a pending ticket.
              </p>
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                <Button variant="brand" size="lg" onClick={() => void openDemo()} disabled={busy}>
                  {busy ? "Preparing workspace…" : "Create a free sandbox"}
                  <ChevronRight className="h-4 w-4" />
                </Button>
                <a href="https://github.com/dsk-dev-ai/erasureproof" target="_blank" rel="noreferrer">
                  <Button variant="outline" size="lg">
                    View source <ArrowUpRight className="h-4 w-4" />
                  </Button>
                </a>
              </div>
              <div className="mt-8 flex flex-wrap items-center justify-center gap-6 text-xs text-muted-foreground">
                <span className="flex items-center gap-1.5"><Check className="h-3.5 w-3.5 text-success" /> Free sandbox key</span>
                <span className="flex items-center gap-1.5"><Check className="h-3.5 w-3.5 text-success" /> Local data</span>
                <span className="flex items-center gap-1.5"><Check className="h-3.5 w-3.5 text-success" /> Open source</span>
              </div>
            </div>
          </Reveal>
        </section>
      </main>

      <SandboxDialog sandbox={sandbox} open={sandboxOpen} onClose={closeSandbox} />

      <footer className="border-t border-border/60">
        <div className="mx-auto flex max-w-7xl flex-col gap-8 px-4 py-10 sm:px-6 lg:px-8">
          <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-start">
            <div className="max-w-sm">
              <Logo />
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                The deletion audit control plane. Reconstruct, remediate, and prove erasure across
                every system that holds a person&apos;s data.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-10 text-sm sm:grid-cols-3">
              <div>
                <p className="mb-3 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Product</p>
                <div className="space-y-2">
                  <Link to="/app" className="block text-muted-foreground hover:text-foreground">Console</Link>
                  <a href="#product" className="block text-muted-foreground hover:text-foreground">Capabilities</a>
                  <a href="#workflow" className="block text-muted-foreground hover:text-foreground">Workflow</a>
                </div>
              </div>
              <div>
                <p className="mb-3 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Developers</p>
                <div className="space-y-2">
                  <Link to="/app/docs" className="block text-muted-foreground hover:text-foreground">Documentation</Link>
                  <a href="/docs" target="_blank" rel="noreferrer" className="block text-muted-foreground hover:text-foreground">API reference</a>
                  <a href="https://github.com/dsk-dev-ai/erasureproof" className="block text-muted-foreground hover:text-foreground">GitHub</a>
                </div>
              </div>
              <div>
                <p className="mb-3 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Trust</p>
                <a href="#security" className="block text-muted-foreground hover:text-foreground">Security model</a>
                <Link to="/app/evidence" className="mt-2 block text-muted-foreground hover:text-foreground">Ledger</Link>
              </div>
            </div>
          </div>
          <div className="flex flex-col gap-3 border-t border-border/50 pt-6 text-[11px] text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
            <p>© 2026 ErasureProof. Built for teams that take erasure seriously.</p>
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-success" /> All systems operational
              </span>
              <span className="font-mono">v1.1.2</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
