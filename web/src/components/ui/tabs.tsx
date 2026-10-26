import { cn } from "@/lib/utils";

interface TabsProps {
  value: string;
  onChange: (value: string) => void;
  items: Array<{ value: string; label: string; count?: number }>;
  className?: string;
}

export function Tabs({ value, onChange, items, className }: TabsProps) {
  return (
    <div className={cn("no-scrollbar flex gap-1 overflow-x-auto rounded-xl border border-border/70 bg-muted/30 p-1", className)}>
      {items.map((item) => (
        <button
          key={item.value}
          onClick={() => onChange(item.value)}
          className={cn(
            "relative flex items-center gap-2 whitespace-nowrap rounded-lg px-3.5 py-2 text-xs font-semibold transition-colors",
            value === item.value
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {item.label}
          {item.count !== undefined ? (
            <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
              {item.count}
            </span>
          ) : null}
        </button>
      ))}
    </div>
  );
}
