import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { useTenant } from "@/components/tenant-provider";
import { useCreateRequest } from "@/hooks/use-api";

function localDateTime() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 16);
}

const jurisdictions = ["EU", "US-CA", "US", "IN", "BR", "CA", "UK"];

export function NewRequestDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { tenant, tenantId } = useTenant();
  const create = useCreateRequest();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [text, setText] = useState("");
  const [auditAt, setAuditAt] = useState(localDateTime);
  const [jurisdiction, setJurisdiction] = useState(tenant?.jurisdiction ?? "EU");

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!tenantId) {
      toast.error("Load a workspace first");
      return;
    }
    try {
      const created = await create.mutateAsync({
        tenant_id: tenantId,
        email: email.trim(),
        request_text: text.trim(),
        audit_at: new Date(auditAt).toISOString(),
        jurisdiction,
      });
      toast.success("Request created. Run the audit to build a plan.");
      onClose();
      setEmail("");
      setText("");
      navigate(`/app/requests/${created.id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not create request");
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="New deletion request"
      description="The request text is classified before any remediation. Non-deletion intents become NOT_APPLICABLE."
    >
      <form onSubmit={(event) => void submit(event)} className="space-y-4">
        <div>
          <Label htmlFor="request-email">Subject email</Label>
          <Input
            id="request-email"
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="alice@example.com"
          />
        </div>
        <div>
          <Label htmlFor="request-text">Request text</Label>
          <Textarea
            id="request-text"
            required
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Please delete all personal data associated with my account."
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="audit-at">Audit at</Label>
            <Input
              id="audit-at"
              type="datetime-local"
              required
              value={auditAt}
              onChange={(event) => setAuditAt(event.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="jurisdiction">Jurisdiction</Label>
            <Select
              id="jurisdiction"
              value={jurisdiction}
              onChange={(event) => setJurisdiction(event.target.value)}
            >
              {jurisdictions.map((item) => (
                <option key={item} value={item}>{item}</option>
              ))}
            </Select>
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="brand" disabled={create.isPending}>
            {create.isPending ? "Creating…" : "Create & open"}
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
