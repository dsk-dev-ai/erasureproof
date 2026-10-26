import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  CircleSlash2,
  FileSearch,
  Filter,
  Plus,
  Search,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs } from "@/components/ui/tabs";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { StatusBadge } from "@/components/requests/status-badge";
import { NewRequestDialog } from "@/components/requests/new-request-dialog";
import { useRequests, useSeedDemo } from "@/hooks/use-api";
import { useTenant } from "@/components/tenant-provider";
import { formatDate, humanize, truncate } from "@/lib/utils";

const filters = [
  { value: "ALL", label: "All" },
  { value: "COMPLETE", label: "Complete" },
  { value: "INCOMPLETE", label: "Incomplete" },
  { value: "NOT_APPLICABLE", label: "Not applicable" },
  { value: "PENDING", label: "Pending" },
];

export function RequestsPage() {
  const { tenant, tenantId, setTenantId } = useTenant();
  const { data = [], isLoading, isError, error, refetch } = useRequests(tenantId);
  const seed = useSeedDemo();
  const [status, setStatus] = useState("ALL");
  const [query, setQuery] = useState("");
  const [jurisdiction, setJurisdiction] = useState("ALL");
  const [newOpen, setNewOpen] = useState(false);

  const jurisdictions = useMemo(
    () => [...new Set(data.map((request) => request.jurisdiction))].sort(),
    [data],
  );

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return data.filter((request) => {
      if (status !== "ALL" && request.status !== status) return false;
      if (jurisdiction !== "ALL" && request.jurisdiction !== jurisdiction) return false;
      if (!needle) return true;
      return (
        request.email.toLowerCase().includes(needle) ||
        request.id.toLowerCase().includes(needle) ||
        request.request_text.toLowerCase().includes(needle)
      );
    });
  }, [data, jurisdiction, query, status]);

  const counts = useMemo(
    () =>
      filters.reduce<Record<string, number>>((accumulator, filter) => {
        accumulator[filter.value] =
          filter.value === "ALL"
            ? data.length
            : data.filter((request) => request.status === filter.value).length;
        return accumulator;
      }, {}),
    [data],
  );

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

  return (
    <>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Requests"
          title="Deletion audit queue"
          description={`${tenant?.name ?? "All workspaces"} · classify intent, reconstruct state, and verify every resource in scope.`}
          actions={
            <Button variant="brand" onClick={() => setNewOpen(true)}>
              <Plus className="h-4 w-4" /> New request
            </Button>
          }
        />

        <Card className="p-3">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <Tabs
              value={status}
              onChange={setStatus}
              items={filters.map((filter) => ({
                ...filter,
                count: counts[filter.value],
              }))}
            />
            <div className="flex flex-1 flex-col gap-2 sm:flex-row lg:justify-end">
              <div className="relative sm:w-72">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search email, ID, or text…"
                  className="pl-9"
                />
              </div>
              <div className="relative sm:w-40">
                <Filter className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Select
                  value={jurisdiction}
                  onChange={(event) => setJurisdiction(event.target.value)}
                  className="pl-9"
                >
                  <option value="ALL">All regions</option>
                  {jurisdictions.map((item) => (
                    <option key={item} value={item}>{item}</option>
                  ))}
                </Select>
              </div>
            </div>
          </div>
        </Card>

        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} className="h-[74px]" />
            ))}
          </div>
        ) : isError ? (
          <ErrorState
            message={error instanceof Error ? error.message : undefined}
            onRetry={() => void refetch()}
          />
        ) : !data.length ? (
          <EmptyState
            icon={<Sparkles className="h-6 w-6" />}
            title="No requests in this workspace"
            description="Load the demo workspace to explore a complete erasure, an incomplete audit, and a non-deletion request — or create your own."
            action={
              <div className="flex flex-wrap justify-center gap-2">
                <Button variant="brand" onClick={() => void loadDemo()} disabled={seed.isPending}>
                  {seed.isPending ? "Building…" : "Load demo workspace"}
                </Button>
                <Button variant="outline" onClick={() => setNewOpen(true)}>
                  <Plus className="h-4 w-4" /> New request
                </Button>
              </div>
            }
          />
        ) : !filtered.length ? (
          <EmptyState
            icon={<CircleSlash2 className="h-6 w-6" />}
            title="No requests match these filters"
            description="Clear the search or choose a different status to see more audit records."
            action={
              <Button
                variant="outline"
                onClick={() => {
                  setStatus("ALL");
                  setQuery("");
                  setJurisdiction("ALL");
                }}
              >
                Clear filters
              </Button>
            }
          />
        ) : (
          <Card className="overflow-hidden">
            <div className="hidden grid-cols-[1.4fr_0.8fr_0.7fr_0.9fr_0.8fr_32px] gap-4 border-b border-border/60 px-5 py-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground lg:grid">
              <span>Subject</span>
              <span>Status</span>
              <span>Region</span>
              <span>Requested</span>
              <span>Audit at</span>
              <span />
            </div>
            <div className="divide-y divide-border/50">
              {filtered.map((request) => (
                <Link
                  key={request.id}
                  to={`/app/requests/${request.id}`}
                  className="group block px-4 py-3.5 transition hover:bg-accent/35 sm:px-5"
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center lg:grid lg:grid-cols-[1.4fr_0.8fr_0.7fr_0.9fr_0.8fr_32px] lg:gap-4">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{request.email}</p>
                      <div className="mt-0.5 flex items-center gap-2">
                        <span className="font-mono text-[10px] text-muted-foreground">{request.id}</span>
                        <span className="hidden max-w-xs truncate text-[10px] text-muted-foreground sm:inline">
                          · {truncate(request.request_text.replaceAll("\n", " "), 54)}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 lg:block">
                      <StatusBadge status={request.status} />
                    </div>
                    <span className="hidden font-mono text-xs text-muted-foreground lg:block">
                      {request.jurisdiction}
                    </span>
                    <span className="hidden text-xs text-muted-foreground lg:block">
                      {formatDate(request.requested_at)}
                    </span>
                    <span className="hidden text-xs text-muted-foreground lg:block">
                      {formatDate(request.audit_at)}
                    </span>
                    <span className="hidden h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition group-hover:bg-primary/10 group-hover:text-primary lg:flex">
                      <ArrowUpRight className="h-4 w-4" />
                    </span>
                    <div className="flex items-center justify-between border-t border-border/40 pt-2 text-[11px] text-muted-foreground sm:border-0 sm:pt-0 lg:hidden">
                      <span>{request.jurisdiction} · {humanize(request.status)}</span>
                      <span>{formatDate(request.audit_at)}</span>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
            <div className="flex items-center justify-between border-t border-border/60 px-5 py-3 text-[11px] text-muted-foreground">
              <span>Showing {filtered.length} of {data.length} requests</span>
              <span className="flex items-center gap-1.5">
                <FileSearch className="h-3.5 w-3.5" /> Evidence-backed
              </span>
            </div>
          </Card>
        )}
      </div>
      <NewRequestDialog open={newOpen} onClose={() => setNewOpen(false)} />
    </>
  );
}
