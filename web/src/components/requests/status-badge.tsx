import { Badge } from "@/components/ui/badge";
import { humanize, statusTone } from "@/lib/utils";

export function StatusBadge({ status, dot = true }: { status?: string | null; dot?: boolean }) {
  const tone = statusTone(status);
  const variant =
    tone === "success"
      ? "success"
      : tone === "danger"
        ? "danger"
        : tone === "warning"
          ? "warning"
          : tone === "muted"
            ? "muted"
            : "neutral";
  return (
    <Badge variant={variant} dot={dot}>
      {humanize(status)}
    </Badge>
  );
}
