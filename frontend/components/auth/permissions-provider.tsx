"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type {
  Permission,
  PermissionsPayload,
} from "@/lib/auth/permissions";
import { hasPermission } from "@/lib/auth/permissions";

type Ctx = {
  payload: PermissionsPayload | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  has: (...needed: Permission[]) => boolean;
};

const PermissionsContext = createContext<Ctx | null>(null);

/**
 * Fetches `/api/be/auth/permissions` once on mount and exposes the result
 * via React context. Using this from any client component avoids duplicate
 * round-trips and keeps role-aware UI consistent across panels.
 */
export function PermissionsProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [payload, setPayload] = useState<PermissionsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/be/auth/permissions");
      if (!res.ok) {
        // 401 just means signed-out; treat as empty payload, not error.
        if (res.status === 401) {
          setPayload(null);
          return;
        }
        throw new Error(`HTTP ${res.status}`);
      }
      const data = (await res.json()) as PermissionsPayload;
      setPayload(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load permissions");
      setPayload(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo<Ctx>(
    () => ({
      payload,
      loading,
      error,
      refresh,
      has: (...needed: Permission[]) => hasPermission(payload, ...needed),
    }),
    [payload, loading, error, refresh]
  );

  return (
    <PermissionsContext.Provider value={value}>
      {children}
    </PermissionsContext.Provider>
  );
}

export function usePermissions(): Ctx {
  const ctx = useContext(PermissionsContext);
  if (!ctx) {
    // Safe default when the provider isn't mounted (e.g. server-side
    // children that never re-hydrate). Anything that needs a real check
    // should be inside the provider tree.
    return {
      payload: null,
      loading: false,
      error: null,
      refresh: async () => undefined,
      has: () => false,
    };
  }
  return ctx;
}

/**
 * Conditional render guard. Renders ``children`` only when the signed-in
 * user has every named permission. ``fallback`` is shown otherwise — pass
 * a tooltip-shaped explainer for buttons that should look "disabled but
 * present" instead of silently disappearing.
 */
export function Can({
  permission,
  permissions,
  children,
  fallback = null,
}: {
  permission?: Permission;
  permissions?: Permission[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}) {
  const { has } = usePermissions();
  const needed = permissions ?? (permission ? [permission] : []);
  return has(...needed) ? <>{children}</> : <>{fallback}</>;
}
