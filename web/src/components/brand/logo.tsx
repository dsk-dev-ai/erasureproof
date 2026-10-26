import { cn } from "@/lib/utils";

export function Logo({ className, markOnly = false }: { className?: string; markOnly?: boolean }) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <svg viewBox="0 0 48 48" className="h-9 w-9 shrink-0" aria-hidden="true">
        <defs>
          <linearGradient id="logo-gradient" x1="0" y1="0" x2="1" y2="1">
            <stop stopColor="#2dd4bf" />
            <stop offset="0.55" stopColor="#14b8a6" />
            <stop offset="1" stopColor="#a78bfa" />
          </linearGradient>
        </defs>
        <rect width="48" height="48" rx="13" fill="hsl(var(--card))" stroke="hsl(var(--border))" />
        <path
          d="M24 8.5l12.5 4.8v9.4c0 8.4-5.6 14.4-12.5 16.8-6.9-2.4-12.5-8.4-12.5-16.8v-9.4z"
          fill="none"
          stroke="url(#logo-gradient)"
          strokeWidth="2.8"
        />
        <path
          d="M17.8 24l4 4 8.5-9.1"
          fill="none"
          stroke="url(#logo-gradient)"
          strokeWidth="2.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      {!markOnly ? (
        <span className="font-display text-[17px] font-bold tracking-tight">
          Erasure<span className="text-gradient">Proof</span>
        </span>
      ) : null}
    </span>
  );
}
