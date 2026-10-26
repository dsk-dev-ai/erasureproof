import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowUpRight,
  Check,
  Globe2,
  Loader2,
  Radar,
  ScanSearch,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input, Label, Textarea } from "@/components/ui/input";
import { useOverview } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { useTenant } from "@/components/tenant-provider";
import { MotionDiv } from "@/components/motion/motion";
import { cn, formatDate, humanize } from "@/lib/utils";
import type { ExposureReport } from "@/lib/types";

const collectorOptions = [
  { id: "direct", label: "Direct URL" },
  { id: "wayback", label: "Wayback" },
  { id: "search", label: "Search index" },
  { id: "hibp", label: "Breach lookup" },
  { id: "github", label: "GitHub public" },
  { id: "gravatar", label: "Gravatar" },
  { id: "username", label: "Username sweep" },
];

function severityClass(severity: string) {
  switch (severity.toLowerCase()) {
    case "critical":
    case "high":
      return "border-rose-400/25 bg-rose-400/[0.05] text-rose-300";
    case "medium":
      return "border-amber-400/25 bg-amber-400/[0.05] text-amber-300";
    default:
      return "border-border/70 bg-muted/20 text-muted-foreground";
  }
}

export function ExposurePage() {
  const { tenantId } = useTenant();
  const { data: overview } = useOverview(tenantId);
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [usernames, setUsernames] = useState("");
  const [urls, setUrls] = useState("");
  const [authorized, setAuthorized] = useState(false);
  const [collectors, setCollectors] = useState<string[]>(["direct", "wayback", "search", "github", "gravatar", "username"]);
  const [report, setReport] = useState<ExposureReport | null>(null);

  const scan = useMutation({
    mutationFn: () =>
      api.exposure({
        email: email.trim() || undefined,
        phone: phone.trim() || undefined,
        name: name.trim() || undefined,
        usernames: usernames.split(",").map((item) => item.trim()).filter(Boolean),
        urls: urls.split(/[\n,]/).map((item) => item.trim()).filter(Boolean),
        collectors,
        authorized,
      }),
    onSuccess: (data) => {
      setReport(data);
      toast.success(`Scan complete · ${data.hits.length} public findings`);
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Exposure scan failed");
    },
  });

  const toggleCollector = (id: string) => {
    setCollectors((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  };

  const enabled = overview?.features.exposure_enabled ?? false;
  const canSubmit = authorized && enabled && (email || phone || name || usernames || urls) && !scan.isPending;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Exposure intelligence"
        title="Public exposure scan"
        description="Passive, authorized discovery of identifiers that remain reachable on public sources. No exploitation, credential attacks, or breach-dump downloads."
        actions={
          <Badge variant={enabled ? "success" : "warning"} dot>
            {enabled ? "Scanner enabled" : "Scanner disabled"}
          </Badge>
        }
      />

      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <Card>
          <CardHeader>
            <CardTitle>Scan target</CardTitle>
            <CardDescription>Use only identifiers you are authorized to investigate.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="exposure-email">Email</Label>
                <Input id="exposure-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="alice@example.com" />
              </div>
              <div>
                <Label htmlFor="exposure-phone">Phone</Label>
                <Input id="exposure-phone" value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="+1 415 555 0134" />
              </div>
            </div>
            <div>
              <Label htmlFor="exposure-name">Full name</Label>
              <Input id="exposure-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="Alice Mercer" />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="exposure-usernames">Usernames</Label>
                <Input id="exposure-usernames" value={usernames} onChange={(event) => setUsernames(event.target.value)} placeholder="alice, alice-m" />
              </div>
              <div>
                <Label htmlFor="exposure-urls">Known URLs</Label>
                <Textarea id="exposure-urls" value={urls} onChange={(event) => setUrls(event.target.value)} placeholder="https://example.com/profile/alice" className="min-h-11" />
              </div>
            </div>
            <div>
              <Label>Collectors</Label>
              <div className="flex flex-wrap gap-1.5">
                {collectorOptions.map((collector) => {
                  const active = collectors.includes(collector.id);
                  return (
                    <button
                      key={collector.id}
                      type="button"
                      onClick={() => toggleCollector(collector.id)}
                      className={cn(
                        "flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[11px] transition",
                        active
                          ? "border-primary/30 bg-primary/10 text-primary"
                          : "border-border/70 text-muted-foreground hover:border-primary/20",
                      )}
                    >
                      {active ? <Check className="h-3 w-3" /> : null}
                      {collector.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-amber-400/20 bg-amber-400/[0.035] p-3.5">
              <input
                type="checkbox"
                checked={authorized}
                onChange={(event) => setAuthorized(event.target.checked)}
                className="mt-0.5 h-4 w-4 accent-[hsl(var(--primary))]"
              />
              <span className="text-[11px] leading-5 text-muted-foreground">
                I confirm I have authorization to investigate these identifiers. This run is passive,
                rate-limited, and recorded in the audit ledger.
              </span>
            </label>

            {!enabled ? (
              <div className="flex items-start gap-2 rounded-xl border border-border/70 bg-muted/25 p-3 text-[11px] leading-5 text-muted-foreground">
                <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                Set <code className="rounded bg-background/70 px-1 font-mono">ERASUREPROOF_EXPOSURE_ENABLED=true</code> on the server to enable live collection.
              </div>
            ) : null}

            <Button variant="brand" className="w-full" disabled={!canSubmit} onClick={() => scan.mutate()}>
              {scan.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Radar className="h-4 w-4" />}
              {scan.isPending ? "Scanning public sources…" : "Run authorized scan"}
            </Button>
          </CardContent>
        </Card>

        <Card className="relative overflow-hidden">
          <CardHeader>
            <CardTitle>Scan telemetry</CardTitle>
            <CardDescription>Collector coverage and safety state</CardDescription>
          </CardHeader>
          <CardContent>
            {scan.isPending ? (
              <div className="flex min-h-[330px] flex-col items-center justify-center">
                <div className="relative flex h-44 w-44 items-center justify-center">
                  {[0, 1, 2].map((index) => (
                    <span
                      key={index}
                      className="absolute rounded-full border border-primary/25"
                      style={{
                        inset: `${index * 22}px`,
                        animation: `ping 2.2s cubic-bezier(0, 0, 0.2, 1) ${index * 0.35}s infinite`,
                      }}
                    />
                  ))}
                  <span className="relative flex h-20 w-20 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <ScanSearch className="h-8 w-8" />
                  </span>
                </div>
                <p className="mt-8 font-display text-lg font-semibold">Collecting public signals</p>
                <p className="mt-1 text-xs text-muted-foreground">Respecting robots, rate limits, and the passive-only boundary.</p>
              </div>
            ) : report ? (
              <div className="space-y-4">
                <div className={cn("flex items-center gap-3 rounded-2xl border p-4", severityClass(report.severity))}>
                  <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-background/30">
                    {report.hits.length ? <ShieldAlert className="h-5 w-5" /> : <ShieldCheck className="h-5 w-5" />}
                  </span>
                  <div className="flex-1">
                    <p className="font-display text-lg font-semibold">{report.hits.length ? `${report.hits.length} public findings` : "No confirmed exposure"}</p>
                    <p className="text-[11px] opacity-80">Risk {report.risk_score}/100 · {humanize(report.severity)} severity</p>
                  </div>
                  <Badge variant={report.hits.length ? "danger" : "success"}>{humanize(report.severity)}</Badge>
                </div>

                <div className="space-y-2">
                  {report.hits.slice(0, 6).map((hit, index) => (
                    <MotionDiv key={`${hit.url}-${index}`} delay={index * 0.04}>
                      <a
                        href={hit.url}
                        target="_blank"
                        rel="noreferrer"
                        className="group block rounded-2xl border border-border/60 bg-background/30 p-3.5 transition hover:border-primary/25"
                      >
                        <div className="flex items-start gap-3">
                          <Globe2 className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium">{hit.title || hit.url}</p>
                            <p className="mt-0.5 line-clamp-2 text-[11px] leading-5 text-muted-foreground">{hit.snippet}</p>
                            <div className="mt-2 flex flex-wrap items-center gap-2 text-[9px] uppercase tracking-wider text-muted-foreground">
                              <span>{hit.collector}</span>
                              <span>·</span>
                              <span>{Math.round(hit.confidence * 100)}% confidence</span>
                              <span>·</span>
                              <span>{hit.identifiers.join(", ")}</span>
                            </div>
                          </div>
                          <ArrowUpRight className="h-4 w-4 shrink-0 text-muted-foreground transition group-hover:text-primary" />
                        </div>
                      </a>
                    </MotionDiv>
                  ))}
                </div>

                <div className="grid grid-cols-3 gap-2 border-t border-border/50 pt-3 text-[10px]">
                  <div>
                    <p className="uppercase tracking-wider text-muted-foreground">Collectors</p>
                    <p className="mt-1 font-mono">{report.collectors.length}</p>
                  </div>
                  <div>
                    <p className="uppercase tracking-wider text-muted-foreground">Errors</p>
                    <p className="mt-1 font-mono">{report.errors.length}</p>
                  </div>
                  <div>
                    <p className="uppercase tracking-wider text-muted-foreground">Evidence</p>
                    <p className="mt-1 truncate font-mono text-primary">{report.report_evidence_id}</p>
                  </div>
                </div>
                <p className="text-[10px] text-muted-foreground">Scanned {formatDate(report.scanned_at)}</p>
              </div>
            ) : (
              <div className="flex min-h-[330px] flex-col items-center justify-center text-center">
                <span className="relative flex h-24 w-24 items-center justify-center rounded-full border border-primary/20 bg-primary/5">
                  <span className="absolute inset-3 rounded-full border border-primary/15" />
                  <Radar className="h-8 w-8 text-primary/70" />
                </span>
                <p className="mt-6 font-display text-base font-semibold">No scan yet</p>
                <p className="mt-1 max-w-xs text-xs leading-5 text-muted-foreground">
                  Results will show confirmed public hits, confidence, collector provenance, and a linked evidence artifact.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {[
          { icon: ShieldCheck, title: "Passive by design", body: "Only public HTTP responses, search snippets, and explicitly supplied URLs." },
          { icon: AlertTriangle, title: "Explicit authorization", body: "The server refuses scans without both operator authorization and an enable flag." },
          { icon: Sparkles, title: "Evidence-backed", body: "Every report becomes a fingerprinted artifact and a ledger event." },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <Card key={item.title}>
              <CardContent className="p-5">
                <Icon className="mb-3 h-4 w-4 text-primary" />
                <p className="text-sm font-semibold">{item.title}</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">{item.body}</p>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
