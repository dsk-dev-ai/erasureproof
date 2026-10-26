import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.08em]",
  {
    variants: {
      variant: {
        default: "border-primary/25 bg-primary/10 text-primary",
        success: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
        danger: "border-rose-400/25 bg-rose-400/10 text-rose-300",
        warning: "border-amber-400/25 bg-amber-400/10 text-amber-300",
        muted: "border-border/70 bg-muted/50 text-muted-foreground",
        neutral: "border-border/70 bg-secondary/60 text-secondary-foreground",
        outline: "border-border bg-transparent text-muted-foreground",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
  dot?: boolean;
}

export function Badge({ className, variant, dot, children, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props}>
      {dot ? <span className="h-1.5 w-1.5 rounded-full bg-current" /> : null}
      {children}
    </span>
  );
}
