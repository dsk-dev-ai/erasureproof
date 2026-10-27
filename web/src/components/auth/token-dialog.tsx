import { useEffect, useState } from "react";
import { KeyRound, Loader2, ShieldCheck, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { clearApiToken, getApiToken, setApiToken } from "@/lib/api";

export function TokenDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const client = useQueryClient();
  const [token, setToken] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) setToken(getApiToken());
  }, [open]);

  const save = async () => {
    if (!token.trim()) {
      toast.error("Enter an API token");
      return;
    }
    setSaving(true);
    try {
      setApiToken(token);
      await client.invalidateQueries();
      toast.success("API access token saved");
      onClose();
    } finally {
      setSaving(false);
    }
  };

  const clear = async () => {
    clearApiToken();
    setToken("");
    await client.invalidateQueries();
    toast.success("API access token removed");
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="API access"
      description="This deployment requires a bearer token or API key for control-plane endpoints."
    >
      <div className="space-y-4">
        <div className="flex items-start gap-3 rounded-2xl border border-primary/20 bg-primary/5 p-3.5">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
          <p className="text-xs leading-5 text-muted-foreground">
            The token is stored only in this browser and sent as an
            <span className="mx-1 font-mono text-foreground/80">Authorization: Bearer</span>
            header. Use a short-lived token and clear it on shared devices.
          </p>
        </div>
        <label className="block space-y-1.5">
          <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            Bearer token or API key
          </span>
          <Input
            type="password"
            autoComplete="off"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void save();
            }}
            placeholder="Paste token"
          />
        </label>
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="ghost" onClick={() => void clear()} disabled={saving}>
            <Trash2 className="h-3.5 w-3.5" /> Clear
          </Button>
          <Button variant="brand" onClick={() => void save()} disabled={saving}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
            Save token
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
