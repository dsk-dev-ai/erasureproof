import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  CircleAlert,
  Database,
  FileSearch,
  Fingerprint,
  Plus,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Users,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { toast } from "sonner";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { StatusBadge } from "@/components/requests/status-badge";
import { NewRequestDialog } from "@/components/requests/new-request-dialog";
import { CountUp, MotionDiv, Reveal } from "@/components/motion/motion";
import { useOverview, useSeedDemo } from "@/hooks/use-api";
import { useTenant } from "@/components/tenant-provider";
import { cn, formatRelative, humanize, timeAgo } from "@/lib/utils";

const statusColors: Record<string, string> = {
  COMPLETE: "#34d399",
  INCOMPLETE: "#fb7185",
  NOT_APPLICABLE: "#64748b",
  PENDING: "#fbbf24",
};

function MetricCard({
  label,
  value,
  suffix,
  detail,
  icon,
  tone = "default",
  delay = 0,
}: {
  label: string;
  value: number;
  suffix?: string;
  detail: string;
  icon: React.ReactNode;
  tone?: "default" | "success" | "danger" | "warning";
  delay?: number;
}) {
  return (
    <MotionDiv delay={delay}>
      <Card className="group relative overflow-hidden">
        <CardContent className="p-5">
          <div className="flex items-start justify-between">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              {label}
            </p>
            <span
              className={cn(
                "flex h-9 w-9 items-center justify-center rounded-xl border",
                tone === "success" && "border-emerald-400/20 bg-emerald-400/10 text-emerald-300",
                tone === "danger" && "border-rose-400/20 bg-rose-400/10 text-rose-300",
                tone === "warning" && "border-amber-400/20 bg-amber-400/10 text-amber-300",
                tone === "default" && "border-primary/20 bg-primary/10 text-primary",
              )}
            >
              {icon}
            </span>
          </div>
          <p className="mt-4 font-display text-3xl font-bold tracking-tight">
            <CountUp value={value} suffix={suffix} />
          </p>
          <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
          <div className="pointer-events-none absolute -bottom-12 -right-8 h-28 w-28 rounded-full bg-primary/5 blur-2xl transition group-hover:bg-primary/10" />
        </CardContent>
      </Card>
    </MotionDiv>
  );
}

function PanelSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: 4 }).map((_, index) => (
        <Skeleton key={index} className="h-[148px]" />
      ))}
    </div>
  );
}

export function DashboardPage() {
  const { tenant, tenantId, setTenantId } = useTenant();
  const { data, isLoading, isError, error, refetch } = useOverview(tenantId);
  const seed = useSeedDemo();
  const [newOpen, setNewOpen] = useState(false);

  const loadDemo = async () => {
    try {
      const result = await seed.mutateAsync();
      const id = result.tenant_id as string | undefined;
      if (id) setTenantId(id);
      toast.success("Demo workspace loaded");
      void refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not seed demo");
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-24 w-full max-w-2xl" />
        <PanelSkeleton />
        <div className="grid gap-4 xl:grid-cols-[1.55fr_1fr]">
          <Skeleton className="h-[320px]" />
          <Skeleton className="h-[320px]" />
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <ErrorState
        message={error instanceof Error ? error.message : undefined}
        onRetry={() => void refetch()}
      />
    );
  }

  if (!data.totals.requests && !data.totals.subjects) {
    return (
      <>
        <PageHeader
          eyebrow="Overview"
          title="Your audit workspace is empty"
          description="Create a request, or load a realistic demo with a complete erasure, an incomplete audit, and a non-deletion request."
        />
        <div className="mt-8">
          <EmptyState
            icon={<Sparkles className="h-6 w-6" />}
            title="See the whole control plane in one click"
            description="The demo is local, deterministic, and non-destructive. It gives you subjects, connectors, evidence, findings, remediation plans, and a verified ledger."
            action={
              <div className="flex flex-wrap justify-center gap-2">
                <Button variant="brand" size="lg" onClick={() => void loadDemo()} disabled={seed.isPending}>
                  {seed.isPending ? "Building workspace…" : "Load demo workspace"}
                  <ArrowRight className="h-4 w-4" />
                </Button>
                <Button variant="outline" size="lg" onClick={() => setNewOpen(true)}>
                  <Plus className="h-4 w-4" /> New request
                </Button>
              </div>
            }
          />
        </div>
        <NewRequestDialog open={newOpen} onClose={() => setNewOpen(false)} />
      </>
    );
  }

  const statusData = Object.entries(data.statuses)
    .filter(([, value]) => value > 0)
    .map(([name, value]) => ({ name, value }));
  const pending = data.statuses.PENDING ?? 0;
  const complete = data.statuses.COMPLETE ?? 0;
  const incomplete = data.statuses.INCOMPLETE ?? 0;
  const passRate = Math.round(data.verification.pass_rate * 100);

  return (
    <>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Overview"
          title={`${tenant?.name ?? "All workspaces"}`}
          description={`Audit state at ${formatRelative(data.generated_at)}. Every number below is derived from evidence and the ledger, not workflow claims.`}
          actions={
            <>
              {tenantId !== "ten_demo" && (
                <Button
                  variant="secondary"
                  onClick={() => void loadDemo()}
                  disabled={seed.isPending}
                >
                  <Sparkles className="h-4 w-4" /> {seed.isPending ? "Loading…" : "Load demo"}
                </Button>
              )}
              <Button variant="brand" onClick={() => setNewOpen(true)}>
                <Plus className="h-4 w-4" /> New request
              </Button>
            </>
          }
        />

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="Open findings"
            value={data.open_findings}
            detail={`${incomplete} incomplete · ${pending} pending`}
            icon={<CircleAlert className="h-4 w-4" />}
            tone="danger"
            delay={0}
          />
          <MetricCard
            label="Verified checks"
            value={passRate}
            suffix="%"
            detail={`${data.verification.passed}/${data.verification.checks} verification steps passed`}
            icon={<ShieldCheck className="h-4 w-4" />}
            tone="success"
            delay={0.06}
          />
          <MetricCard
            label="Attested requests"
            value={Math.round(data.attestation_coverage * 100)}
            suffix="%"
            detail={`${data.totals.attestations} signed attestations issued`}
            icon={<CheckCircle2 className="h-4 w-4" />}
            delay={0.12}
          />
          <MetricCard
            label="Risk score"
            value={data.risk_score}
            suffix="/100"
            detail={`${data.totals.evidence} evidence artifacts · ${data.totals.ledger_entries} ledger entries`}
            icon={<Activity className="h-4 w-4" />}
            tone={data.risk_score > 60 ? "danger" : data.risk_score > 30 ? "warning" : "success"}
            delay={0.18}
          />
        </div>

        <div className="grid gap-4 xl:grid-cols-[1.55fr_1fr]">
          <Reveal>
            <Card className="h-full">
              <CardHeader className="flex-row items-start justify-between">
                <div>
                  <CardTitle>Audit volume</CardTitle>
                  <CardDescription>Requests created over the recent audit window</CardDescription>
                </div>
                <span className="flex items-center gap-1.5 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2.5 py-1 text-[10px] font-semibold text-emerald-300">
                  <TrendingUp className="h-3 w-3" /> {data.totals.requests} total
                </span>
              </CardHeader>
              <CardContent>
                <div className="h-[260px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={data.trend} margin={{ left: -22, right: 6, top: 8 }}>
                      <defs>
                        <linearGradient id="trend-fill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#2dd4bf" stopOpacity={0.35} />
                          <stop offset="100%" stopColor="#2dd4bf" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid stroke="hsl(var(--border))" strokeOpacity={0.42} vertical={false} />
                      <XAxis
                        dataKey="date"
                        tickFormatter={(value: string) => value.slice(5)}
                        tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        allowDecimals={false}
                        tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip
                        contentStyle={{
                          background: "hsl(var(--card))",
                          border: "1px solid hsl(var(--border))",
                          borderRadius: 12,
                          fontSize: 12,
                        }}
                        labelFormatter={(label: string) => `Audit date ${label}`}
                      />
                      <Area
                        type="monotone"
                        dataKey="count"
                        stroke="#2dd4bf"
                        strokeWidth={2.5}
                        fill="url(#trend-fill)"
                        animationDuration={900}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </Reveal>

          <Reveal delay={0.08}>
            <Card className="h-full">
              <CardHeader>
                <CardTitle>Status mix</CardTitle>
                <CardDescription>Current request outcomes</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <div className="relative h-[164px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={statusData}
                        dataKey="value"
                        nameKey="name"
                        innerRadius={50}
                        outerRadius={72}
                        paddingAngle={3}
                        stroke="none"
                      >
                        {statusData.map((entry) => (
                          <Cell key={entry.name} fill={statusColors[entry.name] ?? "#64748b"} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          background: "hsl(var(--card))",
                          border: "1px solid hsl(var(--border))",
                          borderRadius: 12,
                          fontSize: 12,
                        }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                    <p className="font-display text-2xl font-bold">{data.totals.requests}</p>
                    <p className="text-[10px] uppercase tracking-widest text-muted-foreground">requests</p>
                  </div>
                </div>
                <div className="space-y-1.5">
                  {[
                    ["Complete", complete, "COMPLETE"],
                    ["Incomplete", incomplete, "INCOMPLETE"],
                    ["Not applicable", data.statuses.NOT_APPLICABLE ?? 0, "NOT_APPLICABLE"],
                    ["Pending", pending, "PENDING"],
                  ].map(([label, value, key]) => (
                    <div key={String(key)} className="flex items-center gap-2 text-xs">
                      <span
                        className="h-2 w-2 rounded-full"
                        style={{ backgroundColor: statusColors[String(key)] }}
                      />
                      <span className="flex-1 text-muted-foreground">{label}</span>
                      <span className="font-mono text-foreground">{value}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </Reveal>
        </div>

        <div className="grid gap-4 xl:grid-cols-[1.55fr_1fr]">
          <Reveal>
            <Card>
              <CardHeader className="flex-row items-center justify-between">
                <div>
                  <CardTitle>Recent audits</CardTitle>
                  <CardDescription>Latest requests and their proven state</CardDescription>
                </div>
                <Link
                  to="/app/requests"
                  className="flex items-center gap-1 text-xs font-semibold text-primary hover:underline"
                >
                  View all <ArrowRight className="h-3 w-3" />
                </Link>
              </CardHeader>
              <CardContent className="px-3 pb-3">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="text-[10px] uppercase tracking-widest text-muted-foreground">
                        <th className="px-3 py-2 font-medium">Subject</th>
                        <th className="px-3 py-2 font-medium">Status</th>
                        <th className="hidden px-3 py-2 font-medium sm:table-cell">Findings</th>
                        <th className="hidden px-3 py-2 font-medium md:table-cell">Audit at</th>
                        <th className="px-3 py-2" />
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent_requests.map((request) => (
                        <tr
                          key={request.id}
                          className="group border-t border-border/50 transition hover:bg-accent/40"
                        >
                          <td className="px-3 py-3">
                            <p className="font-medium">{request.email}</p>
                            <p className="font-mono text-[10px] text-muted-foreground">{request.id}</p>
                          </td>
                          <td className="px-3 py-3">
                            <StatusBadge status={request.status} />
                          </td>
                          <td className="hidden px-3 py-3 font-mono text-xs text-muted-foreground sm:table-cell">
                            {request.findings}
                          </td>
                          <td className="hidden px-3 py-3 text-xs text-muted-foreground md:table-cell">
                            {timeAgo(request.audit_at)}
                          </td>
                          <td className="px-3 py-3 text-right">
                            <Link
                              to={`/app/requests/${request.id}`}
                              className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition group-hover:bg-primary/10 group-hover:text-primary"
                            >
                              <ArrowUpRight className="h-4 w-4" />
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </Reveal>

          <div className="space-y-4">
            <Reveal delay={0.06}>
              <Card>
                <CardHeader>
                  <CardTitle>Control coverage</CardTitle>
                  <CardDescription>Workspace resources in scope</CardDescription>
                </CardHeader>
                <CardContent className="grid grid-cols-2 gap-2">
                  {[
                    { label: "Subjects", value: data.totals.subjects, icon: Users },
                    { label: "Connectors", value: data.totals.connectors, icon: Database },
                    { label: "Evidence", value: data.totals.evidence, icon: FileSearch },
                    { label: "Ledger", value: data.totals.ledger_entries, icon: Fingerprint },
                  ].map((item) => {
                    const Icon = item.icon;
                    return (
                      <div key={item.label} className="rounded-2xl border border-border/60 bg-background/35 p-3">
                        <Icon className="mb-2 h-4 w-4 text-primary" />
                        <p className="font-display text-xl font-semibold">{item.value}</p>
                        <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{item.label}</p>
                      </div>
                    );
                  })}
                </CardContent>
              </Card>
            </Reveal>

            <Reveal delay={0.12}>
              <Card>
                <CardHeader>
                  <CardTitle>Policies in force</CardTitle>
                  <CardDescription>Jurisdiction rules applied to plans</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {data.policies.map((policy) => (
                      <span
                        key={policy}
                        className="rounded-lg border border-border/70 bg-muted/40 px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground"
                      >
                        {humanize(policy)}
                      </span>
                    ))}
                  </div>
                  <div className="mt-4 space-y-2 border-t border-border/50 pt-4 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Environment</span>
                      <span className="font-mono">{data.features.environment}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Exposure scans</span>
                      <span className={data.features.exposure_enabled ? "text-success" : "text-muted-foreground"}>
                        {data.features.exposure_enabled ? "Enabled" : "Disabled"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Ledger head</span>
                      <span className="max-w-28 truncate font-mono text-primary">{data.ledger.head}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Reveal>
          </div>
        </div>

        {data.ledger.recent.length ? (
          <Reveal>
            <Card>
              <CardHeader className="flex-row items-center justify-between">
                <div>
                  <CardTitle>Live ledger</CardTitle>
                  <CardDescription>Append-only events, newest first</CardDescription>
                </div>
                <Link
                  to="/app/evidence"
                  className="flex items-center gap-1 text-xs font-semibold text-primary hover:underline"
                >
                  Inspect ledger <ArrowRight className="h-3 w-3" />
                </Link>
              </CardHeader>
              <CardContent className="px-3 pb-3">
                <div className="space-y-1">
                  {data.ledger.recent.slice(0, 6).map((entry) => (
                    <div
                      key={entry.seq}
                      className="flex items-center gap-3 rounded-xl px-3 py-2 text-xs transition hover:bg-accent/40"
                    >
                      <span className="w-10 font-mono text-[10px] text-muted-foreground">
                        {String(entry.seq).padStart(4, "0")}
                      </span>
                      <span className="flex-1 truncate font-medium">{humanize(entry.event)}</span>
                      <span className="hidden max-w-32 truncate font-mono text-[10px] text-primary sm:block">
                        {entry.hash.slice(0, 12)}…
                      </span>
                      <span className="text-[10px] text-muted-foreground">{timeAgo(entry.timestamp)}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </Reveal>
        ) : null}
      </div>
      <NewRequestDialog open={newOpen} onClose={() => setNewOpen(false)} />
    </>
  );
}
