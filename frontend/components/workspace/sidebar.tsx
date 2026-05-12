"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useCallback, useEffect } from "react";
import { PANELS, getActivePanel, type PanelKey } from "@/lib/panels";
import { useT } from "@/lib/i18n/provider";

export { PANELS, getActivePanel };
export type { PanelKey };

export function WorkspaceSidebar() {
  const t = useT();
  const router = useRouter();
  const params = useSearchParams();
  const pathname = usePathname();
  const active = getActivePanel(params?.get("view") ?? null);

  const goTo = useCallback(
    (key: PanelKey) => {
      const sp = new URLSearchParams(params?.toString() ?? "");
      if (key === "overview") sp.delete("view");
      else sp.set("view", key);
      const qs = sp.toString();
      router.push(qs ? `${pathname}?${qs}` : pathname || "");
    },
    [pathname, params, router]
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const tag = (e.target as HTMLElement | null)?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || (e.target as HTMLElement | null)?.isContentEditable) return;
      const found = PANELS.find((p) => p.hotkey === e.key);
      if (found) {
        e.preventDefault();
        goTo(found.key);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [goTo]);

  return (
    <nav
      aria-label={t("workspace.panelsLabel")}
      className="
        -mx-4 flex gap-1 overflow-x-auto scrollbar-thin px-4 py-1 text-sm
        [scrollbar-width:thin] [scroll-snap-type:x_mandatory]
        lg:mx-0 lg:grid lg:gap-0.5 lg:overflow-visible lg:px-0
      "
    >
      {PANELS.map((p) => {
        const isActive = p.key === active;
        return (
          <button
            key={p.key}
            onClick={() => goTo(p.key)}
            aria-current={isActive ? "page" : undefined}
            className={
              "group relative flex shrink-0 items-center justify-between gap-2 whitespace-nowrap rounded-full px-3 py-2 text-left transition focus-ring [scroll-snap-align:start] " +
              "lg:shrink lg:rounded-md lg:px-3 lg:py-1.5 " +
              (isActive
                ? "bg-ink text-paper"
                : "bg-paper-deep/60 text-ink/70 hover:bg-ink/5 hover:text-ink lg:bg-transparent")
            }
          >
            <span>{t(p.labelKey)}</span>
            <span
              aria-hidden
              className={
                "kbd hidden lg:inline-flex " +
                (isActive ? "!bg-paper/15 !text-paper/70 !border-paper/15" : "")
              }
            >
              {p.hotkey}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
