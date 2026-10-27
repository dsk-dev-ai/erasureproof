export type Status = "COMPLETE" | "INCOMPLETE" | "NOT_APPLICABLE" | "PENDING";

export interface Tenant {
  id: string;
  name: string;
  jurisdiction: string;
  created_at: string;
}

export interface RequestOut {
  id: string;
  tenant_id: string;
  email: string;
  status: Status;
  request_text: string;
  requested_at: string;
  audit_at: string;
  jurisdiction: string;
  result?: RunResponse | null;
  plan?: Plan | null;
  approval_status?: string | null;
  approval_expires_at?: string | null;
  approval_consumed_at?: string | null;
  approved_by?: string | null;
}

export interface Approval {
  id: string;
  request_id: string;
  tenant_id: string;
  status: string;
  requested_by: string;
  decided_by: string | null;
  reason: string;
  created_at: string;
  decided_at: string | null;
  expires_at: string | null;
  consumed_at: string | null;
}

export interface AuditEvent {
  id: string;
  tenant_id: string | null;
  actor: string;
  actor_role: string;
  action: string;
  resource_type: string;
  resource_id: string;
  request_id: string | null;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface RequestSummary {
  id: string;
  tenant_id: string;
  email: string;
  status: Status;
  request_text: string;
  requested_at: string;
  audit_at: string;
  created_at: string;
  updated_at: string;
  jurisdiction: string;
  findings: number;
  verifications: number;
  verifications_passed: number;
  remediation_applied: boolean;
}

export interface Overview {
  tenant_id: string | null;
  generated_at: string;
  totals: {
    requests: number;
    subjects: number;
    connectors: number;
    evidence: number;
    attestations: number;
    ledger_entries: number;
  };
  statuses: Record<Status, number>;
  verification: { checks: number; passed: number; pass_rate: number };
  attestation_coverage: number;
  open_findings: number;
  risk_score: number;
  recent_requests: RequestSummary[];
  trend: Array<{ date: string; count: number }>;
  ledger: { head: string; recent: LedgerEntry[] };
  policies: string[];
  features: {
    exposure_enabled: boolean;
    demo_enabled: boolean;
    environment: string;
    auth_mode: string;
    approval_required: boolean;
  };
}

export interface PlanStep {
  step_no: number;
  phase: "FINDING" | "REMEDIATION" | "VERIFICATION";
  system_id: string;
  resource_id: string;
  operation: string;
  state: string;
  evidence_id: string;
  category?: string | null;
}

export interface Plan {
  request_id: string;
  status: string;
  steps: PlanStep[];
}

export interface GraphNode {
  id: string;
  step_no: number;
  phase: "FINDING" | "REMEDIATION" | "VERIFICATION";
  system_id: string;
  resource_id: string;
  operation: string;
  state: string;
  category?: string | null;
  label: string;
  depends_on: string[];
}

export interface StepGraph {
  request_id: string;
  nodes: GraphNode[];
  edges: Array<[string, string]>;
  cycle: boolean;
  critical_path: string[];
  order: string[];
}

export interface VerificationResult {
  operation: string;
  system_id: string;
  resource_id: string;
  expected: string;
  actual: string;
  passed: boolean;
  detail: string;
  evidence_id: string;
}

export interface ActionResult {
  system_id: string;
  resource_id: string;
  operation: string;
  success: boolean;
  supported: boolean;
  detail: string;
}

export interface Attestation {
  request_id: string;
  status: string;
  issued_at: string;
  signature: string;
  path: string;
  payload: Record<string, unknown>;
}

export interface RunResponse {
  request_id: string;
  status: Status;
  plan: Plan;
  graph?: StepGraph | null;
  verification: VerificationResult[];
  actions: ActionResult[];
  attestation?: Attestation | null;
  ledger_head: string;
  remediation_applied: boolean;
  errors: string[];
}

export interface Subject {
  id: string;
  tenant_id: string;
  user_id: string;
  identifiers: Array<{
    type: string;
    value: string;
    valid_from?: string | null;
    valid_to?: string | null;
    source: string;
  }>;
  created_at: string;
}

export interface Connector {
  id: string;
  tenant_id: string;
  type: string;
  name: string;
  config: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
}

export interface EvidenceItem {
  evidence_id: string;
  sha256: string;
  source: string;
  captured_at: string;
  size: number;
  content_type: string;
  request_id?: string | null;
}

export interface LedgerEntry {
  seq: number;
  timestamp: string;
  event: string;
  request_id: string | null;
  payload: Record<string, unknown>;
  prev_hash: string;
  hash: string;
}

export interface ExposureHit {
  kind: string;
  url: string;
  title: string;
  snippet: string;
  severity: string;
  confidence: number;
  collector: string;
  identifiers: string[];
  metadata: Record<string, unknown>;
}

export interface ExposureReport {
  scanned_at: string;
  authorized: boolean;
  risk_score: number;
  severity: string;
  hits: ExposureHit[];
  errors: string[];
  collectors: string[];
  report_evidence_id: string;
}
