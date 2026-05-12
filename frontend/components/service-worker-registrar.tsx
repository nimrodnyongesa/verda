"use client";

import { useEffect } from "react";

/**
 * ServiceWorkerRegistrar — registers the cache-shell SW exactly once
 * after first paint.
 *
 * Notes on safety:
 *   * Registration is wrapped in a feature-detect — older browsers and
 *     non-secure contexts (HTTP, except localhost) silently no-op.
 *   * The registration happens *after* the page is interactive
 *     (`requestIdleCallback` when available) so it never delays the
 *     first render.
 *   * In dev (`NODE_ENV !== production`) we deliberately *unregister*
 *     any previous SW so a stale cache from a prior session can't serve
 *     a stale dev bundle. This is the most common gotcha when adding
 *     a SW mid-project.
 *   * The SW itself never caches `/api/*` or any auth flow — it only
 *     warms the static asset shell. See `public/sw.js`.
 */
export function ServiceWorkerRegistrar() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!("serviceWorker" in navigator)) return;

    const isDev = process.env.NODE_ENV !== "production";

    const run = async () => {
      try {
        if (isDev) {
          const regs = await navigator.serviceWorker.getRegistrations();
          await Promise.all(regs.map((r) => r.unregister()));
          return;
        }
        await navigator.serviceWorker.register("/sw.js", { scope: "/" });
      } catch {
        // Silent fail — a missing SW shouldn't break the app.
      }
    };

    const w = window as Window & {
      requestIdleCallback?: (cb: () => void) => number;
    };
    if (typeof w.requestIdleCallback === "function") {
      w.requestIdleCallback(run);
    } else {
      window.setTimeout(run, 1500);
    }
  }, []);

  return null;
}
