import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useOverview(tenantId?: string) {
  return useQuery({
    queryKey: ["overview", tenantId ?? "all"],
    queryFn: () => api.overview(tenantId),
  });
}

export function useTenants(enabled = true) {
  return useQuery({ queryKey: ["tenants"], queryFn: api.tenants, enabled });
}

export function useRequests(tenantId?: string) {
  return useQuery({
    queryKey: ["requests", tenantId ?? "all"],
    queryFn: () => api.requests(tenantId),
  });
}

export function useRequest(id?: string) {
  return useQuery({
    queryKey: ["request", id],
    queryFn: () => api.request(id as string),
    enabled: Boolean(id && id !== "demo"),
  });
}

export function useApprovals(id?: string) {
  return useQuery({
    queryKey: ["approvals", id],
    queryFn: () => api.approvals(id as string),
    enabled: Boolean(id && id !== "demo"),
    retry: false,
  });
}

export function useDecideApproval() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      decision,
      reason,
    }: {
      id: string;
      decision: "APPROVED" | "REJECTED";
      reason: string;
    }) => api.decideApproval(id, decision, reason),
    onSuccess: (_data, variables) => {
      void client.invalidateQueries({ queryKey: ["request", variables.id] });
      void client.invalidateQueries({ queryKey: ["approvals", variables.id] });
      void client.invalidateQueries({ queryKey: ["overview"] });
      void client.invalidateQueries({ queryKey: ["requests"] });
    },
  });
}

export function useGraph(id?: string) {
  return useQuery({
    queryKey: ["graph", id],
    queryFn: () => api.graph(id as string),
    enabled: Boolean(id && id !== "demo"),
    retry: false,
  });
}

export function useSubjects(tenantId?: string) {
  return useQuery({
    queryKey: ["subjects", tenantId],
    queryFn: () => api.subjects(tenantId as string),
    enabled: Boolean(tenantId),
  });
}

export function useConnectors(tenantId?: string) {
  return useQuery({
    queryKey: ["connectors", tenantId],
    queryFn: () => api.connectors(tenantId as string),
    enabled: Boolean(tenantId),
  });
}

export function useConnectorTypes() {
  return useQuery({ queryKey: ["connector-types"], queryFn: api.connectorTypes });
}

export function useEvidence() {
  return useQuery({ queryKey: ["evidence"], queryFn: () => api.evidence(200) });
}

export function useLedger() {
  return useQuery({ queryKey: ["ledger"], queryFn: () => api.ledger(200) });
}

export function usePolicies() {
  return useQuery({ queryKey: ["policies"], queryFn: api.policies });
}

export function useSeedDemo() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.seedDemo,
    onSuccess: () => {
      void client.invalidateQueries();
    },
  });
}

export function useRunRequest() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, force }: { id: string; force?: boolean }) =>
      api.run(id, { remediate: true, force }),
    onSuccess: (_data, variables) => {
      void client.invalidateQueries({ queryKey: ["request", variables.id] });
      void client.invalidateQueries({ queryKey: ["graph", variables.id] });
      void client.invalidateQueries({ queryKey: ["overview"] });
      void client.invalidateQueries({ queryKey: ["requests"] });
      void client.invalidateQueries({ queryKey: ["ledger"] });
      void client.invalidateQueries({ queryKey: ["evidence"] });
    },
  });
}

export function useCreateRequest() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.createRequest,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["overview"] });
      void client.invalidateQueries({ queryKey: ["requests"] });
    },
  });
}

export function useCreateConnector() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.createConnector,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["connectors"] });
      void client.invalidateQueries({ queryKey: ["overview"] });
    },
  });
}

export function useDeleteConnector() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.deleteConnector,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["connectors"] });
      void client.invalidateQueries({ queryKey: ["overview"] });
    },
  });
}

export function useVerifyLedger() {
  return useMutation({ mutationFn: api.verifyLedger });
}

export function useVerifyEvidence() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.verifyEvidence,
    onSuccess: () => void client.invalidateQueries({ queryKey: ["evidence"] }),
  });
}

export function useCreateSandbox() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.createSandbox,
    onSuccess: () => void client.invalidateQueries(),
  });
}

export function useApiKeys(tenantId?: string, includeRevoked = false) {
  return useQuery({
    queryKey: ["api-keys", tenantId ?? "all", includeRevoked],
    queryFn: () => api.apiKeys(tenantId, includeRevoked),
    enabled: Boolean(tenantId),
    retry: false,
  });
}

export function useCreateApiKey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.createApiKey,
    onSuccess: () => void client.invalidateQueries({ queryKey: ["api-keys"] }),
  });
}

export function useRotateApiKey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.rotateApiKey,
    onSuccess: () => void client.invalidateQueries({ queryKey: ["api-keys"] }),
  });
}

export function useRevokeApiKey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.revokeApiKey,
    onSuccess: () => void client.invalidateQueries({ queryKey: ["api-keys"] }),
  });
}
