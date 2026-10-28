import type {
  ApiKey,
  ApiKeyCreated,
  Approval,
  AuditEvent,
  Connector,
  EvidenceItem,
  ExposureReport,
  LedgerEntry,
  Overview,
  RequestOut,
  RunResponse,
  Sandbox,
  StepGraph,
  Subject,
  Tenant,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "/v1";
const API_ROOT = API_BASE.replace(/\/v1\/?$/, "");
const TOKEN_KEY = "erasureproof.token";

export function getApiToken(): string {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setApiToken(token: string): void {
  if (typeof window === "undefined") return;
  const value = token.trim();
  if (value) window.localStorage.setItem(TOKEN_KEY, value);
  else window.localStorage.removeItem(TOKEN_KEY);
  window.dispatchEvent(
    new CustomEvent("erasureproof:token-changed", { detail: value }),
  );
}

export function clearApiToken(): void {
  setApiToken("");
}

function authHeaders(): Record<string, string> {
  const token = getApiToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function unauthorized(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("erasureproof:unauthorized"));
  }
}

async function errorDetail(response: Response): Promise<string> {
  let detail = `${response.status} ${response.statusText}`;
  try {
    const body = (await response.json()) as { detail?: string };
    if (body.detail) detail = body.detail;
  } catch {
    // Keep the HTTP status when the body is not JSON.
  }
  return detail;
}

async function requestUrl<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...authHeaders(),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    if (response.status === 401) unauthorized();
    throw new Error(await errorDetail(response));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  return requestUrl(`${API_BASE}${path}`, init);
}

function query(params: Record<string, string | number | boolean | undefined>) {
  const values = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") values.set(key, String(value));
  }
  const text = values.toString();
  return text ? `?${text}` : "";
}

export const api = {
  base: API_BASE,
  overview: (tenantId?: string) =>
    request<Overview>(`/overview${query({ tenant_id: tenantId })}`),
  tenants: () => request<Tenant[]>("/tenants"),
  requests: (tenantId?: string) =>
    request<RequestOut[]>(`/requests${query({ tenant_id: tenantId })}`),
  request: (id: string) => request<RequestOut>(`/requests/${id}`),
  run: (id: string, options?: { remediate?: boolean; force?: boolean }) =>
    request<RunResponse>(
      `/requests/${id}/run${query({
        remediate: options?.remediate ?? true,
        force: options?.force ?? false,
      })}`,
      { method: "POST" },
    ),
  graph: (id: string) => request<StepGraph>(`/requests/${id}/graph`),
  approvals: (id: string) => request<Approval[]>(`/requests/${id}/approvals`),
  decideApproval: (id: string, decision: "APPROVED" | "REJECTED", reason: string) =>
    request<Approval>(`/requests/${id}/approval`, {
      method: "POST",
      body: JSON.stringify({ decision, reason }),
    }),
  activeApprovals: (tenantId?: string) =>
    request<Approval[]>(`/approvals/active${query({ tenant_id: tenantId })}`),
  auditEvents: (limit = 100, tenantId?: string) =>
    request<AuditEvent[]>(
      `/audit-events${query({ limit, tenant_id: tenantId })}`,
    ),
  createRequest: (body: {
    tenant_id: string;
    email: string;
    request_text: string;
    audit_at: string;
    requested_at?: string;
    jurisdiction?: string;
  }) =>
    request<RequestOut>("/requests", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  subjects: (tenantId: string) => request<Subject[]>(`/tenants/${tenantId}/subjects`),
  connectors: (tenantId: string) =>
    request<Connector[]>(`/tenants/${tenantId}/connectors`),
  connectorTypes: () => request<{ types: string[] }>("/connector-types"),
  createConnector: (body: {
    tenant_id: string;
    type: string;
    name: string;
    config: Record<string, unknown>;
    enabled?: boolean;
  }) =>
    request<Connector>("/connectors", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deleteConnector: (id: string) =>
    request<void>(`/connectors/${id}`, { method: "DELETE" }),
  evidence: (limit = 100) => request<{ count: number; items: EvidenceItem[] }>(`/evidence${query({ limit })}`),
  evidenceContentUrl: (id: string) => `${API_BASE}/evidence/${id}/content`,
  openEvidence: async (id: string) => {
    const popup = window.open("about:blank", "_blank");
    if (popup) popup.opener = null;
    const response = await fetch(api.evidenceContentUrl(id), { headers: authHeaders() });
    if (!response.ok) {
      popup?.close();
      if (response.status === 401) unauthorized();
      throw new Error(await errorDetail(response));
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    if (popup) {
      popup.location.href = url;
    } else {
      window.open(url, "_blank", "noopener,noreferrer");
    }
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  },
  downloadAudit: async (tenantId?: string) => {
    const response = await fetch(
      `${API_BASE}/audit-events/export${query({ tenant_id: tenantId })}`,
      { headers: authHeaders() },
    );
    if (!response.ok) {
      if (response.status === 401) unauthorized();
      throw new Error(await errorDetail(response));
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "erasureproof-audit.csv";
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 5_000);
  },
  verifyEvidence: (id: string) =>
    request<{ evidence_id: string; valid: boolean }>(`/evidence/${id}/verify`, { method: "POST" }),
  ledger: (limit = 100) =>
    request<{ head: string; count: number; entries: LedgerEntry[] }>(`/ledger${query({ limit })}`),
  verifyLedger: () =>
    request<{ valid: boolean; detail: string; head: string }>("/ledger/verify", { method: "POST" }),
  policies: () =>
    request<{ jurisdictions: string[]; policies: Record<string, unknown> }>("/policies"),
  seedDemo: () => request<Record<string, unknown>>("/demo/seed", { method: "POST" }),
  createSandbox: (body: { workspace_name?: string; jurisdiction?: "gdpr" | "ccpa" } = {}) =>
    request<Sandbox>("/onboarding/sandbox", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  apiKeys: (tenantId?: string, includeRevoked = false) =>
    request<ApiKey[]>(
      `/api-keys${query({ tenant_id: tenantId, include_revoked: includeRevoked })}`,
    ),
  createApiKey: (body: {
    tenant_id?: string;
    name: string;
    role: "viewer" | "operator" | "admin";
    expires_in_days?: number | null;
  }) =>
    request<ApiKeyCreated>("/api-keys", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  rotateApiKey: (id: string) =>
    request<ApiKeyCreated>(`/api-keys/${id}/rotate`, { method: "POST" }),
  revokeApiKey: (id: string) => request<void>(`/api-keys/${id}`, { method: "DELETE" }),
  exposure: (body: {
    email?: string;
    phone?: string;
    name?: string;
    usernames?: string[];
    urls?: string[];
    collectors?: string[];
    authorized: boolean;
  }) =>
    request<ExposureReport>("/exposure/scan", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  health: () =>
    requestUrl<{ status: string; version: string; database: string }>(`${API_ROOT}/healthz`),
};
