import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Check,
  Copy,
  ExternalLink,
  FileKey2,
  FileText,
  Fingerprint,
  Link2,
  Loader2,
  LockKeyhole,
  Scale,
  Search,
  ShieldCheck,
  ShieldX,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input, Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs } from "@/components/ui/tabs";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { useEvidence, useLedger, usePolicies, useVerifyEvidence, useVerifyLedger } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { cn, formatDate, humanize, truncate } from "@/lib/utils";

interface PolicyDecision {
  action: string;
  rule_name: string;
  redact_fields: string[];
  retain_fields: string[];
  reason: string;
}

interface PolicyDoc {
  name: string;
  jurisdiction: string;
  version: string;
  defaults: Record<string, PolicyDecision>;
  rules: Array<PolicyDecision & { name: string; priority: number; when: Record<string, unknown> }>;
}

const actionTone = (action: string) => {
  switch (action.toUpperCase()) {
    case "DELETE":
      return "danger";
    case "REDACT":
    case "TOMBSTONE":
      return "warning";
    case "ANONYMIZE":
      return "default";
    case "RETAIN":
      return "success";
    default:
      return "muted";
  }
};

export function EvidencePage() {
  const [params] = useSearchParams();
  const highlight = params.get("highlight");
  const [tab, setTab] = useState(highlight ? "evidence" : "evidence");
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("ALL");
  const [policyJurisdiction, setPolicyJurisdiction] = useState<string | null>(null);
  const evidence = useEvidence();
  const ledger = useLedger();
  const policies = usePolicies();
  const verifyEvidence = useVerifyEvidence();
  const verifyLedger = useVerifyLedger();

  const sources = useMemo(
    () => [...new Set((evidence.data?.items ?? []).map((item) => item.source))].sort(),
    [evidence.data?.items],
  );

  const items = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (evidence.data?.items ?? []).filter((item) => {
      if (source !== "ALL" && item.source !== source) return false;
      if (!needle) return true;
      return (
        item.evidence_id.toLowerCase().includes(needle) ||
        item.sha256.toLowerCase().includes(needle) ||
        item.source.toLowerCase().includes(needle) ||
        (item.request_id ?? "").toLowerCase().includes(needle)
      );
    });
  }, [evidence.data?.items, query, source]);

  const policyData = policies.data?.policies as Record<string, PolicyDoc> | undefined;
  const jurisdictions = policies.data?.jurisdictions ?? [];
  const activePolicy = policyJurisdiction ?? jurisdictions[0];
  const currentPolicy = activePolicy ? policyData?.[activePolicy] : undefined;

  const copy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      toast.success("Copied");
    } catch {
      toast.error("Clipboard unavailable");
    }
  };

  const tabItems = [
    { value: "evidence", label: "Evidence", count: evidence.data?.items.length },
    { value: "ledger", label: "Ledger", count: ledger.data?.entries.length },
    { value: "policies", label: "Policy matrix", count: jurisdictions.length },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Trust center"
        title="Evidence & ledger"
        description="Fingerprinted artifacts, an append-only event chain, and the policy matrix that determines every required action."
        actions={
          verifyLedger.data ? (
            <Badge variant={verifyLedger.data.valid ? "success" : "danger"} dot>
              {verifyLedger.data.valid ? "Ledger verified" : "Ledger invalid"}
            </Badge>
          ) : (
            <Button
              variant="outline"
              onClick={() =>
                verifyLedger.mutate(undefined, {
                  onSuccess: (result) =>
                    result.valid
                      ? toast.success(`Ledger verified · ${result.detail}`)
                      : toast.error(result.detail),
                })
              }
              disabled={verifyLedger.isPending}
            >
              {verifyLedger.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
              Verify ledger
            </Button>
          )
        }
      />

      <Tabs value={tab} onChange={setTab} items={tabItems} className="w-fit" />

      {tab === "evidence" ? (
        <>
          <Card className="p-3">
            <div className="flex flex-col gap-2 sm:flex-row">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search evidence ID, fingerprint, source, or request…"
                  className="pl-9"
                />
              </div>
              <Select value={source} onChange={(event) => setSource(event.target.value)} className="sm:w-52">
                <option value="ALL">All sources</option>
                {sources.map((item) => <option key={item} value={item}>{humanize(item)}</option>)}
              </Select>
            </div>
          </Card>

          {evidence.isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, index) => <Skeleton key={index} className="h-[90px]" />)}
            </div>
          ) : evidence.isError ? (
            <ErrorState
              message={evidence.error instanceof Error ? evidence.error.message : undefined}
              onRetry={() => void evidence.refetch()}
            />
          ) : !items.length ? (
            <EmptyState
              icon={<FileKey2 className="h-6 w-6" />}
              title="No evidence artifacts"
              description="Evidence is created when audits discover files, scan public sources, or write attestations."
            />
          ) : (
            <Card className="divide-y divide-border/50 overflow-hidden">
              {items.map((item) => {
                const isHighlighted = item.evidence_id === highlight;
                return (
                  <div
                    key={item.evidence_id}
                    className={cn(
                      "flex flex-col gap-3 px-4 py-4 transition sm:flex-row sm:items-center",
                      isHighlighted ? "bg-primary/[0.06]" : "hover:bg-accent/25",
                    )}
                  >
                    <span className={cn(
                      "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl",
                      isHighlighted ? "bg-primary/15 text-primary" : "bg-muted/60 text-muted-foreground",
                    )}>
                      <FileText className="h-4 w-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-[11px] font-medium text-primary">{item.evidence_id}</span>
                        <Badge variant="muted">{humanize(item.source)}</Badge>
                        {isHighlighted ? <Badge variant="default">Cited by plan</Badge> : null}
                      </div>
                      <button
                        onClick={() => void copy(item.sha256)}
                        className="mt-1 flex max-w-full items-center gap-1.5 font-mono text-[10px] text-muted-foreground hover:text-foreground"
                        title="Copy SHA-256"
                      >
                        <Fingerprint className="h-3 w-3 shrink-0" />
                        <span className="truncate">{item.sha256}</span>
                        <Copy className="h-2.5 w-2.5 shrink-0" />
                      </button>
                    </div>
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-muted-foreground">
                      <span>{item.content_type}</span>
                      <span>{Math.max(1, Math.round(item.size / 1024))} KB</span>
                      <span>{formatDate(item.captured_at)}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          verifyEvidence.mutate(item.evidence_id, {
                            onSuccess: (result) =>
                              result.valid
                                ? toast.success("Evidence fingerprint verified")
                                : toast.error("Fingerprint mismatch"),
                          })
                        }
                        disabled={verifyEvidence.isPending && verifyEvidence.variables === item.evidence_id}
                        aria-label={`Verify evidence ${item.evidence_id}`}
                        title="Verify fingerprint"
                      >
                        {verifyEvidence.isPending && verifyEvidence.variables === item.evidence_id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <ShieldCheck className="h-3.5 w-3.5" />
                        )}
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() =>
                          void api.openEvidence(item.evidence_id).catch((err) =>
                            toast.error(err instanceof Error ? err.message : "Could not open evidence"),
                          )
                        }
                      >
                        <ExternalLink className="h-3.5 w-3.5" /> Open
                      </Button>
                    </div>
                  </div>
                );
              })}
            </Card>
          )}
        </>
      ) : null}

      {tab === "ledger" ? (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Card className="sm:col-span-2">
              <CardContent className="flex items-center gap-4 p-5">
                <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                  <LockKeyhole className="h-5 w-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] uppercase tracking-widest text-muted-foreground">Current head</p>
                  <button
                    onClick={() => void copy(ledger.data?.head ?? "")}
                    className="mt-1 flex items-center gap-2 font-mono text-xs text-primary hover:underline"
                  >
                    <span className="truncate">{ledger.data?.head ?? "—"}</span>
                    <Copy className="h-3 w-3 shrink-0" />
                  </button>
                </div>
                {verifyLedger.data ? (
                  <Badge variant={verifyLedger.data.valid ? "success" : "danger"}>
                    {verifyLedger.data.valid ? <Check className="h-3 w-3" /> : <ShieldX className="h-3 w-3" />}
                    {verifyLedger.data.valid ? "Valid" : "Invalid"}
                  </Badge>
                ) : null}
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-5">
                <p className="text-[10px] uppercase tracking-widest text-muted-foreground">Entries</p>
                <p className="mt-2 font-display text-3xl font-bold">{ledger.data?.count ?? 0}</p>
                <p className="mt-1 text-[11px] text-muted-foreground">append-only events</p>
              </CardContent>
            </Card>
          </div>

          {ledger.isLoading ? (
            <Skeleton className="h-[400px]" />
          ) : ledger.isError ? (
            <ErrorState
              message={ledger.error instanceof Error ? ledger.error.message : undefined}
              onRetry={() => void ledger.refetch()}
            />
          ) : (
            <Card className="overflow-hidden">
              <CardHeader>
                <CardTitle>Event chain</CardTitle>
                <CardDescription>Each entry commits to the previous hash. Newest entries are shown last.</CardDescription>
              </CardHeader>
              <CardContent className="px-3 pb-3">
                <div className="max-h-[620px] overflow-y-auto">
                  {(ledger.data?.entries ?? []).map((entry) => (
                    <div key={entry.seq} className="flex items-start gap-3 rounded-xl px-3 py-2.5 transition hover:bg-accent/30">
                      <span className="mt-0.5 flex h-6 w-10 shrink-0 items-center justify-center rounded-md bg-muted font-mono text-[9px] text-muted-foreground">
                        {String(entry.seq).padStart(4, "0")}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-xs font-medium">{humanize(entry.event)}</span>
                          {entry.request_id ? (
                            <span className="font-mono text-[9px] text-primary">{entry.request_id}</span>
                          ) : null}
                        </div>
                        <p className="mt-0.5 truncate font-mono text-[9px] text-muted-foreground">
                          {entry.hash} ← {entry.prev_hash}
                        </p>
                      </div>
                      <span className="shrink-0 text-[9px] text-muted-foreground">{formatDate(entry.timestamp)}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      ) : null}

      {tab === "policies" ? (
        <>
          <div className="flex flex-wrap gap-2">
            {jurisdictions.map((item) => (
              <button
                key={item}
                onClick={() => setPolicyJurisdiction(item)}
                className={cn(
                  "rounded-xl border px-3 py-1.5 text-xs font-semibold transition",
                  activePolicy === item
                    ? "border-primary/30 bg-primary/10 text-primary"
                    : "border-border/70 text-muted-foreground hover:text-foreground",
                )}
              >
                {item}
              </button>
            ))}
          </div>

          {policies.isLoading ? (
            <Skeleton className="h-[420px]" />
          ) : policies.isError ? (
            <ErrorState
              message={policies.error instanceof Error ? policies.error.message : undefined}
              onRetry={() => void policies.refetch()}
            />
          ) : currentPolicy ? (
            <>
              <Card>
                <CardHeader className="flex-row items-start justify-between">
                  <div className="flex items-center gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                      <Scale className="h-5 w-5" />
                    </span>
                    <div>
                      <CardTitle>{currentPolicy.name}</CardTitle>
                      <CardDescription>
                        {currentPolicy.jurisdiction} · policy v{currentPolicy.version}
                      </CardDescription>
                    </div>
                  </div>
                  <Badge variant="default">{Object.keys(currentPolicy.defaults).length} categories</Badge>
                </CardHeader>
                <CardContent className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                  {Object.entries(currentPolicy.defaults).map(([category, decision]) => (
                    <div key={category} className="rounded-2xl border border-border/60 bg-background/35 p-4">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                          {humanize(category)}
                        </p>
                        <Badge variant={actionTone(decision.action)}>{humanize(decision.action)}</Badge>
                      </div>
                      <p className="mt-3 text-[11px] leading-5 text-muted-foreground">{decision.reason}</p>
                      {decision.redact_fields.length ? (
                        <p className="mt-2 font-mono text-[9px] text-muted-foreground">
                          redact: {decision.redact_fields.join(", ")}
                        </p>
                      ) : null}
                      {decision.retain_fields.length ? (
                        <p className="mt-1 font-mono text-[9px] text-muted-foreground">
                          retain: {decision.retain_fields.join(", ")}
                        </p>
                      ) : null}
                    </div>
                  ))}
                </CardContent>
              </Card>

              <Card className="overflow-hidden">
                <CardHeader>
                  <CardTitle>Conditional rules</CardTitle>
                  <CardDescription>Evaluated by priority before category defaults.</CardDescription>
                </CardHeader>
                <CardContent className="px-3 pb-3">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="text-[10px] uppercase tracking-widest text-muted-foreground">
                          <th className="px-3 py-2 font-medium">Rule</th>
                          <th className="px-3 py-2 font-medium">When</th>
                          <th className="px-3 py-2 font-medium">Action</th>
                          <th className="px-3 py-2 font-medium">Fields</th>
                          <th className="px-3 py-2 font-medium">Priority</th>
                        </tr>
                      </thead>
                      <tbody>
                        {currentPolicy.rules.map((rule) => (
                          <tr key={rule.name} className="border-t border-border/50">
                            <td className="px-3 py-3 font-medium">{humanize(rule.name)}</td>
                            <td className="px-3 py-3 font-mono text-[10px] text-muted-foreground">
                              {truncate(JSON.stringify(rule.when), 50)}
                            </td>
                            <td className="px-3 py-3"><Badge variant={actionTone(rule.action)}>{humanize(rule.action)}</Badge></td>
                            <td className="px-3 py-3 font-mono text-[10px] text-muted-foreground">
                              {[...rule.redact_fields, ...rule.retain_fields].join(", ") || "—"}
                            </td>
                            <td className="px-3 py-3 font-mono text-muted-foreground">{rule.priority}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {!currentPolicy.rules.length ? (
                      <p className="py-8 text-center text-sm text-muted-foreground">No conditional rules for this jurisdiction.</p>
                    ) : null}
                  </div>
                </CardContent>
              </Card>
            </>
          ) : (
            <EmptyState
              icon={<Link2 className="h-6 w-6" />}
              title="No policies loaded"
              description="The policy registry did not return a jurisdiction. Check the server configuration."
            />
          )}
        </>
      ) : null}
    </div>
  );
}
