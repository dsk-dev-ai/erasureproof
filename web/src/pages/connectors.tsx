import { useState } from "react";
import {
  Cable,
  CheckCircle2,
  Database,
  FileJson,
  FolderOpen,
  HardDrive,
  Plus,
  Sparkles,
  Trash2,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import {
  useConnectorTypes,
  useConnectors,
  useCreateConnector,
  useDeleteConnector,
  useSeedDemo,
} from "@/hooks/use-api";
import { useTenant } from "@/components/tenant-provider";
import { MotionDiv } from "@/components/motion/motion";
import { formatDate, humanize } from "@/lib/utils";

const configTemplates: Record<string, Record<string, unknown>> = {
  filesystem: {
    system_id: "filesystem",
    root: "/data/exports",
    default_category: "EXPORT",
    categories: { "backups/*": "BACKUP", "logs/*": "LOG" },
    ocr: true,
  },
  sql: {
    system_id: "analytics",
    url: "sqlite:///data/analytics.db",
    table: "events",
    id_column: "email",
    category: "ANALYTICS",
  },
  postgres: {
    system_id: "warehouse",
    dsn: "postgresql://user:password@localhost/warehouse",
    table: "events",
    id_column: "email",
  },
  control: {
    system_id: "workflow",
    category: "CONTROL",
  },
  s3: {
    system_id: "objects",
    bucket: "support-attachments",
    prefix: "tickets/",
  },
  local: {
    system_id: "objects",
    root: "/data/objects",
    bucket: "support-attachments",
  },
};

const typeIcon = (type: string) => {
  switch (type) {
    case "filesystem":
      return FolderOpen;
    case "sql":
    case "postgres":
      return Database;
    case "s3":
    case "local":
      return HardDrive;
    default:
      return FileJson;
  }
};

function CreateConnectorDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { tenantId } = useTenant();
  const { data: types } = useConnectorTypes();
  const create = useCreateConnector();
  const [name, setName] = useState("");
  const [type, setType] = useState("filesystem");
  const [config, setConfig] = useState(JSON.stringify(configTemplates.filesystem, null, 2));

  const changeType = (value: string) => {
    setType(value);
    setConfig(JSON.stringify(configTemplates[value] ?? { system_id: value }, null, 2));
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!tenantId) {
      toast.error("Load a workspace first");
      return;
    }
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(config) as Record<string, unknown>;
    } catch {
      toast.error("Connector configuration must be valid JSON");
      return;
    }
    try {
      await create.mutateAsync({
        tenant_id: tenantId,
        type,
        name: name.trim(),
        config: parsed,
        enabled: true,
      });
      toast.success("Connector connected");
      setName("");
      onClose();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not create connector");
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Connect a data source"
      description="Connectors are read at audit time. Destructive actions are executed only after a validated plan."
      className="max-w-2xl"
    >
      <form onSubmit={(event) => void submit(event)} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="connector-name">Display name</Label>
            <Input
              id="connector-name"
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Support attachments"
            />
          </div>
          <div>
            <Label htmlFor="connector-type">Connector type</Label>
            <Select id="connector-type" value={type} onChange={(event) => changeType(event.target.value)}>
              {(types?.types ?? ["filesystem", "sql", "postgres", "control", "s3", "local"]).map((item) => (
                <option key={item} value={item}>{humanize(item)}</option>
              ))}
            </Select>
          </div>
        </div>
        <div>
          <Label htmlFor="connector-config">Configuration JSON</Label>
          <Textarea
            id="connector-config"
            value={config}
            onChange={(event) => setConfig(event.target.value)}
            className="min-h-56 font-mono text-xs leading-5"
            spellCheck={false}
          />
        </div>
        <div className="rounded-xl border border-amber-400/20 bg-amber-400/5 px-3 py-2.5 text-[11px] leading-5 text-amber-200/80">
          Credentials should come from your runtime environment. Do not paste production secrets into the console.
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="brand" disabled={create.isPending}>
            {create.isPending ? "Connecting…" : "Connect source"}
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

export function ConnectorsPage() {
  const { tenant, tenantId, setTenantId } = useTenant();
  const { data = [], isLoading, isError, error, refetch } = useConnectors(tenantId);
  const seed = useSeedDemo();
  const remove = useDeleteConnector();
  const [open, setOpen] = useState(false);

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

  const disconnect = async (id: string, name: string) => {
    if (!window.confirm(`Disconnect “${name}”? Existing evidence remains verifiable.`)) return;
    try {
      await remove.mutateAsync(id);
      toast.success("Connector removed");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not remove connector");
    }
  };

  return (
    <>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Integrations"
          title="Connectors"
          description={`${tenant?.name ?? "All workspaces"} · Sources read during discovery, remediation, and verification.`}
          actions={
            <Button variant="brand" onClick={() => setOpen(true)}>
              <Plus className="h-4 w-4" /> Connect source
            </Button>
          }
        />

        {isLoading ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-52" />)}
          </div>
        ) : isError ? (
          <ErrorState
            message={error instanceof Error ? error.message : undefined}
            onRetry={() => void refetch()}
          />
        ) : !data.length ? (
          <EmptyState
            icon={<Cable className="h-6 w-6" />}
            title="No connectors configured"
            description="Load the demo workspace to inspect control, warehouse, archive, and object-store connectors."
            action={
              <div className="flex flex-wrap justify-center gap-2">
                <Button variant="brand" onClick={() => void loadDemo()} disabled={seed.isPending}>
                  <Sparkles className="h-4 w-4" /> {seed.isPending ? "Building…" : "Load demo workspace"}
                </Button>
                <Button variant="outline" onClick={() => setOpen(true)}>
                  <Plus className="h-4 w-4" /> Connect source
                </Button>
              </div>
            }
          />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {data.map((connector, index) => {
              const Icon = typeIcon(connector.type);
              const system = String(connector.config.system_id ?? connector.name);
              return (
                <MotionDiv key={connector.id} delay={Math.min(index * 0.04, 0.24)}>
                  <Card className="group h-full transition hover:border-primary/30">
                    <CardHeader className="flex-row items-start justify-between">
                      <div className="flex items-center gap-3">
                        <span className="flex h-11 w-11 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10 text-primary">
                          <Icon className="h-5 w-5" />
                        </span>
                        <div>
                          <CardTitle>{connector.name}</CardTitle>
                          <CardDescription className="font-mono text-[10px]">{connector.id}</CardDescription>
                        </div>
                      </div>
                      <Badge variant={connector.enabled ? "success" : "muted"} dot>
                        {connector.enabled ? "Enabled" : "Paused"}
                      </Badge>
                    </CardHeader>
                    <CardContent>
                      <div className="flex flex-wrap gap-2">
                        <span className="rounded-lg border border-border/70 bg-muted/35 px-2 py-1 font-mono text-[10px] text-muted-foreground">
                          {humanize(connector.type)}
                        </span>
                        <span className="rounded-lg border border-border/70 bg-muted/35 px-2 py-1 font-mono text-[10px] text-muted-foreground">
                          {system}
                        </span>
                      </div>
                      <pre className="mt-4 max-h-28 overflow-hidden rounded-xl border border-border/60 bg-background/45 p-3 font-mono text-[10px] leading-5 text-muted-foreground">
                        {JSON.stringify(connector.config, null, 2)}
                      </pre>
                      <div className="mt-4 flex items-center justify-between border-t border-border/50 pt-3">
                        <span className="text-[10px] text-muted-foreground">
                          Added {formatDate(connector.created_at)}
                        </span>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => void disconnect(connector.id, connector.name)}
                          disabled={remove.isPending && remove.variables === connector.id}
                          className="text-muted-foreground hover:text-destructive"
                          aria-label={`Remove ${connector.name}`}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </MotionDiv>
              );
            })}
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-3">
          {[
            { icon: CheckCircle2, title: "Read-only discovery", body: "Connectors can enumerate and inspect resources without mutating them." },
            { icon: XCircle, title: "Destructive actions gated", body: "Delete and redact operations run only through a validated plan." },
            { icon: Database, title: "Evidence captured", body: "Every discovered artifact is fingerprinted and written to local storage." },
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
      <CreateConnectorDialog open={open} onClose={() => setOpen(false)} />
    </>
  );
}
