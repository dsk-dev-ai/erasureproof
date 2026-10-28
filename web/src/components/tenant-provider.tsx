import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { TokenDialog } from "@/components/auth/token-dialog";
import { useTenants } from "@/hooks/use-api";
import { getApiToken } from "@/lib/api";
import type { Tenant } from "@/lib/types";

interface TenantContextValue {
  tenantId?: string;
  tenant?: Tenant;
  tenants: Tenant[];
  setTenantId: (id: string) => void;
  isLoading: boolean;
}

const TenantContext = createContext<TenantContextValue | null>(null);

export function TenantProvider({ children }: { children: React.ReactNode }) {
  const [tokenPresent, setTokenPresent] = useState(() => Boolean(getApiToken()));
  const { data: tenants = [], isLoading } = useTenants(tokenPresent);
  const [tokenOpen, setTokenOpen] = useState(false);
  const [tenantId, setTenantIdState] = useState<string | undefined>(() => {
    if (typeof window === "undefined") return undefined;
    return window.localStorage.getItem("erasureproof.tenant") ?? undefined;
  });

  useEffect(() => {
    if (!tenants.length) return;
    const stored = tenantId && tenants.some((tenant) => tenant.id === tenantId);
    if (!stored) {
      const preferred =
        tenants.find((tenant) => tenant.id === "ten_demo") ?? tenants[0];
      setTenantIdState(preferred.id);
      window.localStorage.setItem("erasureproof.tenant", preferred.id);
    }
  }, [tenantId, tenants]);

  const setTenantId = useCallback((id: string) => {
    setTenantIdState(id);
    window.localStorage.setItem("erasureproof.tenant", id);
  }, []);

  useEffect(() => {
    const open = () => setTokenOpen(true);
    const onUnauthorized = () => {
      if (!getApiToken()) setTokenOpen(true);
    };
    const onTokenChanged = () => setTokenPresent(Boolean(getApiToken()));
    window.addEventListener("erasureproof:show-token", open);
    window.addEventListener("erasureproof:unauthorized", onUnauthorized);
    window.addEventListener("erasureproof:token-changed", onTokenChanged);
    return () => {
      window.removeEventListener("erasureproof:show-token", open);
      window.removeEventListener("erasureproof:unauthorized", onUnauthorized);
      window.removeEventListener("erasureproof:token-changed", onTokenChanged);
    };
  }, []);

  const tenant = tenants.find((item) => item.id === tenantId);
  const value = useMemo(
    () => ({ tenantId, tenant, tenants, setTenantId, isLoading }),
    [tenantId, tenant, tenants, setTenantId, isLoading],
  );

  return (
    <TenantContext.Provider value={value}>
      {children}
      <TokenDialog open={tokenOpen} onClose={() => setTokenOpen(false)} />
    </TenantContext.Provider>
  );
}

export function useTenant() {
  const context = useContext(TenantContext);
  if (!context) throw new Error("useTenant must be used inside TenantProvider");
  return context;
}
