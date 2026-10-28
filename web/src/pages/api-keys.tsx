import { useState } from "react";
import { Copy, KeyRound, Loader2, Plus, RefreshCw, ShieldAlert, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useTenant } from "@/components/tenant-provider";
import {
  useApiKeys,
  useCreateApiKey,
  useRevokeApiKey,
  useRotateApiKey,
} from "@/hooks/use-api";
import { formatDate, timeAgo } from "@/lib/utils";
import type { ApiKey, ApiKeyCreated } from "@/lib/types";

function RevealKeyDialog({
  created,
  open,
  onClose,
}: {
  created: ApiKeyCreated | null;
  open: boolean;
  onClose: () => void;
}) {
  if (!created) return null;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(created.api_key);
      toast.success("API key copied");
    } catch {
      toast.error("Clipboard access was blocked");
    }
  };
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Copy your API key"
      description="This is the only time the full key will be shown."
    >
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <code className="min-w-0 flex-1 break-all rounded-xl border border-border/70 bg-background/70 px-3 py-2.5 font-mono text-[11px]">
            {created.api_key}
          </code>
          <Button variant="outline" size="icon-sm" onClick={() => void copy()}>
            <Copy className="h-3.5 w-3.5" />
          </Button>
        </div>
        <div className="rounded-2xl border border-amber-400/25 bg-amber-400/5 p-3.5 text-xs leading-5 text-muted-foreground">
          Store it in a secret manager now. ErasureProof stores only a SHA-256 hash and cannot
          recover the key later. Prefix: <span className="font-mono text-foreground">{created.key_prefix}</span>
        </div>
        <div className="flex justify-end">
          <Button variant="brand" onClick={onClose}>I have stored the key</Button>
        </div>
      </div>
    </Dialog>
  );
}

function StatusBadge({ row }: { row: ApiKey }) {
  if (row.revoked_at) return <Badge variant="muted">Revoked</Badge>;
  if (row.expires_at && new Date(row.expires_at).getTime() <= Date.now()) {
    return <Badge variant="warning">Expired</Badge>;
  }
  return <Badge variant="success" dot>Active</Badge>;
}

export function ApiKeysPage() {
  const { tenant, tenantId } = useTenant();
  const { data: keys = [], isLoading, error } = useApiKeys(tenantId);
  const create = useCreateApiKey();
  const rotate = useRotateApiKey();
  const revoke = useRevokeApiKey();
  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState("Production integration");
  const [role, setRole] = useState<"viewer" | "operator" | "admin">("operator");
  const [days, setDays] = useState("90");
  const [created, setCreated] = useState<ApiKeyCreated | null>(null);
  const [revealOpen, setRevealOpen] = useState(false);

  const submit = async () => {
    if (!tenantId) return;
    try {
      const result = await create.mutateAsync({
        tenant_id: tenantId,
        name: name.trim() || "API key",
        role,
        expires_in_days: days === "never" ? null : Number(days),
      });
      setCreated(result);
      setRevealOpen(true);
      setCreateOpen(false);
    } catch (failure) {
      toast.error(failure instanceof Error ? failure.message : "Could not create API key");
    }
  };

  const rotateKey = async (row: ApiKey) => {
    if (!window.confirm(`Rotate "${row.name}"? The current key will stop working immediately.`)) return;
    try {
      const result = await rotate.mutateAsync(row.id);
      setCreated(result);
      setRevealOpen(true);
    } catch (failure) {
      toast.error(failure instanceof Error ? failure.message : "Could not rotate API key");
    }
  };

  const revokeKey = async (row: ApiKey) => {
    if (!window.confirm(`Revoke "${row.name}"? This cannot be undone.`)) return;
    try {
      await revoke.mutateAsync(row.id);
      toast.success("API key revoked");
    } catch (failure) {
      toast.error(failure instanceof Error ? failure.message : "Could not revoke API key");
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Developer access"
        title="API keys"
        description="Tenant-scoped credentials for SDKs, CI pipelines, and customer integrations."
        actions={
          <Button variant="brand" onClick={() => setCreateOpen(true)} disabled={!tenantId || create.isPending}>
            <Plus className="h-4 w-4" /> Create key
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        {[
          ["Hashed at rest", "Only SHA-256 digests are stored; full keys are shown once."],
          ["Tenant scoped", "A key cannot read or mutate another workspace."],
          ["Expire or rotate", "Set a lifetime and replace keys without downtime."],
        ].map(([title, body]) => (
          <Card key={title}>
            <CardContent className="flex items-start gap-3 p-5">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <ShieldAlert className="h-4 w-4" />
              </span>
              <div>
                <p className="text-sm font-semibold">{title}</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">{body}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader className="flex-row items-start justify-between">
          <div>
            <CardTitle>{tenant?.name ?? "No workspace"} keys</CardTitle>
            <CardDescription>
              {keys.length} key{keys.length === 1 ? "" : "s"} · audit events are recorded for creation,
              rotation, and revocation.
            </CardDescription>
          </div>
          <Badge variant="outline">{tenantId ?? "no tenant"}</Badge>
        </CardHeader>
        <CardContent>
          {!tenantId ? (
            <p className="rounded-2xl border border-border/60 bg-background/30 p-6 text-sm text-muted-foreground">
              Open or create a workspace first.
            </p>
          ) : error ? (
            <p className="rounded-2xl border border-rose-400/20 bg-rose-400/5 p-4 text-sm text-rose-300">
              {error.message} — an administrator key is required to manage credentials.
            </p>
          ) : isLoading ? (
            <div className="flex items-center gap-3 p-6 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading keys…
            </div>
          ) : keys.length === 0 ? (
            <div className="rounded-2xl border border-border/60 bg-background/30 p-6">
              <p className="text-sm font-semibold">No API keys yet</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Create a viewer key for dashboards, an operator key for audits, or an admin key for
                workspace administration.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-xs">
                <thead>
                  <tr className="text-[10px] uppercase tracking-widest text-muted-foreground">
                    <th className="px-3 py-2 font-medium">Name</th>
                    <th className="px-3 py-2 font-medium">Key</th>
                    <th className="px-3 py-2 font-medium">Role</th>
                    <th className="px-3 py-2 font-medium">Last used</th>
                    <th className="px-3 py-2 font-medium">Expires</th>
                    <th className="px-3 py-2 font-medium">Status</th>
                    <th className="px-3 py-2 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {keys.map((row) => (
                    <tr key={row.id} className="border-t border-border/50">
                      <td className="px-3 py-3">
                        <p className="font-medium text-foreground">{row.name}</p>
                        <p className="mt-0.5 text-[10px] text-muted-foreground">{row.subject}</p>
                      </td>
                      <td className="px-3 py-3 font-mono text-[10px] text-primary">{row.key_prefix}…</td>
                      <td className="px-3 py-3"><Badge variant="neutral">{row.role}</Badge></td>
                      <td className="px-3 py-3 text-muted-foreground">{timeAgo(row.last_used_at)}</td>
                      <td className="px-3 py-3 text-muted-foreground">{formatDate(row.expires_at)}</td>
                      <td className="px-3 py-3"><StatusBadge row={row} /></td>
                      <td className="px-3 py-3">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            title="Rotate key"
                            disabled={Boolean(row.revoked_at) || rotate.isPending}
                            onClick={() => void rotateKey(row)}
                          >
                            <RefreshCw className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            title="Revoke key"
                            disabled={Boolean(row.revoked_at) || revoke.isPending}
                            onClick={() => void revokeKey(row)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Create an API key"
        description="Choose the least privilege your integration needs."
      >
        <div className="space-y-4">
          <label className="block space-y-1.5">
            <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Name</span>
            <Input value={name} onChange={(event) => setName(event.target.value)} maxLength={100} />
          </label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block space-y-1.5">
              <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Role</span>
              <select
                value={role}
                onChange={(event) => setRole(event.target.value as "viewer" | "operator" | "admin")}
                className="h-10 w-full rounded-xl border border-border/80 bg-background/60 px-3 text-xs outline-none focus:border-primary/50"
              >
                <option value="viewer">Viewer — read-only</option>
                <option value="operator">Operator — audits and request runs</option>
                <option value="admin">Admin — keys and workspace settings</option>
              </select>
            </label>
            <label className="block space-y-1.5">
              <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Lifetime</span>
              <select
                value={days}
                onChange={(event) => setDays(event.target.value)}
                className="h-10 w-full rounded-xl border border-border/80 bg-background/60 px-3 text-xs outline-none focus:border-primary/50"
              >
                <option value="30">30 days</option>
                <option value="90">90 days</option>
                <option value="365">1 year</option>
                <option value="never">No expiry</option>
              </select>
            </label>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button variant="brand" onClick={() => void submit()} disabled={create.isPending}>
              {create.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
              Create key
            </Button>
          </div>
        </div>
      </Dialog>

      <RevealKeyDialog created={created} open={revealOpen} onClose={() => setRevealOpen(false)} />
    </div>
  );
}
