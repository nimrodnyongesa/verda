"use client";

import { useEffect, useState } from "react";
import { dismissToast, subscribe, type Toast } from "@/lib/toast";

const VARIANT: Record<Toast["variant"], { bar: string; icon: string }> = {
  info: { bar: "bg-gold", icon: "ℹ" },
  success: { bar: "bg-fern", icon: "✓" },
  error: { bar: "bg-rust", icon: "!" },
};

export function Toaster() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => subscribe(setToasts), []);

  return (
    <div
      aria-live="polite"
      aria-atomic="true"
      className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2"
    >
      {toasts.map((t) => {
        const v = VARIANT[t.variant];
        return (
          <div
            key={t.id}
            role="status"
            className="pointer-events-auto group relative overflow-hidden rounded-lg border border-ink/10 bg-white shadow-lg shadow-ink/10 backdrop-blur"
          >
            <span className={`absolute inset-y-0 left-0 w-1 ${v.bar}`} aria-hidden />
            <div className="flex items-start gap-3 px-4 py-3 pl-5">
              <span className={`mt-0.5 inline-flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-bold text-paper ${v.bar}`}>
                {v.icon}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-ink">{t.title}</div>
                {t.body ? (
                  <p className="mt-0.5 text-xs text-ink/65 break-words">{t.body}</p>
                ) : null}
              </div>
              <button
                aria-label="Dismiss"
                onClick={() => dismissToast(t.id)}
                className="-mr-1 rounded p-1 text-ink/40 hover:bg-ink/5 hover:text-ink"
              >
                ×
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
