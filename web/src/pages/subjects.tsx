import { useMemo, useState } from "react";
import {
  AtSign,
  CalendarDays,
  Fingerprint,
  Mail,
  Phone,
  Search,
  Sparkles,
  UserRound,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { useSeedDemo, useSubjects } from "@/hooks/use-api";
import { useTenant } from "@/components/tenant-provider";
import { MotionDiv } from "@/components/motion/motion";
import { formatDate, humanize } from "@/lib/utils";

const identifierIcon = (type: string) => {
  switch (type.toUpperCase()) {
    case "EMAIL":
      return Mail;
    case "PHONE":
      return Phone;
    case "USERNAME":
      return AtSign;
    case "EMAIL_HASH":
      return Fingerprint;
    default:
      return UserRound;
  }
};

export function SubjectsPage() {
  const { tenant, tenantId, setTenantId } = useTenant();
  const { data = [], isLoading, isError, error, refetch } = useSubjects(tenantId);
  const seed = useSeedDemo();
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return data;
    return data.filter(
      (subject) =>
        subject.id.toLowerCase().includes(needle) ||
        subject.user_id.toLowerCase().includes(needle) ||
        subject.identifiers.some((identifier) => identifier.value.toLowerCase().includes(needle)),
    );
  }, [data, query]);

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
    <div className="space-y-6">
      <PageHeader
        eyebrow="Identity graph"
        title="Subjects"
        description={`${tenant?.name ?? "All workspaces"} · Current and historic identifiers resolved into a single, stable subject reference.`}
        actions={
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search identity…"
              className="w-full pl-9 sm:w-64"
            />
          </div>
        }
      />

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-[230px]" />)}
        </div>
      ) : isError ? (
        <ErrorState
          message={error instanceof Error ? error.message : undefined}
          onRetry={() => void refetch()}
        />
      ) : !data.length ? (
        <EmptyState
          icon={<Sparkles className="h-6 w-6" />}
          title="No subjects discovered yet"
          description="Load the demo workspace to see how current and historic identifiers resolve into stable subject references."
          action={
            <Button variant="brand" onClick={() => void loadDemo()} disabled={seed.isPending}>
              {seed.isPending ? "Building…" : "Load demo workspace"}
            </Button>
          }
        />
      ) : !filtered.length ? (
        <EmptyState
          icon={<Search className="h-6 w-6" />}
          title="No matching identities"
          description="Try a different email, phone, username, or internal subject ID."
          action={<Button variant="outline" onClick={() => setQuery("")}>Clear search</Button>}
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((subject, index) => {
            const emails = subject.identifiers.filter((item) => item.type.toUpperCase() === "EMAIL");
            const phones = subject.identifiers.filter((item) => item.type.toUpperCase() === "PHONE");
            return (
              <MotionDiv key={subject.id} delay={Math.min(index * 0.04, 0.24)}>
                <Card className="group h-full overflow-hidden transition hover:border-primary/30">
                  <CardContent className="p-5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/20 to-violet-500/15 font-display text-base font-bold text-primary">
                          {(emails[0]?.value?.[0] ?? "S").toUpperCase()}
                        </span>
                        <div>
                          <p className="text-sm font-semibold">{emails[0]?.value ?? subject.user_id}</p>
                          <p className="font-mono text-[10px] text-muted-foreground">{subject.user_id}</p>
                        </div>
                      </div>
                      <Badge variant="muted">{subject.identifiers.length}</Badge>
                    </div>

                    <div className="mt-5 flex flex-wrap gap-1.5">
                      {subject.identifiers.slice(0, 8).map((identifier, identifierIndex) => {
                        const Icon = identifierIcon(identifier.type);
                        return (
                          <span
                            key={`${identifier.type}-${identifier.value}-${identifierIndex}`}
                            className="inline-flex max-w-full items-center gap-1.5 rounded-lg border border-border/70 bg-muted/35 px-2 py-1 text-[10px] text-muted-foreground"
                            title={`${humanize(identifier.type)} · ${identifier.source}`}
                          >
                            <Icon className="h-2.5 w-2.5 shrink-0" />
                            <span className="truncate">{identifier.value}</span>
                          </span>
                        );
                      })}
                      {subject.identifiers.length > 8 ? (
                        <span className="rounded-lg border border-border/70 px-2 py-1 text-[10px] text-muted-foreground">
                          +{subject.identifiers.length - 8}
                        </span>
                      ) : null}
                    </div>

                    <div className="mt-5 grid grid-cols-2 gap-2 border-t border-border/50 pt-4 text-[10px]">
                      <div>
                        <p className="uppercase tracking-wider text-muted-foreground">Historic emails</p>
                        <p className="mt-1 font-mono text-foreground/80">{Math.max(0, emails.length - 1)}</p>
                      </div>
                      <div>
                        <p className="uppercase tracking-wider text-muted-foreground">Phones</p>
                        <p className="mt-1 font-mono text-foreground/80">{phones.length}</p>
                      </div>
                      <div className="col-span-2 flex items-center gap-1.5 text-muted-foreground">
                        <CalendarDays className="h-3 w-3" /> Resolved {formatDate(subject.created_at)}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </MotionDiv>
            );
          })}
        </div>
      )}
    </div>
  );
}
