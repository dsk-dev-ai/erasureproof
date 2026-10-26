import type {
  Connector,
  EvidenceItem,
  ExposureReport,
  LedgerEntry,
  Overview,
  RequestOut,
  RunResponse,
  StepGraph,
  Subject,
  Tenant,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "/v1";
const API_ROOT = API_BASE.replace(/\/v1\/?$/, "");

async function requestUrl<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // Keep the HTTP status when the body is not JSON.
    }
    throw new Error(detail);
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
  verifyEvidence: (id: string) =>
    request<{ evidence_id: string; valid: boolean }>(`/evidence/${id}/verify`, { method: "POST" }),
  ledger: (limit = 100) =>
    request<{ head: string; count: number; entries: LedgerEntry[] }>(`/ledger${query({ limit })}`),
  verifyLedger: () =>
    request<{ valid: boolean; detail: string; head: string }>("/ledger/verify", { method: "POST" }),
  policies: () =>
    request<{ jurisdictions: string[]; policies: Record<string, unknown> }>("/policies"),
  seedDemo: () => request<Record<string, unknown>>("/demo/seed", { method: "POST" }),
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
