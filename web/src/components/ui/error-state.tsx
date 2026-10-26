import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

export function ErrorState({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div className="surface flex min-h-48 flex-col items-center justify-center rounded-3xl p-8 text-center">
      <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-destructive/10 text-destructive">
        <AlertTriangle className="h-5 w-5" />
      </span>
      <p className="font-medium">The console could not load this view.</p>
      <p className="mt-1 max-w-md text-sm text-muted-foreground">{message ?? "Check that the API is running."}</p>
      {onRetry ? (
        <Button variant="secondary" className="mt-5" onClick={onRetry}>
          <RefreshCw className="h-4 w-4" /> Retry
        </Button>
      ) : null}
    </div>
  );
}
