import { Check, Copy, ExternalLink, KeyRound, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import type { Sandbox } from "@/lib/types";

async function copy(value: string, label: string) {
  try {
    await navigator.clipboard.writeText(value);
    toast.success(`${label} copied`);
  } catch {
    toast.error("Clipboard access was blocked");
  }
}

export function SandboxDialog({
  sandbox,
  open,
  onClose,
}: {
  sandbox: Sandbox | null;
  open: boolean;
  onClose: () => void;
}) {
  if (!sandbox) return null;
  const base = typeof window !== "undefined" ? window.location.origin : "https://your-host";
  const curl = [
    `export ERASUREPROOF_API_KEY="${sandbox.api_key}"`,
    `export BASE_URL="${base}"`,
    "",
    `curl -s "$BASE_URL/v1/requests/${sandbox.sample_request_id}" \\`,
    `  -H "Authorization: Bearer $ERASUREPROOF_API_KEY"`,
    "",
    `curl -s -X POST "$BASE_URL/v1/requests/${sandbox.sample_request_id}/run?remediate=false" \\`,
    `  -H "Authorization: Bearer $ERASUREPROOF_API_KEY"`,
  ].join("\n");

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Your sandbox is ready"
      description="A seeded workspace, three connectors, and one audit-ready deletion request."
      className="max-w-2xl"
    >
      <div className="space-y-4">
        <div className="flex items-start gap-3 rounded-2xl border border-amber-400/25 bg-amber-400/5 p-3.5">
          <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-amber-300">
              API key · shown once
            </p>
            <div className="mt-2 flex items-center gap-2">
              <code className="min-w-0 flex-1 break-all rounded-xl border border-border/70 bg-background/70 px-3 py-2 font-mono text-[11px]">
                {sandbox.api_key}
              </code>
              <Button variant="outline" size="icon-sm" onClick={() => void copy(sandbox.api_key, "API key")}>
                <Copy className="h-3.5 w-3.5" />
              </Button>
            </div>
            <p className="mt-2 text-[11px] leading-5 text-muted-foreground">
              This key is an administrator for <span className="font-mono">{sandbox.tenant_id}</span> and
              expires {new Date(sandbox.expires_at).toLocaleDateString()}. Store it in a secret manager.
            </p>
          </div>
        </div>

        <div className="grid gap-2 sm:grid-cols-3">
          {[
            ["Workspace", sandbox.tenant_name],
            ["Sample subject", sandbox.sample_email],
            ["Request", sandbox.sample_request_id],
          ].map(([label, value]) => (
            <div key={label} className="rounded-xl border border-border/60 bg-card/50 p-3">
              <p className="text-[9px] uppercase tracking-widest text-muted-foreground">{label}</p>
              <p className="mt-1 truncate font-mono text-[11px]">{value}</p>
            </div>
          ))}
        </div>

        <div className="overflow-hidden rounded-2xl border border-border/70 bg-[#071017]">
          <div className="flex items-center justify-between border-b border-white/5 px-3 py-2 text-[10px] uppercase tracking-widest text-slate-500">
            <span>Quickstart</span>
            <button
              className="flex items-center gap-1.5 text-slate-300 hover:text-white"
              onClick={() => void copy(curl, "Quickstart")}
            >
              <Copy className="h-3 w-3" /> Copy
            </button>
          </div>
          <pre className="overflow-x-auto p-3 font-mono text-[10px] leading-5 text-slate-300">
            {curl}
          </pre>
        </div>

        <div className="flex items-start gap-3 rounded-2xl border border-primary/20 bg-primary/5 p-3.5">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
          <p className="text-xs leading-5 text-muted-foreground">
            The sandbox is isolated and contains only fictional data. Audit-only runs do not modify
            data; destructive remediation remains approval-gated in production.
          </p>
        </div>

        <div className="flex flex-wrap justify-end gap-2">
          <a href="/docs" target="_blank" rel="noreferrer">
            <Button variant="outline">
              OpenAPI <ExternalLink className="h-3.5 w-3.5" />
            </Button>
          </a>
          <Button variant="brand" onClick={onClose}>
            <Check className="h-3.5 w-3.5" /> Open sandbox console
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
