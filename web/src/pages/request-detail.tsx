import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock4,
  Copy,
  Download,
  ExternalLink,
  FileCheck2,
  FileSearch,
  Fingerprint,
  GitBranch,
  Loader2,
  Play,
  RotateCw,
  ShieldCheck,
  ShieldX,
  Sparkles,
  Stamp,
  Terminal,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs } from "@/components/ui/tabs";
import { ErrorState } from "@/components/ui/error-state";
import { StatusBadge } from "@/components/requests/status-badge";
import { PlanGraph } from "@/components/requests/plan-graph";
import { MotionDiv } from "@/components/motion/motion";
import {
  useApprovals,
  useDecideApproval,
  useEvidence,
  useGraph,
  useOverview,
  useRequest,
  useRunRequest,
  useVerifyEvidence,
} from "@/hooks/use-api";
import { api } from "@/lib/api";
import { cn, formatDate, formatRelative, humanize } from "@/lib/utils";
import type { PlanStep, VerificationResult } from "@/lib/types";

const phaseOrder = ["FINDING", "REMEDIATION", "VERIFICATION"] as const;

const phaseMeta = {
  FINDING: {
    label: "Findings",
    description: "What remains at audit time",
    icon: FileSearch,
    className: "border-rose-400/20 bg-rose-400/[0.04]",
    text: "text-rose-300",
  },
  REMEDIATION: {
    label: "Remediation",
    description: "Safe, ordered corrective action",
    icon: Terminal,
    className: "border-amber-400/20 bg-amber-400/[0.04]",
    text: "text-amber-300",
  },
  VERIFICATION: {
    label: "Verification",
    description: "Checks that prove the final state",
    icon: ShieldCheck,
    className: "border-emerald-400/20 bg-emerald-400/[0.04]",
    text: "text-emerald-300",
  },
};

function stateTone(state: string) {
  switch (state.toUpperCase()) {
    case "PRESENT":
    case "ACTIVE":
      return "danger" as const;
    case "ABSENT":
    case "DISABLED":
    case "BLOCKED":
    case "REDACTED":
    case "ANONYMIZED":
      return "success" as const;
    default:
      return "muted" as const;
  }
}

function operationIcon(operation: string) {
  if (operation.startsWith("REPORT_")) return AlertTriangle;
  if (operation.startsWith("VERIFY_")) return ShieldCheck;
  if (operation === "DELETE_RECORD") return XCircle;
  if (operation === "BLOCK_RESTORE") return Download;
  if (operation === "DISABLE_DATA_FLOW") return GitBranch;
  return FileCheck2;
}

function StepRow({ step, index }: { step: PlanStep; index: number }) {
  const Icon = operationIcon(step.operation);
  return (
    <MotionDiv delay={Math.min(index * 0.02, 0.2)}>
      <div className="group flex gap-3 rounded-2xl border border-border/60 bg-background/30 p-3 transition hover:border-primary/25 hover:bg-accent/20 sm:gap-4">
        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-border/70 bg-card text-muted-foreground">
          <Icon className="h-3.5 w-3.5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[10px] text-muted-foreground">
              {String(step.step_no).padStart(2, "0")}
            </span>
            <span className="text-sm font-medium">{humanize(step.operation)}</span>
            <Badge variant={stateTone(step.state)} dot>
              {humanize(step.state)}
            </Badge>
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
            <span className="font-mono">{step.system_id}</span>
            <span className="text-border">/</span>
            <span className="font-mono text-foreground/70">{step.resource_id}</span>
            {step.category ? (
              <>
                <span className="text-border">·</span>
                <span>{step.category}</span>
              </>
            ) : null}
          </div>
        </div>
        {step.evidence_id ? (
          <Link
            to={`/app/evidence?highlight=${step.evidence_id}`}
            className="hidden self-center rounded-lg border border-primary/20 bg-primary/5 px-2 py-1 font-mono text-[10px] text-primary transition hover:bg-primary/10 sm:block"
          >
            {step.evidence_id}
          </Link>
        ) : (
          <span className="hidden self-center font-mono text-[10px] text-muted-foreground/60 sm:block">
            planned
          </span>
        )}
      </div>
    </MotionDiv>
  );
}

function VerificationRow({ result }: { result: VerificationResult }) {
  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-2xl border p-3",
        result.passed
          ? "border-emerald-400/20 bg-emerald-400/[0.04]"
          : "border-rose-400/20 bg-rose-400/[0.04]",
      )}
    >
      {result.passed ? (
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
      ) : (
        <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-300" />
      )}
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium">{humanize(result.operation)}</p>
        <p className="mt-0.5 truncate font-mono text-[10px] text-muted-foreground">
          {result.system_id}/{result.resource_id}
        </p>
        {result.detail ? (
          <p className="mt-1 text-[11px] leading-5 text-muted-foreground">{result.detail}</p>
        ) : null}
      </div>
      <div className="text-right">
        <p className="font-mono text-[10px] text-muted-foreground">
          {result.actual || "—"} / {result.expected || "—"}
        </p>
        {result.evidence_id ? (
          <span className="font-mono text-[9px] text-primary">{result.evidence_id}</span>
        ) : null}
      </div>
    </div>
  );
}

export function RequestDetailPage() {
  const { id } = useParams();
  const { data: request, isLoading, isError, error, refetch } = useRequest(id);
  const { data: graphData } = useGraph(request?.status && request.status !== "PENDING" ? id : undefined);
  const { data: evidenceData } = useEvidence();
  const run = useRunRequest();
  const verify = useVerifyEvidence();
  const { data: overview } = useOverview();
  const { data: approvals = [] } = useApprovals(request?.id);
  const decide = useDecideApproval();
  const [tab, setTab] = useState("plan");
  const [reason, setReason] = useState("");

  const plan = request?.result?.plan ?? request?.plan;
  const graph = request?.result?.graph ?? graphData;
  const result = request?.result;
  const steps = plan?.steps ?? [];
  const evidence = useMemo(
    () => (evidenceData?.items ?? []).filter((item) => item.request_id === request?.id),
    [evidenceData?.items, request?.id],
  );
  const evidenceIds = useMemo(() => new Set(steps.map((step) => step.evidence_id).filter(Boolean)), [steps]);
  const referencedEvidence = evidence.filter((item) => evidenceIds.has(item.evidence_id));
  const shownEvidence = referencedEvidence.length ? referencedEvidence : evidence;

  const counts = useMemo(
    () =>
      phaseOrder.reduce<Record<string, number>>((accumulator, phase) => {
        accumulator[phase] = steps.filter((step) => step.phase === phase).length;
        return accumulator;
      }, {}),
    [steps],
  );
  const verified = result?.verification ?? [];
  const passed = verified.filter((item) => item.passed).length;
  const isApplicable = request?.status !== "NOT_APPLICABLE";
  const needsRun = request?.status === "PENDING" || !steps.length;
  const approvalRequired = overview?.features.approval_required ?? false;
  const approvalExpired = request?.approval_expires_at
    ? new Date(request.approval_expires_at).getTime() <= Date.now()
    : false;
  const approvalActive =
    !approvalRequired ||
    Boolean(
      request?.approval_status === "APPROVED" &&
        !request.approval_consumed_at &&
        !approvalExpired,
    );
  const latestApproval = approvals[0];

  const decideApproval = async (decision: "APPROVED" | "REJECTED") => {
    if (!request) return;
    try {
      await decide.mutateAsync({
        id: request.id,
        decision,
        reason: reason.trim() || `${decision === "APPROVED" ? "Approved" : "Rejected"} in console`,
      });
      setReason("");
      toast.success(
        decision === "APPROVED"
          ? "Remediation approved. The audit can now run."
          : "Remediation rejected.",
      );
      void refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Approval action failed");
    }
  };

  const startAudit = async () => {
    if (!request) return;
    if (approvalRequired && !approvalActive) {
      toast.error("An administrator must approve remediation before this run.");
      return;
    }
    try {
      const response = await run.mutateAsync({ id: request.id, force: request.status !== "PENDING" });
      toast.success(
        response.status === "COMPLETE"
          ? "Audit complete. Every required verification passed."
          : response.status === "INCOMPLETE"
            ? "Audit complete. Findings and a remediation plan are ready."
            : "Request classified as not applicable to deletion.",
      );
      setTab("plan");
      void refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Audit failed");
    }
  };

  const copy = async (value: string, label: string) => {
    try {
      await navigator.clipboard.writeText(value);
      toast.success(`${label} copied`);
    } catch {
      toast.error("Clipboard is unavailable");
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-16 w-80" />
        <div className="grid gap-4 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => <Skeleton key={index} className="h-24" />)}
        </div>
        <Skeleton className="h-[420px]" />
      </div>
    );
  }

  if (isError || !request) {
    return (
      <ErrorState
        message={error instanceof Error ? error.message : undefined}
        onRetry={() => void refetch()}
      />
    );
  }

  const tabs = [
    { value: "plan", label: "Plan", count: steps.length },
    { value: "graph", label: "Dependency graph", count: graph?.nodes.length },
    { value: "evidence", label: "Evidence", count: shownEvidence.length },
    { value: "proof", label: "Verification & proof", count: verified.length },
  ];

  return (
    <div className="space-y-6">
      <div>
        <Link
          to="/app/requests"
          className="mb-4 inline-flex items-center gap-1.5 text-xs text-muted-foreground transition hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> All requests
        </Link>
        <PageHeader
          eyebrow={request.id}
          title={request.email}
          description={request.request_text}
          actions={
            <>
              <Button variant="outline" onClick={() => copy(request.id, "Request ID")}>
                <Copy className="h-3.5 w-3.5" /> Copy ID
              </Button>
              <Button
                variant="brand"
                onClick={() => void startAudit()}
                disabled={run.isPending || (approvalRequired && !approvalActive)}
                title={
                  approvalRequired && !approvalActive
                    ? "Administrator approval is required"
                    : undefined
                }
              >
                {run.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : needsRun ? <Play className="h-4 w-4" /> : <RotateCw className="h-4 w-4" />}
                {run.isPending ? "Running audit…" : needsRun ? "Run deletion audit" : "Re-run audit"}
              </Button>
            </>
          }
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={request.status} />
        <span className="rounded-full border border-border/70 px-2.5 py-1 font-mono text-[10px] text-muted-foreground">
          {request.jurisdiction}
        </span>
        <span className="rounded-full border border-border/70 px-2.5 py-1 text-[10px] text-muted-foreground">
          Requested {formatDate(request.requested_at)}
        </span>
        <span className="rounded-full border border-border/70 px-2.5 py-1 text-[10px] text-muted-foreground">
          Audit cutoff {formatDate(request.audit_at)}
        </span>
        {result?.ledger_head ? (
          <span className="rounded-full border border-primary/20 bg-primary/5 px-2.5 py-1 font-mono text-[10px] text-primary">
            ledger {result.ledger_head.slice(0, 10)}…
          </span>
        ) : null}
      </div>

      {approvalRequired && isApplicable ? (
        <Card
          className={cn(
            "overflow-hidden",
            approvalActive ? "border-emerald-400/20 bg-emerald-400/[0.03]" : "border-amber-400/25 bg-amber-400/[0.04]",
          )}
        >
          <CardHeader className="flex-row items-start gap-3">
            <span
              className={cn(
                "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl",
                approvalActive ? "bg-emerald-400/10 text-emerald-300" : "bg-amber-400/10 text-amber-300",
              )}
            >
              <Stamp className="h-4 w-4" />
            </span>
            <div className="min-w-0 flex-1">
              <CardTitle>Remediation approval</CardTitle>
              <CardDescription>
                Destructive actions are single-use and must be approved by a different administrator.
              </CardDescription>
            </div>
            <Badge
              variant={
                approvalActive
                  ? "success"
                  : request.approval_status === "REJECTED"
                    ? "danger"
                    : "warning"
              }
            >
              {request.approval_consumed_at
                ? "Consumed"
                : approvalExpired && request.approval_status === "APPROVED"
                  ? "Expired"
                  : request.approval_status
                    ? humanize(request.approval_status)
                    : "Pending"}
            </Badge>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2 text-[11px] text-muted-foreground sm:grid-cols-3">
              <span>
                Approved by:{" "}
                <span className="font-mono text-foreground/80">
                  {request.approved_by ?? "—"}
                </span>
              </span>
              <span>
                Expires:{" "}
                <span className="text-foreground/80">
                  {request.approval_expires_at ? formatDate(request.approval_expires_at) : "—"}
                </span>
              </span>
              <span>
                Consumed:{" "}
                <span className="text-foreground/80">
                  {request.approval_consumed_at ? formatRelative(request.approval_consumed_at) : "—"}
                </span>
              </span>
            </div>
            {latestApproval?.reason ? (
              <p className="rounded-xl border border-border/60 bg-background/30 px-3 py-2 text-[11px] text-muted-foreground">
                {latestApproval.reason}
              </p>
            ) : null}
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="Decision note (optional, recorded in the audit trail)"
              rows={2}
              className="w-full rounded-xl border border-border/80 bg-background/60 px-3 py-2 text-xs outline-none focus:border-primary/50"
            />
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-[10px] text-muted-foreground">
                Administrator role required. Approval expires after the configured TTL.
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void decideApproval("REJECTED")}
                  disabled={decide.isPending}
                >
                  <XCircle className="h-3.5 w-3.5" /> Reject
                </Button>
                <Button
                  variant="brand"
                  size="sm"
                  onClick={() => void decideApproval("APPROVED")}
                  disabled={decide.isPending}
                >
                  {decide.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  )}
                  Approve remediation
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {request.status === "NOT_APPLICABLE" ? (
        <Card className="border-border/70">
          <CardContent className="flex flex-col items-start gap-4 p-6 sm:flex-row">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
              <ShieldX className="h-5 w-5" />
            </span>
            <div className="flex-1">
              <h2 className="font-display text-lg font-semibold">This request does not authorize deletion</h2>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
                The request was classified as a non-deletion intent. ErasureProof did not remove,
                redact, or anonymize any data. No remediation plan is required.
              </p>
            </div>
            <Badge variant="muted">No steps</Badge>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Findings", value: counts.FINDING ?? 0, detail: "records still present", tone: "danger" },
          { label: "Remediations", value: counts.REMEDIATION ?? 0, detail: plansWord(counts.REMEDIATION ?? 0), tone: "warning" },
          { label: "Verified", value: passed, detail: `${verified.length} checks total`, tone: verified.length && passed === verified.length ? "success" : "default" },
          { label: "Evidence", value: shownEvidence.length, detail: "fingerprinted artifacts", tone: "default" },
        ].map((item, index) => (
          <MotionDiv key={item.label} delay={index * 0.05}>
            <Card>
              <CardContent className="p-5">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">{item.label}</p>
                <p className={cn(
                  "mt-3 font-display text-3xl font-bold",
                  item.tone === "danger" && "text-rose-300",
                  item.tone === "warning" && "text-amber-300",
                  item.tone === "success" && "text-emerald-300",
                )}>{item.value}</p>
                <p className="mt-1 text-[11px] text-muted-foreground">{item.detail}</p>
              </CardContent>
            </Card>
          </MotionDiv>
        ))}
      </div>

      {needsRun && isApplicable ? (
        <Card className="overflow-hidden border-primary/20 bg-gradient-to-br from-primary/8 to-violet-500/5">
          <CardContent className="flex flex-col items-start gap-5 p-6 sm:flex-row sm:items-center sm:p-8">
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-brand text-white shadow-lg shadow-primary/20">
              <Sparkles className="h-5 w-5" />
            </span>
            <div className="flex-1">
              <h2 className="font-display text-lg font-semibold">Ready to reconstruct the truth</h2>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
                Resolve historic identifiers, inspect every connector and evidence artifact, apply
                policy, then execute an ordered remediation plan with verification.
              </p>
            </div>
            <Button
              variant="brand"
              onClick={() => void startAudit()}
              disabled={run.isPending || (approvalRequired && !approvalActive)}
              title={
                approvalRequired && !approvalActive
                  ? "Administrator approval is required"
                  : undefined
              }
            >
              {run.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              {run.isPending ? "Auditing…" : "Start audit"}
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {run.isError ? (
        <div className="flex items-start gap-3 rounded-2xl border border-rose-400/20 bg-rose-400/5 p-4 text-sm text-rose-300">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          {run.error instanceof Error ? run.error.message : "The audit failed."}
        </div>
      ) : null}

      {isApplicable ? (
        <>
          <Tabs value={tab} onChange={setTab} items={tabs} />

          {tab === "plan" ? (
            <div className="space-y-4">
              {phaseOrder.map((phase) => {
                const meta = phaseMeta[phase];
                const Icon = meta.icon;
                const phaseSteps = steps.filter((step) => step.phase === phase);
                if (!phaseSteps.length) return null;
                return (
                  <Card key={phase} className={cn("overflow-hidden", meta.className)}>
                    <CardHeader className="flex-row items-center gap-3">
                      <span className={cn("flex h-9 w-9 items-center justify-center rounded-xl border border-current/20 bg-background/30", meta.text)}>
                        <Icon className="h-4 w-4" />
                      </span>
                      <div className="flex-1">
                        <CardTitle>{meta.label}</CardTitle>
                        <CardDescription>{meta.description}</CardDescription>
                      </div>
                      <span className="font-mono text-xs text-muted-foreground">{phaseSteps.length} steps</span>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      {phaseSteps.map((step, index) => (
                        <StepRow key={step.step_no} step={step} index={index} />
                      ))}
                    </CardContent>
                  </Card>
                );
              })}
              {!steps.length ? (
                <Card>
                  <CardContent className="py-14 text-center">
                    <FileSearch className="mx-auto mb-3 h-7 w-7 text-muted-foreground" />
                    <p className="font-medium">No plan steps yet</p>
                    <p className="mt-1 text-sm text-muted-foreground">Run the audit to build a remediation plan.</p>
                  </CardContent>
                </Card>
              ) : null}
            </div>
          ) : null}

          {tab === "graph" ? (
            <Card>
              <CardHeader>
                <CardTitle>Plan dependency graph</CardTitle>
                <CardDescription>Flows and restores are disabled before dependent records are changed.</CardDescription>
              </CardHeader>
              <CardContent>
                {graph ? <PlanGraph graph={graph} /> : (
                  <div className="flex min-h-48 items-center justify-center rounded-2xl border border-dashed border-border/70 text-sm text-muted-foreground">
                    Run the audit to generate the dependency graph.
                  </div>
                )}
              </CardContent>
            </Card>
          ) : null}

          {tab === "evidence" ? (
            <Card>
              <CardHeader>
                <CardTitle>Evidence artifacts</CardTitle>
                <CardDescription>Findings and checks cite participant-visible evidence IDs.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {shownEvidence.map((item) => (
                  <div key={item.evidence_id} className="flex flex-col gap-3 rounded-2xl border border-border/60 bg-background/30 p-3.5 sm:flex-row sm:items-center">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                      <Fingerprint className="h-4 w-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-[11px] text-primary">{item.evidence_id}</span>
                        <Badge variant="muted">{item.source}</Badge>
                      </div>
                      <p className="mt-1 truncate font-mono text-[10px] text-muted-foreground">
                        sha256:{item.sha256}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[10px] text-muted-foreground">{formatRelative(item.captured_at)}</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          verify.mutate(item.evidence_id, {
                            onSuccess: (response) =>
                              response.valid
                                ? toast.success("Evidence object matches its fingerprint")
                                : toast.error("Evidence fingerprint mismatch"),
                          })
                        }
                        disabled={verify.isPending && verify.variables === item.evidence_id}
                      >
                        {verify.isPending && verify.variables === item.evidence_id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <ShieldCheck className="h-3.5 w-3.5" />
                        )}
                        Verify
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
                ))}
                {!shownEvidence.length ? (
                  <p className="py-10 text-center text-sm text-muted-foreground">
                    No evidence is linked to this request yet.
                  </p>
                ) : null}
              </CardContent>
            </Card>
          ) : null}

          {tab === "proof" ? (
            <div className="grid gap-4 xl:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Verification results</CardTitle>
                  <CardDescription>Post-remediation state at the audit snapshot.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  {verified.map((item, index) => (
                    <VerificationRow key={`${item.operation}-${index}`} result={item} />
                  ))}
                  {!verified.length ? (
                    <div className="flex min-h-40 flex-col items-center justify-center rounded-2xl border border-dashed border-border/70 text-center">
                      <Clock4 className="mb-2 h-6 w-6 text-muted-foreground" />
                      <p className="text-sm text-muted-foreground">No verification checks have run.</p>
                    </div>
                  ) : null}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Signed attestation</CardTitle>
                  <CardDescription>A portable proof binding status, plan, evidence, and ledger head.</CardDescription>
                </CardHeader>
                <CardContent>
                  {result?.attestation ? (
                    <div className="space-y-3">
                      <div className="flex items-center gap-3 rounded-2xl border border-emerald-400/20 bg-emerald-400/5 p-4">
                        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-400/10 text-emerald-300">
                          <ShieldCheck className="h-5 w-5" />
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-semibold">{humanize(result.attestation.status)}</p>
                          <p className="truncate font-mono text-[10px] text-muted-foreground">
                            {result.attestation.signature}
                          </p>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => copy(JSON.stringify(result.attestation, null, 2), "Attestation")}
                        >
                          <Copy className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                      <pre className="max-h-72 overflow-auto rounded-2xl border border-border/60 bg-[#071017] p-4 font-mono text-[10px] leading-5 text-slate-300">
                        {JSON.stringify(result.attestation.payload, null, 2)}
                      </pre>
                    </div>
                  ) : (
                    <div className="flex min-h-40 flex-col items-center justify-center rounded-2xl border border-dashed border-border/70 text-center">
                      <FileCheck2 className="mb-2 h-6 w-6 text-muted-foreground" />
                      <p className="text-sm text-muted-foreground">No attestation issued yet.</p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {result?.actions?.length ? (
                <Card className="xl:col-span-2">
                  <CardHeader>
                    <CardTitle>Execution log</CardTitle>
                    <CardDescription>Connector actions recorded during this run.</CardDescription>
                  </CardHeader>
                  <CardContent className="grid gap-2 sm:grid-cols-2">
                    {result.actions.map((action, index) => (
                      <div key={`${action.operation}-${index}`} className="flex items-center gap-3 rounded-xl border border-border/60 p-3 text-xs">
                        {action.success ? (
                          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-300" />
                        ) : (
                          <XCircle className="h-4 w-4 shrink-0 text-rose-300" />
                        )}
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-medium">{humanize(action.operation)}</p>
                          <p className="truncate font-mono text-[10px] text-muted-foreground">
                            {action.system_id}/{action.resource_id}
                          </p>
                        </div>
                        <span className="text-[10px] text-muted-foreground">{action.supported ? "supported" : "unsupported"}</span>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              ) : null}

              {result?.errors?.length ? (
                <Card className="border-rose-400/20 xl:col-span-2">
                  <CardHeader>
                    <CardTitle>Run errors</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-1.5 text-xs text-rose-300">
                    {result.errors.map((item) => <p key={item}>{item}</p>)}
                  </CardContent>
                </Card>
              ) : null}
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

function plansWord(value: number) {
  return value === 1 ? "ordered action" : "ordered actions";
}
