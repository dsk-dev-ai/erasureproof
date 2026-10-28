import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Boxes,
  Cable,
  Code2,
  FileCheck2,
  Fingerprint,
  Gauge,
  Globe2,
  LifeBuoy,
  LockKeyhole,
  Rocket,
  Scale,
  ShieldCheck,
} from "lucide-react";
import overviewMd from "@/content/docs/overview.md?raw";
import quickstartMd from "@/content/docs/quickstart.md?raw";
import architectureMd from "@/content/docs/architecture.md?raw";
import lifecycleMd from "@/content/docs/request-lifecycle.md?raw";
import evidenceMd from "@/content/docs/evidence.md?raw";
import policyMd from "@/content/docs/policy.md?raw";
import connectorsMd from "@/content/docs/connectors.md?raw";
import apiMd from "@/content/docs/api.md?raw";
import exposureMd from "@/content/docs/exposure.md?raw";
import deploymentMd from "@/content/docs/deployment.md?raw";
import securityMd from "@/content/docs/security.md?raw";
import evaluationMd from "@/content/docs/evaluation.md?raw";
import { cn } from "@/lib/utils";

const docs = [
  { slug: "overview", title: "Overview", category: "Start here", icon: BookOpen, content: overviewMd, description: "What ErasureProof is and what “complete” actually means." },
  { slug: "quickstart", title: "Quickstart", category: "Start here", icon: Rocket, content: quickstartMd, description: "Run the backend, demo, CLI, and web console." },
  { slug: "architecture", title: "Architecture", category: "Concepts", icon: Boxes, content: architectureMd, description: "The stages between a request and a signed proof." },
  { slug: "request-lifecycle", title: "Request lifecycle", category: "Concepts", icon: FileCheck2, content: lifecycleMd, description: "Intent, identity, discovery, planning, execution, verification." },
  { slug: "evidence", title: "Evidence & ledger", category: "Concepts", icon: Fingerprint, content: evidenceMd, description: "Content addressing, hash chains, and attestations." },
  { slug: "policy", title: "Policy engine", category: "Concepts", icon: Scale, content: policyMd, description: "Delete, redact, anonymize, retain, or tombstone." },
  { slug: "connectors", title: "Connectors", category: "Operations", icon: Cable, content: connectorsMd, description: "Connect SQL, files, archives, objects, and control systems." },
  { slug: "deployment", title: "Deployment", category: "Operations", icon: Globe2, content: deploymentMd, description: "Docker, configuration, persistence, and proxy setup." },
  { slug: "api", title: "API reference", category: "Developers", icon: Code2, content: apiMd, description: "Endpoints for requests, evidence, ledger, and exposure." },
  { slug: "exposure", title: "Exposure intelligence", category: "Developers", icon: LockKeyhole, content: exposureMd, description: "Passive public-source scanning and its guardrails." },
  { slug: "security", title: "Security & limits", category: "Trust", icon: ShieldCheck, content: securityMd, description: "Trust boundaries, safe defaults, and known limitations." },
  { slug: "evaluation", title: "Evaluation", category: "Trust", icon: Gauge, content: evaluationMd, description: "How correctness and plan quality are measured." },
];

const categories = ["Start here", "Concepts", "Operations", "Developers", "Trust"];

function slugify(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");
}

export function DocsPage() {
  const { slug } = useParams();
  const current = docs.find((doc) => doc.slug === slug) ?? docs[0];
  const index = docs.findIndex((doc) => doc.slug === current.slug);
  const previous = docs[index - 1];
  const next = docs[index + 1];

  const headings = useMemo(
    () =>
      current.content
        .split("\n")
        .filter((line) => /^## /.test(line))
        .map((line) => line.replace(/^## /, ""))
        .map((title) => ({ title, id: slugify(title) })),
    [current.content],
  );

  const ContentIcon = current.icon;

  return (
    <div className="grid gap-8 xl:grid-cols-[220px_minmax(0,1fr)_200px]">
      <aside className="hidden xl:block">
        <div className="sticky top-24">
          <p className="mb-3 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
            <LifeBuoy className="h-3.5 w-3.5" /> Documentation
          </p>
          <nav className="space-y-5">
            {categories.map((category) => (
              <div key={category}>
                <p className="mb-1.5 px-2 text-[9px] font-bold uppercase tracking-[0.16em] text-muted-foreground/65">
                  {category}
                </p>
                <div className="space-y-0.5">
                  {docs.filter((doc) => doc.category === category).map((doc) => {
                    const Icon = doc.icon;
                    const active = doc.slug === current.slug;
                    return (
                      <Link
                        key={doc.slug}
                        to={`/app/docs/${doc.slug}`}
                        className={cn(
                          "flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs transition",
                          active
                            ? "bg-primary/10 font-semibold text-primary"
                            : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
                        )}
                      >
                        <Icon className="h-3.5 w-3.5 shrink-0" />
                        {doc.title}
                      </Link>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>
          <div className="mt-6 rounded-xl border border-border/60 bg-card/40 p-3">
            <p className="text-[11px] font-semibold">Need the raw API?</p>
            <a href="/docs" target="_blank" rel="noreferrer" className="mt-1 flex items-center gap-1 text-[10px] text-primary hover:underline">
              OpenAPI reference <ArrowRight className="h-2.5 w-2.5" />
            </a>
          </div>
        </div>
      </aside>

      <div className="min-w-0">
        <div className="mb-6 xl:hidden">
          <label htmlFor="docs-mobile" className="mb-1.5 block text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            Documentation
          </label>
          <select
            id="docs-mobile"
            value={current.slug}
            onChange={(event) => {
              window.location.assign(`/app/docs/${event.target.value}`);
            }}
            className="h-10 w-full rounded-xl border border-border/80 bg-card px-3 text-sm"
          >
            {categories.map((category) => (
              <optgroup key={category} label={category}>
                {docs.filter((doc) => doc.category === category).map((doc) => (
                  <option key={doc.slug} value={doc.slug}>{doc.title}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>

        <article className="surface rounded-3xl p-6 sm:p-9">
          <div className="mb-7 flex items-start gap-4 border-b border-border/60 pb-6">
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-brand text-white shadow-lg shadow-primary/20">
              <ContentIcon className="h-5 w-5" />
            </span>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-primary">
                {current.category} · v1.1
              </p>
              <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-3xl">{current.title}</h1>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{current.description}</p>
            </div>
          </div>

          <div className="prose-erasure max-w-none">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({ children }) => (
                  <h1 className="mb-4 mt-2 font-display text-2xl font-bold text-foreground">{children}</h1>
                ),
                h2: ({ children }) => {
                  const text = String(children);
                  return (
                    <h2 id={slugify(text)} className="scroll-mt-24 border-t border-border/50 pt-7 font-display text-xl font-semibold text-foreground">
                      {children}
                    </h2>
                  );
                },
                a: ({ href, children }) =>
                  href?.startsWith("/") ? (
                    <Link to={href}>{children}</Link>
                  ) : (
                    <a href={href} target="_blank" rel="noreferrer">{children}</a>
                  ),
              }}
            >
              {current.content}
            </ReactMarkdown>
          </div>

          <div className="mt-10 flex flex-col gap-2 border-t border-border/60 pt-5 sm:flex-row sm:items-center sm:justify-between">
            {previous ? (
              <Link to={`/app/docs/${previous.slug}`} className="group flex items-center gap-2 rounded-xl px-2 py-1.5 text-xs text-muted-foreground transition hover:text-foreground">
                <ArrowLeft className="h-3.5 w-3.5" />
                <span>
                  <span className="block text-[9px] uppercase tracking-widest text-muted-foreground/60">Previous</span>
                  {previous.title}
                </span>
              </Link>
            ) : <span />}
            {next ? (
              <Link to={`/app/docs/${next.slug}`} className="group flex items-center gap-2 rounded-xl px-2 py-1.5 text-right text-xs text-muted-foreground transition hover:text-foreground">
                <span>
                  <span className="block text-[9px] uppercase tracking-widest text-muted-foreground/60">Next</span>
                  {next.title}
                </span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            ) : null}
          </div>
        </article>
      </div>

      <aside className="hidden xl:block">
        <div className="sticky top-24">
          <p className="mb-3 text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground">On this page</p>
          <nav className="space-y-1 border-l border-border/60">
            {headings.map((heading) => (
              <a
                key={heading.id}
                href={`#${heading.id}`}
                className="-ml-px block border-l border-transparent py-1 pl-3 text-[11px] leading-4 text-muted-foreground transition hover:border-primary/50 hover:text-foreground"
              >
                {heading.title}
              </a>
            ))}
          </nav>
          <div className="mt-6 rounded-xl border border-emerald-400/15 bg-emerald-400/[0.035] p-3">
            <div className="flex items-center gap-1.5 text-[10px] font-semibold text-emerald-300">
              <ShieldCheck className="h-3 w-3" /> Deterministic by design
            </div>
            <p className="mt-1.5 text-[10px] leading-4 text-muted-foreground">
              Documentation is versioned with the code and shipped inside the console.
            </p>
          </div>
        </div>
      </aside>
    </div>
  );
}
